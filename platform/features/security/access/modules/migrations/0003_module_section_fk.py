import uuid
from django.db import migrations, models
import django.db.models.deletion


def populate_section_fk(apps, schema_editor):
    Module = apps.get_model('modules', 'Module')
    Section = apps.get_model('sections', 'Section')
    for module in Module.objects.all():
        section = Section.objects.filter(code=module.section).first()
        if section:
            module.section_fk = section
            module.save(update_fields=['section_fk'])


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0002_seed_modules'),
        ('sections', '0002_seed_sections'),
    ]

    operations = [
        migrations.AddField(
            model_name='module',
            name='section_fk',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='modules',
                to='sections.section',
                verbose_name='Sección',
            ),
        ),
        migrations.RunPython(populate_section_fk, reverse_code=migrations.RunPython.noop),
    ]
