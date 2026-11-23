"""Seed Parameter rows needed by the onboarding + email-confirmation flow.

Runtime config lives in the Parameter table (per team convention); this
migration makes the flow functional out-of-the-box without requiring a
manual SQL step.

Idempotent via ``get_or_create`` — safe to re-run.
"""

from django.db import migrations


# (code, name, description, data_type, value)
_PARAMETER_TYPES = [
    ('SECURITY', 'Security', 'Authentication and session security settings.'),
    ('ONBOARDING', 'Onboarding', 'Company registration / onboarding flow settings.'),
    ('COMMUNICATION', 'Communication', 'Email and notification-related settings.'),
]


_PARAMETERS = [
    # (code, type_code, name, description, data_type, value)
    (
        'REG_EMAIL_CONFIRM', 'SECURITY',
        'Require email confirm',
        'When true, newly onboarded admins must confirm their email before login.',
        'BOOL', 'false',
    ),
    (
        'EMAIL_CFM_TTL_H', 'SECURITY',
        'Email confirm TTL (hours)',
        'Lifetime of an email-confirmation token in hours.',
        'INT', '24',
    ),
    (
        'EMAIL_CFM_WND_S', 'SECURITY',
        'Email confirm throttle (s)',
        'Minimum seconds between confirmation re-sends for a given user.',
        'INT', '60',
    ),
    (
        'EMAIL_CFM_URL', 'COMMUNICATION',
        'Email confirm URL',
        'Frontend page that POSTs the confirmation token to /auth/confirm-email/.',
        'STRING', 'https://warehouse-anywhere.com/confirm-email',
    ),
    (
        'ONB_REG_TTL_D', 'ONBOARDING',
        'Onboarding TTL (days)',
        'Lifetime of an in-progress onboarding registration in days.',
        'INT', '7',
    ),
    (
        'ONB_TOK_TTL_S', 'ONBOARDING',
        'Onboarding token TTL (s)',
        'Lifetime of an onboarding resume-link token in seconds.',
        'INT', '7200',
    ),
]


def seed(apps, schema_editor):
    ParameterType = apps.get_model('parameter_type', 'ParameterType')
    Parameter = apps.get_model('parameter', 'Parameter')

    type_by_code = {}
    for code, name, description in _PARAMETER_TYPES:
        ptype, _ = ParameterType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'description': description, 'is_active': True},
        )
        type_by_code[code] = ptype

    for code, type_code, name, description, data_type, value in _PARAMETERS:
        Parameter.objects.get_or_create(
            code=code,
            defaults={
                'parameter_type': type_by_code[type_code],
                'name': name,
                'description': description,
                'data_type': data_type,
                'value': value,
                'is_active': True,
            },
        )


def unseed(apps, schema_editor):
    Parameter = apps.get_model('parameter', 'Parameter')
    Parameter.objects.filter(code__in=[p[0] for p in _PARAMETERS]).delete()
    # ParameterTypes are left in place: they may be referenced by other
    # Parameter rows created outside this migration.


class Migration(migrations.Migration):

    dependencies = [
        ('parameter', '0002_alter_parameter_code_alter_parameter_description_and_more'),
        ('parameter_type', '0002_alter_parametertype_code_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
