from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support_incident', '0004_alter_incident_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='incident',
            name='kind',
            field=models.CharField(
                choices=[('incident', 'Incidencia'), ('suggestion', 'Sugerencia')],
                default='incident',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='incident',
            name='attachments',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddIndex(
            model_name='incident',
            index=models.Index(fields=['kind'], name='incidents_kind_idx'),
        ),
    ]
