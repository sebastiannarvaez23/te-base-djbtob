import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Consolidate security_features into security_functionalities:
    1. Copy all rows from security_features → security_functionalities (keeping same UUIDs
       so that existing security_rol_features.feature_id values remain valid).
    2. Repoint the security_rol_features FK from security_features to security_functionalities.
    3. Drop the security_features table.
    4. Update Django model state: RolFeature.feature → Functionality, remove Feature model.
    """

    dependencies = [
        ('registration', '0009_rolmodule'),
        ('functionalities', '0002_rename_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        -- 1. Copy rows from security_features into security_functionalities,
                        --    preserving original UUIDs so FK values in rol_features stay valid.
                        INSERT INTO security_functionalities (id, key, label, category, module_id, is_active, created_at, updated_at)
                        SELECT
                            f.id,
                            f.key,
                            f.label,
                            f.category,
                            m.id,
                            f.is_active,
                            NOW(),
                            NOW()
                        FROM security_features f
                        JOIN security_modules m ON m.code = f.module
                        ON CONFLICT (key) DO UPDATE SET
                            label     = EXCLUDED.label,
                            category  = EXCLUDED.category,
                            is_active = EXCLUDED.is_active,
                            module_id = EXCLUDED.module_id;

                        -- 2. Remove old FK constraints from security_rol_features
                        ALTER TABLE security_rol_features
                            DROP CONSTRAINT IF EXISTS security_rol_features_feature_id_fkey;
                        ALTER TABLE security_rol_features
                            DROP CONSTRAINT IF EXISTS security_rol_features_rol_id_feature_id_uniq;

                        -- 3. Add new FK pointing to security_functionalities
                        --    (feature_id values already reference the correct rows because we kept UUIDs)
                        ALTER TABLE security_rol_features
                            ADD CONSTRAINT security_rol_features_feature_id_fkey
                            FOREIGN KEY (feature_id) REFERENCES security_functionalities(id) ON DELETE CASCADE;
                        ALTER TABLE security_rol_features
                            ADD CONSTRAINT security_rol_features_rol_id_feature_id_uniq
                            UNIQUE (rol_id, feature_id);

                        -- 4. Drop security_features (no longer needed)
                        DROP TABLE security_features;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='rolfeature',
                    name='feature',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='rol_features',
                        to='functionalities.functionality',
                    ),
                ),
                migrations.DeleteModel(name='Feature'),
            ],
        ),
    ]
