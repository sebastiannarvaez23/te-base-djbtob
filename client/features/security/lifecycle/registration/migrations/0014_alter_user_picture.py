from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0013_backfill_email_verified_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='picture',
            field=models.ImageField(blank=True, max_length=500, null=True, upload_to='perfil/', verbose_name='Foto de perfil'),
        ),
    ]
