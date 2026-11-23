from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0018_user_deactivated_by_company_close'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='birth_date',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de nacimiento'),
        ),
    ]
