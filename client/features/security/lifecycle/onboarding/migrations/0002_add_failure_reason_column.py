"""Add the ``failure_reason`` column to ``onboarding_company_registrations``.

The 0001_initial migration declares this field, but in some environments the
table was created from an earlier version of that migration where the column
was absent. Since 0001 is marked as applied, Django never re-runs it; the
model expects the column and any SELECT fails with `UndefinedColumn`.

Using ``ADD COLUMN IF NOT EXISTS`` keeps this safe to run in environments
that *do* already have the column (CI, fresh installs, etc.).
"""

from django.db import migrations


SQL = """
    ALTER TABLE onboarding_company_registrations
    ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(500) NOT NULL DEFAULT '';
"""

REVERSE_SQL = """
    ALTER TABLE onboarding_company_registrations
    DROP COLUMN IF EXISTS failure_reason;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(SQL, reverse_sql=REVERSE_SQL),
    ]
