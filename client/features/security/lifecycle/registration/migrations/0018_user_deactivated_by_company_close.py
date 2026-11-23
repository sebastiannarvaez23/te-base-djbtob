from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0017_user_document_number_user_document_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='deactivated_by_company_close',
            field=models.BooleanField(default=False),
        ),
    ]
