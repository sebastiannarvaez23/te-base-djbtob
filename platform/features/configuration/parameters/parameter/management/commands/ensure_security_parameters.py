"""Ensure SECURITY_ACCESS runtime parameters exist.

Does not overwrite an existing value — operators toggle them from admin.
"""

from django.core.management.base import BaseCommand

from platform.features.configuration.parameters.parameter.models import Parameter
from platform.features.configuration.parameters.parameter_type.models import ParameterType


_TYPE = (
    'SECURITY_ACCESS',
    'Security & access',
    'Authentication, session, and access-control runtime settings.',
)

_PARAMS = (
    {
        'code': 'DOUBLE_FA_AUTH',
        'name': 'Two-factor authentication',
        'description': 'When true, login from an unrecognized device requires an email OTP.',
        'data_type': 'BOOL',
        'value': 'false',
    },
    {
        'code': 'HISTORY_PASS',
        'name': 'Password history',
        'description': 'How many previous passwords cannot be reused. 0 disables the check.',
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'PASSWORD_EXPIRED',
        'name': 'Password expiry days',
        'description': 'Days until a password expires and must be changed. 0 disables expiry.',
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'MAX_LOGIN_RETRIES',
        'name': 'Max login retries',
        'description': (
            'Maximum consecutive failed password attempts before login is '
            'temporarily locked. 0 disables the check.'
        ),
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'TIME_INACTIVITY',
        'name': 'Inactivity timeout',
        'description': (
            'Minutes without activity before a company user session ends. '
            '0 disables the check.'
        ),
        'data_type': 'INT',
        'value': '0',
    },
    {
        'code': 'MULTI_SESSIONS',
        'name': 'Multiple active sessions',
        'description': (
            'When true, a company user may hold more than one live session. '
            'When false or inactive, login is rejected if a session already exists.'
        ),
        'data_type': 'BOOL',
        'value': 'true',
    },
)


class Command(BaseCommand):
    help = 'Ensure SECURITY_ACCESS runtime parameters exist (defaults leave policy off).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        code, name, description = _TYPE
        if dry:
            for spec in _PARAMS:
                exists = Parameter.objects.filter(code=spec['code']).exists()
                action = 'exists' if exists else 'would create'
                self.stdout.write(f'{spec["code"]}: {action}')
            return

        ptype, _ = ParameterType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'description': description, 'is_active': True},
        )
        for spec in _PARAMS:
            _, created = Parameter.objects.get_or_create(
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
