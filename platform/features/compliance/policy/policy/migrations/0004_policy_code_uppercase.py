# Structural: uppercase policy codes before enforcing CHECK constraint.

from django.db import migrations, models


def uppercase_policy_codes(apps, schema_editor):
    """Backfill estructural imprescindible para el CheckConstraint de mayúsculas."""
    Policy = apps.get_model('compliance_policy', 'Policy')
    for policy in Policy.objects.all().iterator():
        upper = (policy.code or '').strip().upper()
        if policy.code != upper:
            policy.code = upper
            policy.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('compliance_policy', '0003_policy_locale_versions'),
    ]

    operations = [
        migrations.RunPython(uppercase_policy_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='policy',
            name='code',
            field=models.CharField(
                help_text='Uppercase kebab-case slug (e.g. DATA-PROCESSING). Used in MinIO object keys.',
                max_length=80,
                unique=True,
            ),
        ),
        migrations.AddConstraint(
            model_name='policy',
            constraint=models.CheckConstraint(
                check=models.Q(code__regex=r'^[A-Z0-9]+(?:-[A-Z0-9]+)*$'),
                name='chk_compliance_policy_code_upper',
            ),
        ),
    ]
