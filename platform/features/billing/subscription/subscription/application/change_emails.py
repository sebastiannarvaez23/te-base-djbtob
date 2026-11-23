"""
Data layer for the subscription-change emails (SUB_UPGRADE / SUB_DOWNGRADE).

Pure builders: receive the already-loaded plans + admin + company and return
the flat dict each template expects (mirrors invoice_context).
"""
from datetime import datetime
from typing import Any

from platform.features.billing.commerce.invoice.application.invoice_context import SUPPORT_EMAIL
from platform.features.billing.subscription.subscription.domain.billing_cycle import MONTHLY, YEARLY

PLATFORM_URL = 'https://base.local/dashboard'

_ES_MONTHS = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
              'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def _period_from(now: datetime, interval: str = MONTHLY) -> str:
    if interval == YEARLY:
        return f'{_ES_MONTHS[now.month]} {now.year} - {_ES_MONTHS[now.month]} {now.year + 1}'
    nxt = (now.month % 12) + 1
    nxt_year = now.year + (1 if now.month == 12 else 0)
    return f'{_ES_MONTHS[now.month]} {now.year} - {_ES_MONTHS[nxt]} {nxt_year}'


def _full_name(admin) -> str:
    if admin is None:
        return ''
    name = f'{getattr(admin, "first_name", "") or ""} {getattr(admin, "last_name", "") or ""}'.strip()
    return name or getattr(admin, 'username', '') or ''


def _features(plan) -> list[str]:
    return list(getattr(plan, 'features', []) or [])


def _bullets(items) -> str:
    return '\n'.join(f'- {i}' for i in items)


def build_upgrade_context(*, new_plan, previous_plan, admin, company, now: datetime,
                          charge_amount=None, billing_interval: str = MONTHLY) -> dict[str, Any]:
    """Context for SUB_UPGRADE (the plan-improved email; carries the invoice)."""
    price = charge_amount if charge_amount is not None else getattr(new_plan, 'price', 0)
    return {
        'new_plan':          getattr(new_plan, 'name', '') or '',
        'new_price':         float(price or 0),
        'previous_plan':     getattr(previous_plan, 'name', '') if previous_plan else '',
        'user_name':         _full_name(admin),
        'company_name':      getattr(company, 'name', '') or '',
        'current_year':      now.year,
        'platform_url':      PLATFORM_URL,
        'upgrade_date':      now.strftime('%Y-%m-%d'),
        'support_email':     SUPPORT_EMAIL,
        'new_features_list': _bullets(_features(new_plan)),
        'billing_interval':  billing_interval,
    }


def build_downgrade_context(*, new_plan, previous_plan, admin, company, now: datetime,
                            charge_amount=None, billing_interval: str = MONTHLY) -> dict[str, Any]:
    """Context for SUB_DOWNGRADE (scheduled plan reduction; no charge/invoice)."""
    new_features = set(_features(new_plan))
    removed = [f for f in _features(previous_plan) if f not in new_features] if previous_plan else []
    price = charge_amount if charge_amount is not None else getattr(new_plan, 'price', 0)
    return {
        'new_plan':              getattr(new_plan, 'name', '') or '',
        'new_price':             float(price or 0),
        'previous_plan':         getattr(previous_plan, 'name', '') if previous_plan else '',
        'user_name':             _full_name(admin),
        'company_name':          getattr(company, 'name', '') or '',
        'current_year':          now.year,
        'platform_url':          PLATFORM_URL,
        'upgrade_url':           PLATFORM_URL,
        'downgrade_date':        now.strftime('%Y-%m-%d'),
        'support_email':         SUPPORT_EMAIL,
        'removed_features_list': _bullets(removed),
        'billing_interval':      billing_interval,
    }


def build_suspended_context(*, plan, admin, company, now: datetime,
                            charge_amount=None, billing_interval: str = MONTHLY) -> dict[str, Any]:
    """Context for SUB_SUSPENDED (a renewal charge failed → access suspended)."""
    due = charge_amount if charge_amount is not None else getattr(plan, 'price', 0)
    return {
        'total_due':         float(due or 0),
        'user_name':         _full_name(admin),
        'company_name':      getattr(company, 'name', '') or '',
        'current_year':      now.year,
        'support_email':     SUPPORT_EMAIL,
        'billing_period':    _period_from(now, billing_interval),
        'reactivation_url':  PLATFORM_URL,
        'cancellation_date': now.strftime('%Y-%m-%d'),
        'subscription_name': getattr(plan, 'name', '') or '',
        'billing_interval':  billing_interval,
    }
