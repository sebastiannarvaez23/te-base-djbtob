import django.db.models.functions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_filters', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='modulefilter',
            name='mflt_user_module_name_uniq',
        ),
        migrations.AddConstraint(
            model_name='modulefilter',
            constraint=models.UniqueConstraint(
                django.db.models.functions.Lower('name'),
                'user_id',
                'module_key',
                name='mflt_user_module_name_ci',
            ),
        ),
    ]
