from django.core.management.base import BaseCommand

from platform.features.billing.commerce.promotion.application.use_cases import ExpireVouchersUseCase
from platform.features.billing.commerce.promotion.infrastructure.repositories import (
    DjangoPromotionVoucherRepository,
)


class Command(BaseCommand):
    help = 'Mark promotion vouchers as EXPIRED when past redeem_valid_until.'

    def handle(self, *args, **options):
        count = ExpireVouchersUseCase(DjangoPromotionVoucherRepository()).execute()
        self.stdout.write(self.style.SUCCESS(f'Expired {count} promotion voucher(s).'))
