from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logging_config', '0002_ensure_logconfiguration_table'),
    ]

    operations = [
        migrations.AlterField(
            model_name='logconfiguration',
            name='log_type',
            field=models.CharField(
                choices=[
                    ('audit', 'Auditoría'),
                    ('operations', 'Operaciones'),
                    ('integration', 'Integración'),
                    ('security', 'Seguridad'),
                    ('errors', 'Errores'),
                    ('performance', 'Performance'),
                    ('system', 'Sistema'),
                    ('tenant', 'Logs por empresa'),
                ],
                max_length=50,
                unique=True,
                verbose_name='Tipo de log',
            ),
        ),
    ]
