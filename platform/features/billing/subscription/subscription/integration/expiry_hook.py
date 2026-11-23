"""
Subscription-expiry hook handler.

Registered with the access-layer hook (``core.access.hooks``) in this app's
``ready()``. When the middleware loads an active acquisition whose vigencia has
passed, it calls here and we enqueue the matching Celery task — a pending
downgrade is materialised, otherwise (auto_renew) the plan is renewed, else
the period is marked expired.

Throttled so it fires at most once per ~10 min until handled, and it only
*enqueues*: the heavy work (charge + PDF render, or the expire write) stays
OUT of the request path.
"""
_THROTTLE_SECONDS = 600


def on_subscription_expiry(company_id, cs) -> None:
    from django.utils import timezone
    if cs.end_date > timezone.now():
        return

    pending = getattr(cs, 'pending_subscription_id', None)
    auto_renew = getattr(cs, 'auto_renew', False)

    from django.core.cache import caches
    if not caches['access'].add(f'sub:{company_id}:expiry_enqueued', '1', timeout=_THROTTLE_SECONDS):
        return

    if pending:
        from ..tasks.downgrades import apply_pending_downgrade_for_company
        apply_pending_downgrade_for_company.delay(str(company_id))
    elif auto_renew:
        from ..tasks.renewals import renew_subscription_for_company
        renew_subscription_for_company.delay(str(company_id))
    else:
        from ..tasks.expire import expire_subscription_for_company
        expire_subscription_for_company.delay(str(company_id))
