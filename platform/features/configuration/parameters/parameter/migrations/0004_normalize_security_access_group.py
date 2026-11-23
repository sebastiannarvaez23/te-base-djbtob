"""Normalize the Parameter taxonomy for the security/access flow.

Two changes:
  1. Consolidate REG_EMAIL_CONFIRM, EMAIL_CFM_TTL_H, EMAIL_CFM_WND_S,
     ONB_REG_TTL_D and ONB_TOK_TTL_S under a single SECURITY_ACCESS group
     so the admin UI shows them together and so future security-related
     parameters have an obvious home.

  2. Remove EMAIL_CFM_URL from the Parameter table — it now lives in the
     ``EMAIL_CFM_URL`` env var (per the team rule for per-deployment
     config; same precedent as ``DOMAIN_PLATFORM``).

Idempotent: re-running is a no-op on a converged DB.
"""

from django.db import migrations


_SECURITY_ACCESS = (
    'SECURITY_ACCESS',
    'Security & access',
    'Authentication, session, and access-control runtime settings.',
)

_RELOCATED_CODES = [
    'REG_EMAIL_CONFIRM',
    'EMAIL_CFM_TTL_H',
    'EMAIL_CFM_WND_S',
    'ONB_REG_TTL_D',
    'ONB_TOK_TTL_S',
]

_REMOVED_CODES = ['EMAIL_CFM_URL']


def normalize(apps, schema_editor):
    ParameterType = apps.get_model('parameter_type', 'ParameterType')
    Parameter = apps.get_model('parameter', 'Parameter')

    code, name, description = _SECURITY_ACCESS
    sa_type, _ = ParameterType.objects.get_or_create(
        code=code,
        defaults={'name': name, 'description': description, 'is_active': True},
    )

    Parameter.objects.filter(code__in=_RELOCATED_CODES).update(parameter_type=sa_type)
    Parameter.objects.filter(code__in=_REMOVED_CODES).delete()


def revert(apps, schema_editor):
    # No-op: we don't reconstruct the prior ad-hoc taxonomy. Re-running
    # 0003 (forward) would re-seed EMAIL_CFM_URL if a rollback is ever
    # required.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('parameter', '0003_seed_onboarding_email_params'),
        ('parameter_type', '0002_alter_parametertype_code_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize, revert),
    ]
