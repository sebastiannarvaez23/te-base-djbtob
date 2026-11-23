"""Ensure admin-catalog security parameters exist (schema public).

Does not overwrite an existing value — operators toggle them from admin UI.
"""

from django.core.management.base import BaseCommand

from platform.features.configuration.admin_parameters.admin_parameter.models import (
    AdminParameter,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.models import (
    AdminParameterType,
)

_TYPE = (
    'SECURITY',
    'Security and access',
    'Authentication session and access control for the admin portal',
)

_PARAMS = (
    {
        'code': 'DOUBLE_FA_AUTH',
        'name': 'Two factor authentication',
        'description': 'Require email OTP for unrecognized admin devices',
        'data_type': 'BOOL',
        'value': 'false',
    },
    {
        'code': 'HISTORY_PASS',
        'name': 'Password history',
        'description': 'How many previous passwords cannot be reused',
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'PASSWORD_EXPIRED',
        'name': 'Password expiry days',
        'description': 'Days until an admin password expires and must change',
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'MAX_LOGIN_RETRIES',
        'name': 'Max login retries',
        'description': 'Consecutive failed password attempts before lockout',
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'TIME_INACTIVITY',
        'name': 'Inactivity timeout',
        'description': 'Minutes without activity before an admin session ends',
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'MULTI_SESSIONS',
        'name': 'Multiple active sessions',
        'description': 'Allow more than one live admin session at a time',
        'data_type': 'BOOL',
        'value': 'true',
    },
    {
        'code': 'TOKEN_DURATION',
        'name': 'Access token duration',
        'description': 'Admin access token lifetime in minutes',
        'data_type': 'INT',
        'value': '1440',
    },
    {
        'code': 'REF_TOKEN_DURATION',
        'name': 'Refresh token duration',
        'description': 'Admin refresh token lifetime in days',
        'data_type': 'INT',
        'value': '14',
    },
)


class Command(BaseCommand):
    help = 'Ensure admin security parameters exist (defaults leave most policies off).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        code, name, description = _TYPE
        if dry:
            for spec in _PARAMS:
                exists = AdminParameter.objects.filter(code=spec['code']).exists()
                action = 'exists' if exists else 'would create'
                self.stdout.write(f'{spec["code"]}: {action}')
            return

        ptype, _ = AdminParameterType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'description': description, 'is_active': True},
        )
        for spec in _PARAMS:
            _, created = AdminParameter.objects.get_or_create(
                code=spec['code'],
                defaults={
                    'parameter_type': ptype,
                    'name': spec['name'],
                    'description': spec['description'],
                    'data_type': spec['data_type'],
                    'value': spec['value'],
                    'is_active': True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'Created {spec["code"]}={spec["value"]}',
                ))
            else:
                self.stdout.write(f'{spec["code"]} already present — left unchanged.')
