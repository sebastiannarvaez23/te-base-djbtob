"""
Access-layer hooks (dependency inversion).

The subscription middleware needs to react when a company's vigencia has
passed — but ``core/access`` must not depend on the billing *tasks*. So
feature apps register a handler here at startup (see
``subscription/apps.py``); ``core/access`` only knows the handler's shape:
``handler(company_id: str, cs) -> None``.
"""
import logging

logger = logging.getLogger('app.api')

_subscription_expiry_handlers = []


def register_subscription_expiry_handler(handler) -> None:
    """Register a callback fired when an active acquisition is past its
    vigencia. Idempotent, so dev autoreload never double-registers."""
    if handler not in _subscription_expiry_handlers:
        _subscription_expiry_handlers.append(handler)


def notify_subscription_expiry(company_id, cs) -> None:
    """Invoke every registered handler. Best-effort: a failing handler never
    breaks the request path."""
    for handler in _subscription_expiry_handlers:
        try:
            handler(company_id, cs)
        except Exception:
            logger.warning(
                'subscription expiry handler failed for company=%s',
                company_id, exc_info=True,
            )
