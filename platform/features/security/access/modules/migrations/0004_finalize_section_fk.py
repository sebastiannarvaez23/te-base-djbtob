from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0003_module_section_fk'),
        ('sections', '0002_seed_sections'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='module',
            name='section',
        ),
        migrations.AlterField(
            model_name='module',
            name='section_fk',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='modules',
                to='sections.section',
                verbose_name='Sección',
            ),
        ),
        migrations.RenameField(
            model_name='module',
            old_name='section_fk',
            new_name='section',
        ),
    ]
