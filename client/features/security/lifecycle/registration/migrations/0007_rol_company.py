from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0006_feature_uuid_pk'),
        ('company', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rol',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='roles',
                to='company.company',
                verbose_name='Empresa',
            ),
        ),
    ]
