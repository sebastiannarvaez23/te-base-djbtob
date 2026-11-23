from django.db import migrations


class Migration(migrations.Migration):
    """
    Convert security_features.id from integer to UUID.
    Also updates the FK in security_rol_features.feature_id.
    Since this table is rebuilt by sync_features, all data is cleared first.
    """

    dependencies = [
        ('registration', '0005_rol_description_is_active'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Drop FK and unique constraints that reference feature_id
                ALTER TABLE security_rol_features
                    DROP CONSTRAINT IF EXISTS "security_rol_feature_feature_id_961f41fd_fk_security_";
                ALTER TABLE security_rol_features
                    DROP CONSTRAINT IF EXISTS security_rol_features_rol_id_feature_id_32d83495_uniq;

                -- Clear data (rebuilt by sync_features)
                DELETE FROM security_rol_features;
                DELETE FROM security_features;

                -- Convert feature.id: drop PK, add uuid column, drop old, rename, add PK
                ALTER TABLE security_features DROP CONSTRAINT security_features_pkey;
                ALTER TABLE security_features ADD COLUMN id_new uuid NOT NULL DEFAULT gen_random_uuid();
                ALTER TABLE security_features DROP COLUMN id;
                ALTER TABLE security_features RENAME COLUMN id_new TO id;
                ALTER TABLE security_features ADD PRIMARY KEY (id);

                -- Convert feature_id column in rol_features to UUID
                ALTER TABLE security_rol_features DROP COLUMN feature_id;
                ALTER TABLE security_rol_features ADD COLUMN feature_id uuid;
                ALTER TABLE security_rol_features
                    ADD CONSTRAINT security_rol_features_feature_id_fkey
                    FOREIGN KEY (feature_id) REFERENCES security_features(id) ON DELETE CASCADE;
                ALTER TABLE security_rol_features
                    ADD CONSTRAINT security_rol_features_rol_id_feature_id_uniq
                    UNIQUE (rol_id, feature_id);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
