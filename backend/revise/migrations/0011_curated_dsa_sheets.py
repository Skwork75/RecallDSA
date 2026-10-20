from django.db import migrations, models
import django.db.models.deletion


def populate_sheet_metadata(apps, schema_editor):
    DSASheet = apps.get_model('revise', 'DSASheet')
    DSASheetProblem = apps.get_model('revise', 'DSASheetProblem')
    from django.utils.text import slugify

    for sheet in DSASheet.objects.order_by('pk'):
        base_slug = slugify(sheet.title) or f'sheet-{sheet.pk}'
        sheet_slug = base_slug
        suffix = 1
        while DSASheet.objects.filter(slug=sheet_slug).exclude(pk=sheet.pk).exists():
            sheet_slug = f'{base_slug}-{suffix}'
            suffix += 1
        sheet.slug = sheet_slug
        sheet.total_problems = DSASheetProblem.objects.filter(sheet_id=sheet.pk).count()
        sheet.save(update_fields=['slug', 'total_problems'])


class Migration(migrations.Migration):

    dependencies = [
        ('revise', '0010_delete_userproblemprogress_userproblemprogress'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dsasheet',
            old_name='name',
            new_name='title',
        ),
        migrations.AddField(
            model_name='dsasheet',
            name='slug',
            field=models.SlugField(blank=True, db_index=False, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='dsasheet',
            name='author',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='dsasheet',
            name='total_problems',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='dsasheet',
            name='cover_image_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='dsasheet',
            name='is_featured',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='dsasheetproblem',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='dsasheetproblem',
            name='category',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.RunPython(populate_sheet_metadata, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='dsasheet',
            name='slug',
            field=models.SlugField(blank=True, max_length=255, unique=True),
        ),
        migrations.AlterModelOptions(
            name='dsasheetproblem',
            options={'ordering': ['order', 'id']},
        ),
    ]
