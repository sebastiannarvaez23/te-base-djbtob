from datetime import datetime
from decimal import Decimal

from core.query import QueryFilter, QueryParam


class ChargeListQuery(QueryFilter):
    """Charges are always paginated."""

    ALLOW_UNPAGINATED = False
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    DATE_RANGES = (('from', 'to'),)

    status = QueryParam(
        coerce=str,
        choices=[
            'pending',
            'processing',
            'requires_action',
            'authorized',
            'captured',
            'failed',
            'canceled',
            'refunded',
            'partially_refunded',
            'disputed',
        ],
    )
    method_type = QueryParam(
        coerce=str,
        choices=[
            'card',
            'bank_transfer',
            'pse',
            'wallet',
            'voucher',
            'bnpl',
            'crypto',
            'other',
        ],
    )
    invoice_id = QueryParam(coerce=str, is_uuid=True)
    amount_min = QueryParam(coerce=Decimal)
    amount_max = QueryParam(coerce=Decimal)
    from_dt = QueryParam(coerce=datetime, name='from')
    to_dt = QueryParam(coerce=datetime, name='to')
