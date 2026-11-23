"""Idempotent seed of ISO currencies and country–currency links.

Does not create countries — only links when the country already exists
in ``geography_location``.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from platform.features.geography.currency.currency.domain.schemas import (
    CreateCountryCurrencySchema,
    UpsertCurrencySeedSchema,
)
from platform.features.geography.currency.currency.infrastructure.repositories import (
    DjangoCurrencyRepository,
)

#: Extensible seed list — primary focus USD + COP.
DEFAULT_CURRENCIES = (
    UpsertCurrencySeedSchema(code='USD', name='US Dollar', decimal_places=2),
    UpsertCurrencySeedSchema(code='COP', name='Colombian Peso', decimal_places=2),
)

#: country_code → [(currency_code, is_default), ...]
DEFAULT_COUNTRY_LINKS = {
    'CO': (('COP', True), ('USD', False)),
    'US': (('USD', True),),
}


class Command(BaseCommand):
    help = (
        'Upsert USD/COP (and country links for CO/US when those countries exist). '
        'Idempotent; safe to re-run.'
    )

    def handle(self, *args, **options):
        repo = DjangoCurrencyRepository()
        created_currencies = 0
        updated_currencies = 0
        linked = 0
        skipped_countries: list[str] = []

        with transaction.atomic():
            currency_ids: dict[str, object] = {}
            for seed in DEFAULT_CURRENCIES:
                row, created = repo.upsert_currency_by_code(seed)
                currency_ids[row.code] = row.id
                if created:
                    created_currencies += 1
                else:
                    updated_currencies += 1

            for country_code, links in DEFAULT_COUNTRY_LINKS.items():
                country_id = repo.get_country_id_by_code(country_code)
                if country_id is None:
                    skipped_countries.append(country_code)
                    continue
                existing = {
                    item.currency_code: item
                    for item in repo.list_country_currencies(country_id=country_id)
                }
                for currency_code, is_default in links:
                    currency_id = currency_ids.get(currency_code)
                    if currency_id is None:
                        continue
                    if currency_code in existing:
                        link = existing[currency_code]
                        if is_default and not link.is_default:
                            from platform.features.geography.currency.currency.domain.schemas import (
                                UpdateCountryCurrencySchema,
                            )
                            repo.update_country_currency(
                                link.id,
                                UpdateCountryCurrencySchema(is_default=True, is_active=True),
                            )
                        continue
                    repo.create_country_currency(CreateCountryCurrencySchema(
                        country_id=country_id,
                        currency_id=currency_id,
                        is_default=is_default,
                        is_active=True,
                    ))
                    linked += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Currencies created={created_currencies} updated={updated_currencies}; '
                f'links created={linked}.'
            ),
        )
        if skipped_countries:
            self.stdout.write(
                self.style.WARNING(
                    'Skipped country links (country missing): '
                    + ', '.join(skipped_countries),
                ),
            )
