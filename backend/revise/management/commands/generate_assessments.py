from django.core.management.base import BaseCommand

from revise.services import generate_assessments_for_active_users


class Command(BaseCommand):
    help = 'Generate this week’s assessment for every active user.'

    def handle(self, *args, **options):
        assessments = generate_assessments_for_active_users()
        self.stdout.write(self.style.SUCCESS(
            f'Generated or reused {len(assessments)} weekly assessments.'
        ))
