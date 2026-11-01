from django.conf import settings
from django.db import migrations, models


def backfill_progress_from_legacy_rows(apps, schema_editor):
    UserProblem = apps.get_model('revise', 'UserProblem')
    UserProblemProgress = apps.get_model('revise', 'UserProblemProgress')
    database = schema_editor.connection.alias

    for legacy in UserProblem.objects.using(database).iterator():
        confidence = legacy.confidence or 0
        if not 0 <= confidence <= 5:
            confidence = 0
        source = 'leetcode_sync' if legacy.source == 'import' else 'manual'
        UserProblemProgress.objects.using(database).get_or_create(
            user_id=legacy.user_id,
            problem_id=legacy.problem_id,
            defaults={
                'is_tracked': True,
                'source': source,
                'easiness_factor': 2.5,
                'interval': legacy.interval,
                'repetition_number': legacy.revision_count,
                'next_review_date': legacy.next_revision,
                'confidence_rating': confidence,
                'last_reviewed_at': legacy.last_reviewed,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('revise', '0013_usersettings'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='userproblemprogress',
            name='source',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual'),
                    ('leetcode_sync', 'LeetCode sync'),
                    ('sheet', 'DSA sheet'),
                    ('image_import', 'Image import'),
                ],
                default='manual',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='userproblemprogress',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(backfill_progress_from_legacy_rows, migrations.RunPython.noop),
    ]
