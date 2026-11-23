import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE company_domain ADD COLUMN new_id UUID;
                        UPDATE company_domain SET new_id = gen_random_uuid();
                        ALTER TABLE company_domain ALTER COLUMN new_id SET NOT NULL;
                        ALTER TABLE company_domain DROP CONSTRAINT company_domain_pkey CASCADE;
                        ALTER TABLE company_domain DROP COLUMN id;
                        ALTER TABLE company_domain RENAME COLUMN new_id TO id;
                        ALTER TABLE company_domain ADD PRIMARY KEY (id);
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='domain',
                    name='id',
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
        ),
    ]
