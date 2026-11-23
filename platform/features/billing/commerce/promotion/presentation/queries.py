from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class VoucherQuery(QueryFilter):
    """Admin list filters for promotion vouchers (page / page_size built-in)."""

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    status = QueryParam(
        coerce=str,
        choices=['ACTIVE', 'REDEEMED', 'EXPIRED', 'REVOKED'],
    )
    voucher_type = QueryParam(coerce=str, choices=['GIFT', 'DISCOUNT'])
    scope = QueryParam(coerce=str, choices=['COMPANY', 'OPEN', 'FIRST_TAKE'])
    origin = QueryParam(coerce=str, choices=['ADMIN', 'PUBLIC_PURCHASE'])
    company_id = QueryParam(coerce=str, is_uuid=True)
    serial = QueryParam(coerce=str, max_length=64, pattern=PATTERN_TEXT)
    company = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)  # company name contains
    search = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)   # serial | company | plan name


class RedemptionListQuery(QueryFilter):
    company_id = QueryParam(coerce=str, is_uuid=True)
    voucher_id = QueryParam(coerce=str, is_uuid=True)


class TenantBenefitsQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    status = QueryParam(coerce=str, choices=['ACTIVE', 'COMPLETED', 'CANCELLED'])
