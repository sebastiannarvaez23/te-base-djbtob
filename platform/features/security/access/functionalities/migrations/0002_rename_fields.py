from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Align field names with the client-side Feature model:
    - code        → key
    - name        → label
    - remove description
    - add category (was added to model, migration pending)
    """

    dependencies = [
        ('functionalities', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='functionality',
            name='category',
            field=models.CharField(default='features', max_length=50, verbose_name='Categoría'),
        ),
        migrations.RenameField(
            model_name='functionality',
            old_name='code',
            new_name='key',
        ),
        migrations.RenameField(
            model_name='functionality',
            old_name='name',
            new_name='label',
        ),
        migrations.RemoveField(
            model_name='functionality',
            name='description',
        ),
        migrations.AlterModelOptions(
            name='functionality',
            options={
                'ordering': ['module__order', 'key'],
                'verbose_name': 'Funcionalidad',
                'verbose_name_plural': 'Funcionalidades',
                'db_table': 'security_functionalities',
            },
        ),
    ]
