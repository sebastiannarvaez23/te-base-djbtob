from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('platform_users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminuser',
            name='telephone',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Teléfono'),
        ),
        migrations.AddField(
            model_name='adminuser',
            name='picture',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Foto de perfil'),
        ),
    ]
