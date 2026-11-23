from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compliance_policy', '0006_policy_country_draft'),
    ]

    operations = [
        migrations.AddField(
            model_name='policycountry',
            name='change_summary',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Summary of changes vs the previous published version (required on updates).',
            ),
        ),
    ]
