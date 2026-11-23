from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0003_alter_fieldmapping_id_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integrationapplicationscope',
            name='scope',
            field=models.CharField(max_length=100),
        ),
    ]
