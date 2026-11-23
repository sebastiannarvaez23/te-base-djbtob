from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('platform_roles', '0004_admin_catalog'),
    ]

    operations = [
        migrations.AddField(
            model_name='adminsection',
            name='icon',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='Icono',
            ),
        ),
        migrations.AddField(
            model_name='adminmodule',
            name='is_sidebar',
            field=models.BooleanField(
                default=True,
                verbose_name='Menú del sidebar',
            ),
        ),
    ]
