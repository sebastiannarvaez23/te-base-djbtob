"""Ensure tenant-close runtime parameters exist.

Does not overwrite an existing value — operators set them from admin.
"""

from django.core.management.base import BaseCommand

from platform.features.company.tenant.company.domain.lifecycle import (
    CLOSE_GRACE_PARAM,
    DEFAULT_CLOSE_GRACE_DAYS,
)
from platform.features.configuration.parameters.parameter.models import Parameter
from platform.features.configuration.parameters.parameter_type.models import ParameterType


_TYPE = (
    'TENANT_LIFE',
    'Tenant lifecycle',
    'Company close, grace window and purge settings.',
)

_PARAMS = (
        {
        'code': CLOSE_GRACE_PARAM,
        'name': 'Dias para dada de baja empresa',
        'description': (
            'Dias que una empresa tiene de ventana desde el momento en que '
            'decidio dar de baja la empresa'
        ),
        'data_type': 'INT',
        'value': str(DEFAULT_CLOSE_GRACE_DAYS),
    },
)


class Command(BaseCommand):
    help = 'Ensure tenant-close runtime parameters exist (default grace 30 days).'

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
