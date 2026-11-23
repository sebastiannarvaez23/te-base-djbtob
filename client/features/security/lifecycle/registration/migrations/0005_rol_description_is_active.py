from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0004_feature_rolfeature'),
    ]

    operations = [
        migrations.AddField(
            model_name='rol',
            name='description',
            field=models.CharField(blank=True, default='', max_length=500, verbose_name='Descripción'),
        ),
        migrations.AddField(
            model_name='rol',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Activo'),
        ),
    ]
