from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sections', '0002_seed_sections'),
    ]

    operations = [
        migrations.AddField(
            model_name='section',
            name='icon',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='Icono',
            ),
        ),
    ]
