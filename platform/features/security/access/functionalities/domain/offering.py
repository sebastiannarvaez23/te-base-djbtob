"""Commercial pairing for a functionality.

A plan functionality is included in the subscription. A complement is
licensed per company as a renewal or a one-time acquisition.
"""
from __future__ import annotations

OFFERING_PLAN = 'plan'
OFFERING_COMPLEMENT = 'complement'
BILLING_INCLUDED = 'included'
BILLING_RENEWAL = 'renewal'
BILLING_ONE_TIME = 'one_time'

OFFERINGS = (OFFERING_PLAN, OFFERING_COMPLEMENT)
BILLING_MODES = (BILLING_INCLUDED, BILLING_RENEWAL, BILLING_ONE_TIME)


def offering_pairing_ok(offering: str, billing_mode: str) -> bool:
    if offering == OFFERING_PLAN:
        return billing_mode == BILLING_INCLUDED
    if offering == OFFERING_COMPLEMENT:
        return billing_mode in (BILLING_RENEWAL, BILLING_ONE_TIME)
    return False


def apply_commercial(offering: str, billing_mode: str, catalog_service_id):
    """Stored offering, billing mode and Neurana service.

    A complement added to the subscription must name a Neurana catalog
    service. The application layer checks that the service is active.
    A one-time complement does not.
    """
    from core.errors import AppErrorCode, ValidationAppException

    if not offering_pairing_ok(offering, billing_mode):
        raise ValidationAppException(
            AppErrorCode.CMP_OFFERING_MISMATCH,
            override_detail='A plan item is included. A complement is added to the subscription or paid once.',
        )
    if offering != OFFERING_COMPLEMENT:
        return OFFERING_PLAN, BILLING_INCLUDED, None
    if billing_mode == BILLING_ONE_TIME:
        return OFFERING_COMPLEMENT, BILLING_ONE_TIME, None
    if catalog_service_id is None:
        raise ValidationAppException(
            AppErrorCode.CMP_SERVICE_REQUIRED,
            override_detail='A complement added to the subscription needs an active Neurana catalog service that carries the price.',
        )
    return OFFERING_COMPLEMENT, BILLING_RENEWAL, catalog_service_id
