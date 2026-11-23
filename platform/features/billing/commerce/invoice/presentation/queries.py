from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class InvoiceQuery(QueryFilter):
    invoice_number = QueryParam(coerce=str, max_length=50, pattern=PATTERN_CODE)
    company        = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    nit            = QueryParam(coerce=str, max_length=40, pattern=PATTERN_CODE)
    subscription   = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status         = QueryParam(
        coerce=str,
        choices=['pending', 'paid', 'cancelled', 'overdue'],
    )


class CompanyInvoiceQuery(QueryFilter):
    """Per-company invoice list — intentionally unpaginated (bounded by company)."""

    ALLOW_UNPAGINATED = True
    status = QueryParam(
        coerce=str,
        choices=['pending', 'paid', 'cancelled', 'overdue'],
    )
