import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from revise.models import DSASheet, DSASheetProblem, GlobalProblem, Pattern


class Command(BaseCommand):
    help = 'Seed curated DSA sheets and their global problems from local JSON files.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=Path,
            default=Path(__file__).resolve().parents[2] / 'data' / 'sheets',
            help='A JSON file or directory of JSON files (defaults to revise/data/sheets).',
        )

    def handle(self, *args, **options):
        source_path = options['path']
        if source_path.is_dir():
            json_files = sorted(source_path.glob('*.json'))
        elif source_path.is_file() and source_path.suffix.lower() == '.json':
            json_files = [source_path]
        else:
            raise CommandError(f'JSON file or directory not found: {source_path}')

        if not json_files:
            raise CommandError(f'No JSON files found in {source_path}')

        totals = {
            'sheets_added': 0,
            'sheets_skipped': 0,
            'problems_added': 0,
            'problems_skipped': 0,
            'links_added': 0,
            'links_skipped': 0,
        }
        for json_file in json_files:
            try:
                payload = json.loads(json_file.read_text(encoding='utf-8'))
                sheet_payloads = payload if isinstance(payload, list) else payload.get('sheets', [payload])
            except (json.JSONDecodeError, AttributeError) as error:
                raise CommandError(f'Invalid sheet JSON in {json_file}: {error}') from error

            if not isinstance(sheet_payloads, list):
                raise CommandError(f'Expected a sheet object or list of sheets in {json_file}')
            for sheet_payload in sheet_payloads:
                self._seed_sheet(sheet_payload, totals, json_file)

        self.stdout.write(self.style.SUCCESS(
            'Finished: '
            f"{totals['sheets_added']} sheets added, {totals['sheets_skipped']} sheets reused; "
            f"{totals['problems_added']} global problems added, {totals['problems_skipped']} reused; "
            f"{totals['links_added']} sheet links added, {totals['links_skipped']} already present."
        ))

    @transaction.atomic
    def _seed_sheet(self, data, totals, source):
        if not isinstance(data, dict):
            raise CommandError(f'Each sheet in {source} must be an object.')

        title = data.get('title') or data.get('name')
        problems_data = data.get('problems')
        if not title or not isinstance(problems_data, list):
            raise CommandError(f'Each sheet in {source} requires a title and a problems list.')

        slug = data.get('slug') or slugify(title) or 'dsa-sheet'
        sheet, created = DSASheet.objects.get_or_create(
            slug=slug,
            defaults={
                'title': title,
                'description': data.get('description', ''),
                'author': data.get('author', ''),
                'cover_image_url': data.get('cover_image_url', ''),
                'is_featured': data.get('is_featured', False),
            },
        )
        if created:
            totals['sheets_added'] += 1
            self.stdout.write(f'Added sheet: {title}')
        else:
            totals['sheets_skipped'] += 1
            changed_fields = []
            for field in ('title', 'description', 'author', 'cover_image_url', 'is_featured'):
                if field in data and getattr(sheet, field) != data[field]:
                    setattr(sheet, field, data[field])
                    changed_fields.append(field)
            if changed_fields:
                sheet.save(update_fields=changed_fields)
            self.stdout.write(f'Skipped existing sheet: {title}')

        added_in_sheet = 0
        for index, item in enumerate(problems_data, start=1):
            if not isinstance(item, dict):
                raise CommandError(f'Problem #{index} in {source} must be an object.')
            required = ('title', 'leetcode_id', 'link', 'difficulty')
            missing = [field for field in required if not item.get(field)]
            if missing:
                raise CommandError(f'Problem #{index} in {source} is missing: {", ".join(missing)}')

            pattern_name = item.get('pattern') or item.get('category')
            pattern = None
            if pattern_name:
                pattern, _ = Pattern.objects.get_or_create(p_name=pattern_name)
            problem, problem_created = GlobalProblem.objects.get_or_create(
                leetcode_id=item['leetcode_id'],
                defaults={
                    'title': item['title'],
                    'link': item['link'],
                    'difficulty': item['difficulty'],
                    'pattern': pattern,
                    'description': item.get('description', ''),
                },
            )
            if pattern and not problem.pattern_id:
                problem.pattern = pattern
                problem.save(update_fields=['pattern'])
            if pattern:
                problem.patterns.add(pattern)

            _, sheet_problem_created = DSASheetProblem.objects.get_or_create(
                sheet=sheet,
                problem=problem,
                defaults={
                    'order': item.get('order', index),
                    'category': item.get('category', pattern_name or ''),
                },
            )
            if problem_created:
                totals['problems_added'] += 1
                self.stdout.write(f'  Added global problem: {problem.title}')
            else:
                totals['problems_skipped'] += 1
                self.stdout.write(f'  Reused global problem: {problem.title}')
            if sheet_problem_created:
                totals['links_added'] += 1
                added_in_sheet += 1
                self.stdout.write(f'  Linked to sheet: {problem.title}')
            else:
                totals['links_skipped'] += 1
                self.stdout.write(f'  Skipped existing sheet link: {problem.title}')

        sheet.total_problems = sheet.problems.count()
        sheet.save(update_fields=['total_problems'])
        self.stdout.write(f'  {added_in_sheet} sheet problems linked; {sheet.total_problems} total.')
