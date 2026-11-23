from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('email_template', '0002_remove_emailtemplate_bcc_remove_emailtemplate_cc_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='mock_data',
            field=models.JSONField(blank=True, default=dict, help_text='JSON with sample values for template variables, used for preview emulation.', verbose_name='Mock data'),
        ),
    ]
