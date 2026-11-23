"""Composition root for the promotion feature.

This is the ONLY promotion module (besides presentation/tasks/apps) allowed to
instantiate concrete infrastructure adapters. Application use cases and services
depend on ports; here we wire the Django implementations and expose small
factory functions + facades that callers (presentation, tasks, other features)
use instead of building dependencies themselves.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional


# ── adapter factories ────────────────────────────────────────────────────────

def get_promotion_repo():
    from platform.features.billing.commerce.promotion.infrastructure.repositories import (
        DjangoPromotionVoucherRepository,
    )
    return DjangoPromotionVoucherRepository()


def get_plan_catalog():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.plan_catalog import (
        DjangoPlanCatalog,
    )
    return DjangoPlanCatalog()


def get_charge_port():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.charge import (
        DjangoPromotionCharge,
    )
    return DjangoPromotionCharge()


def get_billing_company():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.billing_company import (
        DjangoBillingCompany,
    )
    return DjangoBillingCompany()


def get_invoice_bridge():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.invoice_bridge import (
        DjangoInvoiceBridge,
    )
    return DjangoInvoiceBridge()


def get_onboarding_registration():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.onboarding_registration import (
        DjangoOnboardingRegistration,
    )
    return DjangoOnboardingRegistration()


def get_payment_method_creator():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.payment_method import (
        DjangoPaymentMethodCreator,
    )
    return DjangoPaymentMethodCreator()


def get_notification():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.notification import (
        DjangoNotification,
    )
    return DjangoNotification()


def get_billing_directory():
    from platform.features.billing.commerce.promotion.infrastructure.adapters.billing_directory import (
        DjangoPromoBillingDirectory,
    )
    return DjangoPromoBillingDirectory()


# ── settings-derived config (settings read ONLY here) ─────────────────────────

def get_email_config():
    from django.conf import settings

    from platform.features.billing.commerce.promotion.application.voucher_emails import EmailConfig
    return EmailConfig(
        client_app_url=getattr(settings, 'CLIENT_APP_URL', 'http://localhost:4110'),
        support_email=getattr(settings, 'PLATFORM_SUPPORT_EMAIL', 'soporte@base.local'),
        currency=getattr(settings, 'PROMO_PUBLIC_CURRENCY', 'USD'),
    )


def get_public_currency() -> str:
    from django.conf import settings
    return getattr(settings, 'PROMO_PUBLIC_CURRENCY', 'USD')


def get_public_redeem_months() -> int:
    from django.conf import settings
    return int(getattr(settings, 'PROMO_PUBLIC_REDEEM_MONTHS', 12))


def get_gift_catalog() -> dict:
    from django.conf import settings

    from platform.features.billing.commerce.promotion.application.purchase_catalog import parse_catalog
    return parse_catalog(getattr(settings, 'PROMO_GIFT_CATALOG_JSON', None))


def build_company_voucher_notifier():
    """Return a ``callable(voucher) -> None`` that emails the company admin.

    Wires the notification + directory adapters and email config so the
    application ``CreateVoucherUseCase`` stays ORM/infrastructure-free.
    """
    from platform.features.billing.commerce.promotion.application.voucher_emails import (
        dispatch_company_voucher_email,
    )
    notifier = get_notification()
    directory = get_billing_directory()
    config = get_email_config()

    def _notify(voucher) -> None:
        dispatch_company_voucher_email(
            notifier=notifier, directory=directory, voucher=voucher, config=config,
        )

    return _notify


# ── use case builders ─────────────────────────────────────────────────────────

def build_validate_use_case():
    from platform.features.billing.commerce.promotion.application.use_cases import ValidateVoucherUseCase
    return ValidateVoucherUseCase(get_promotion_repo(), get_plan_catalog())


def build_redeem_use_case():
    from platform.features.billing.commerce.promotion.application.use_cases import RedeemVoucherUseCase
    return RedeemVoucherUseCase(get_promotion_repo(), get_plan_catalog(), get_charge_port())


def build_create_voucher_use_case():
    from platform.features.billing.commerce.promotion.application.use_cases import CreateVoucherUseCase
    return CreateVoucherUseCase(
        get_promotion_repo(), notifier=build_company_voucher_notifier(),
    )


def build_public_preview_use_case():
    from platform.features.billing.commerce.promotion.application.public_purchase import (
        PublicPurchasePreviewUseCase,
    )
    return PublicPurchasePreviewUseCase(
        plan_catalog=get_plan_catalog(),
        catalog=get_gift_catalog(),
        currency=get_public_currency(),
    )


def build_public_checkout_use_case():
    from platform.features.billing.commerce.promotion.application.public_purchase import (
        PublicPurchaseCheckoutUseCase,
    )
    return PublicPurchaseCheckoutUseCase(
        repository=get_promotion_repo(),
        charge_port=get_charge_port(),
        billing_company=get_billing_company(),
        invoice_bridge=get_invoice_bridge(),
        notifier=get_notification(),
        plan_catalog=get_plan_catalog(),
        catalog=get_gift_catalog(),
        redeem_months=get_public_redeem_months(),
        email_config=get_email_config(),
        currency=get_public_currency(),
    )


def build_validate_onboarding_use_case():
    from platform.features.billing.commerce.promotion.application.onboarding import (
        ValidateOnboardingPromotionUseCase,
    )
    return ValidateOnboardingPromotionUseCase(
        registration=get_onboarding_registration(),
        validate_use_case=build_validate_use_case(),
    )


def build_apply_onboarding_use_case():
    from platform.features.billing.commerce.promotion.application.onboarding import (
        ApplyOnboardingPromotionUseCase,
    )
    return ApplyOnboardingPromotionUseCase(
        registration=get_onboarding_registration(),
        validate_use_case=build_validate_use_case(),
    )


def process_onboarding_billing(*, company_id, registration) -> None:
    """Composition facade used by client onboarding finalize."""
    from platform.features.billing.commerce.promotion.application.onboarding_finalize import (
        OnboardingBillingService,
    )
    OnboardingBillingService(
        redeem_use_case=build_redeem_use_case(),
        charge_port=get_charge_port(),
        payment_method_creator=get_payment_method_creator(),
        plan_catalog=get_plan_catalog(),
    ).run(company_id=company_id, registration=registration)


# ── renewal facades (stable names imported by subscription feature) ───────────

def get_renewal_charge_amount(company_id, plan_price: Decimal, *, plan_id=None):
    from platform.features.billing.commerce.promotion.application.renewal_integration import (
        get_renewal_charge_amount as _f,
    )
    return _f(get_promotion_repo(), company_id, plan_price, plan_id=plan_id)


def after_successful_renewal_charge(company_id, *, plan_id=None) -> None:
    from platform.features.billing.commerce.promotion.application.renewal_integration import (
        after_successful_renewal_charge as _f,
    )
    _f(get_promotion_repo(), company_id, plan_id=plan_id)


# ── benefit lifecycle facades ─────────────────────────────────────────────────

def forfeit_active_promotion_benefits(company_id, *, voucher_types: Optional[tuple[str, ...]] = None) -> int:
    return get_promotion_repo().cancel_benefits(company_id, voucher_types=voucher_types)


def forfeit_active_gift_benefits(company_id) -> int:
    return forfeit_active_promotion_benefits(company_id, voucher_types=('GIFT',))


def revert_expired_gift_benefits(*, now=None) -> int:
    """Restore the previous plan for gift upgrades whose window elapsed."""
    from django.utils import timezone

    from platform.features.billing.commerce.promotion.application.benefit_lifecycle import (
        revert_expired_gift_benefits as _run,
    )
    now = now or timezone.now()
    return _run(get_promotion_repo(), get_plan_catalog(), now=now)
