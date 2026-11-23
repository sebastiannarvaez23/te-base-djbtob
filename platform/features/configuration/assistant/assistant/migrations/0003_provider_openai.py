from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assistant_settings', '0002_alter_assistantsettings_id'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='assistantsettings',
            name='chk_asst_provider',
        ),
        migrations.AddConstraint(
            model_name='assistantsettings',
            constraint=models.CheckConstraint(
                check=models.Q(('provider__in', ['fake', 'local', 'anthropic', 'openai'])),
                name='chk_asst_provider',
            ),
        ),
    ]
