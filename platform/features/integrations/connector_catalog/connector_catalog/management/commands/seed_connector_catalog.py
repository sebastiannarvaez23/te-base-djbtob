from django.core.management.base import BaseCommand

from platform.features.integrations.connector_catalog.connector_catalog.domain.schemas import CreateConnectorDefinitionSchema
from platform.features.integrations.connector_catalog.connector_catalog.infrastructure.repositories import (
    DjangoConnectorCatalogRepository,
)
from platform.features.integrations.connector_catalog.connector_catalog.application.use_cases import (
    CreateConnectorDefinitionUseCase,
)


DEFAULT_CONNECTORS = [
    {
        'key': 'sap',
        'kind': 'ERP',
        'name': 'SAP',
        'description': 'SAP ERP connector (batch orders sync).',
        'version': '1.0',
        'capabilities': ['order.pull', 'order.push'],
        'config_schema': {
            'type': 'object',
            'required': ['base_url'],
            'properties': {
                'base_url': {'type': 'string', 'title': 'Base URL'},
                'company_code': {'type': 'string', 'title': 'Company code'},
            },
        },
    },
    {
        'key': 'siesa',
        'kind': 'ERP',
        'name': 'SIESA',
        'description': 'SIESA ERP connector (batch orders sync).',
        'version': '1.0',
        'capabilities': ['order.pull', 'order.push'],
        'config_schema': {
            'type': 'object',
            'required': ['base_url'],
            'properties': {
                'base_url': {'type': 'string', 'title': 'Base URL'},
                'company_code': {'type': 'string', 'title': 'Company code'},
            },
        },
    },
    {
        'key': 'webhook-inbound',
        'kind': 'APP',
        'name': 'Webhook inbound',
        'description': 'Inbound webhook for client applications.',
        'version': '1.0',
        'capabilities': ['order.pull'],
        'config_schema': {
            'type': 'object',
            'properties': {
                'webhook_path': {'type': 'string', 'title': 'Webhook path'},
            },
        },
    },
]


class Command(BaseCommand):
    help = 'Seed integration connector catalog (SAP, SIESA, webhook-inbound).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        repo = DjangoConnectorCatalogRepository()
        create_uc = CreateConnectorDefinitionUseCase(repo)
        created = 0
        skipped = 0

        for item in DEFAULT_CONNECTORS:
            if repo.get_by_key(item['key']):
                skipped += 1
                self.stdout.write(f"skip {item['key']} (exists)")
                continue
            if options['dry_run']:
                self.stdout.write(f"would create {item['key']}")
                created += 1
                continue
            schema = CreateConnectorDefinitionSchema(**item)
            create_uc.execute(schema)
            created += 1
            self.stdout.write(self.style.SUCCESS(f"created {item['key']}"))

        self.stdout.write(self.style.SUCCESS(f'done: created={created} skipped={skipped}'))
