from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entity_grants', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entitygrant',
            name='entity_type',
            field=models.CharField(max_length=32),
        ),
    ]
