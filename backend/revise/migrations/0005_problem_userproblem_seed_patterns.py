from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


PATTERNS = [
    'BST', 'Binary Search', 'Sliding Window', 'Two Pointers', 'Linked List',
    'Stack', 'Queue', 'Heap', 'Backtracking', 'Graph', 'Dynamic Programming',
    'Greedy', 'Trie',
]


def seed_patterns(apps, schema_editor):
    Pattern = apps.get_model('revise', 'Pattern')
    for pattern_name in PATTERNS:
        Pattern.objects.get_or_create(p_name=pattern_name)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('revise', '0003_pattern'),
    ]

    operations = [
        migrations.CreateModel(
            name='Problem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('leetcode_id', models.PositiveIntegerField(unique=True)),
                ('link', models.URLField()),
                ('difficulty', models.CharField(choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')], max_length=10)),
                ('pattern', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='problems', to='revise.pattern')),
            ],
        ),
        migrations.CreateModel(
            name='UserProblem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('solved', models.BooleanField(default=False)),
                ('confidence', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('last_reviewed', models.DateTimeField(blank=True, null=True)),
                ('next_revision', models.DateTimeField(blank=True, null=True)),
                ('revision_count', models.PositiveIntegerField(default=0)),
                ('problem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_progress', to='revise.problem')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='problem_progress', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='userproblem',
            constraint=models.UniqueConstraint(fields=('user', 'problem'), name='unique_user_problem'),
        ),
        migrations.RunPython(seed_patterns, migrations.RunPython.noop),
    ]