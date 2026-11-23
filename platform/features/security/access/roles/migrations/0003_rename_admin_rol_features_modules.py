from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Rename join tables to mirror client naming (rol_features / rol_modules).

    Catalog stays ``security_functionalities``; grants use ``features`` vocabulary.
    Schema-only — no data inserts or updates.
    """

    dependencies = [
        ('platform_roles', '0002_admin_role_features_modules'),
    ]

    operations = [
        migrations.AlterModelTable(name='adminrolefeature', table='admin_rol_features'),
        migrations.AlterModelTable(name='adminrolemodule', table='admin_rol_modules'),
        migrations.RenameField(model_name='adminrolefeature', old_name='role', new_name='rol'),
        migrations.RenameField(model_name='adminrolemodule', old_name='role', new_name='rol'),
        migrations.AlterField(
            model_name='adminrolefeature',
            name='feature',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='admin_rol_features',
                to='functionalities.functionality',
            ),
        ),
        migrations.AlterField(
            model_name='adminrolefeature',
            name='rol',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='rol_features',
                to='platform_roles.adminrole',
            ),
        ),
        migrations.AlterField(
            model_name='adminrolemodule',
            name='rol',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='rol_modules',
                to='platform_roles.adminrole',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='adminrolefeature',
            unique_together={('rol', 'feature')},
        ),
        migrations.AlterUniqueTogether(
            name='adminrolemodule',
            unique_together={('rol', 'module_code')},
        ),
    ]
