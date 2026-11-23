"""Push companies that already have a NIT into the Neurana fiscal master.

Not scheduled. Run it by hand when the master should catch up with companies
created before registration existed. A failed call does not change the company.
"""
import logging

from django.core.management.base import BaseCommand

from platform.features.company.tenant.company.application.neurana_customer import (
    register_company_customer,
)
from platform.features.company.tenant.company.models import Company

logger = logging.getLogger('app.company')


class Command(BaseCommand):
    help = 'Register existing companies that already have a NIT in Neurana. Not run automatically.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List companies with a NIT without calling Neurana.',
        )

    def handle(self, *args, **options):
        companies = (
            Company.objects
            .exclude(nit='')
            .exclude(nit__isnull=True)
            .order_by('name')
        )
        dry_run = bool(options.get('dry_run'))
        count = 0
        for company in companies.iterator():
            count += 1
            self.stdout.write(f'{company.id} {company.nit} {company.name}')
            if dry_run:
                continue
            register_company_customer(company.id)
        self.stdout.write(self.style.SUCCESS(f'{count} companies with a NIT'))
