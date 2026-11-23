"""Pure validation of voucher-creation input (no Django)."""

from decimal import Decimal

from core.errors import AppErrorCode, AppException


def validate_create_input(data) -> None:
    if data.redeem_valid_until <= data.redeem_valid_from:
        raise AppException(AppErrorCode.PROMO_INVALID_INPUT)
    if not data.subscription_ids:
        raise AppException(AppErrorCode.PROMO_INVALID_INPUT)
    if data.voucher_type == 'GIFT':
        if not data.benefit_months or data.benefit_months < 1 or data.benefit_months > 36:
            raise AppException(AppErrorCode.PROMO_INVALID_INPUT)
    elif data.voucher_type == 'DISCOUNT':
        pct = Decimal(str(data.discount_percent or 0))
        if pct <= 0 or pct > 100:
            raise AppException(AppErrorCode.PROMO_INVALID_INPUT)
        if data.discount_duration_months < 1:
            raise AppException(AppErrorCode.PROMO_INVALID_INPUT)
    else:
        raise AppException(AppErrorCode.PROMO_INCOMPATIBLE)
    if data.scope == 'COMPANY' and not data.company_id:
        raise AppException(AppErrorCode.PROMO_INVALID_INPUT)
    if data.scope in ('OPEN', 'FIRST_TAKE') and data.company_id:
        raise AppException(AppErrorCode.PROMO_INVALID_INPUT)
