from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0011_alter_rolfeature_id_alter_rolmodule_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
