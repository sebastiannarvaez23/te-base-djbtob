from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0010_alter_module_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='module',
            name='is_sidebar',
            field=models.BooleanField(
                default=True,
                verbose_name='Menú del sidebar',
            ),
        ),
    ]
