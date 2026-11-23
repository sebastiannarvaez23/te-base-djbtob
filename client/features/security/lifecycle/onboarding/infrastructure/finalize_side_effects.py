"""Post-commit side effects after a successful onboarding finalize."""

from __future__ import annotations

import logging
from uuid import UUID

from client.features.security.lifecycle.onboarding.domain.interfaces import (
    ICompanyRegistrationRepository,
    IFinalizeSideEffects,
)

logger = logging.getLogger('app.api')


class DjangoFinalizeSideEffects(IFinalizeSideEffects):

    def __init__(self, repository: ICompanyRegistrationRepository):
        self.repository = repository

    def after_commit(
        self,
        *,
        company_id: UUID,
        user_id: UUID,
        registration_id: UUID,
        email_confirm_required: bool,
    ) -> None:
        from client.features.security.lifecycle.registration.models import User
        from platform.features.billing.subscription.subscription.models import CompanySubscription
        from platform.features.company.tenant.company.models import Company

        try:
            user = User.objects.get(id=user_id)
            company = Company.objects.get(id=company_id)
        except (User.DoesNotExist, Company.DoesNotExist):
            logger.exception(
                'Finalize side effects missing user/company',
                extra={'user_id': str(user_id), 'company_id': str(company_id)},
            )
            return

        try:
            registration = self.repository.get(registration_id)
            from platform.features.billing.commerce.promotion.composition import (
                process_onboarding_billing,
            )
            process_onboarding_billing(company_id=company_id, registration=registration)
        except Exception:
            logger.exception('process_onboarding_billing failed post-finalize')

        try:
            from platform.features.communication.notification.dispatchers import (
                dispatch_welcome_admin,
            )

            company_sub = (
                CompanySubscription.objects
                .filter(company=company)
                .select_related('subscription')
                .first()
            )
            if company_sub is not None:
                dispatch_welcome_admin(
                    user=user,
                    company=company,
                    subscription=company_sub.subscription,
                    company_subscription=company_sub,
                )
        except Exception:
            logger.exception('dispatch_welcome_admin failed post-finalize')

        try:
            from client.features.communication.messaging.inbox.application.welcome_notifier import (
                notify_executive_welcome,
            )

            notify_executive_welcome(
                schema_name=company.schema_name,
                user_id=user.id,
                user_name=f'{user.first_name} {user.last_name}'.strip() or user.username,
                company_name=company.name,
            )
        except Exception:
            logger.exception('notify_executive_welcome failed post-finalize')

        if not email_confirm_required:
            return

        try:
            from client.features.security.lifecycle.auth.application.email_confirmation import (
                IssueEmailConfirmationTokenUseCase,
            )
            from core.parameters import get_parameter
            from django.conf import settings as _settings
            from platform.features.communication.notification.dispatchers import (
                dispatch_email_confirm,
            )

            ttl_hours = int(get_parameter('EMAIL_CFM_TTL_H', default=24))
            raw = IssueEmailConfirmationTokenUseCase(ttl_hours=ttl_hours).execute(user)
            dispatch_email_confirm(
                user=user,
                confirmation_url=f'{_settings.EMAIL_CFM_URL}?token={raw}',
                expiration_time=ttl_hours,
            )
        except Exception:
            logger.exception('dispatch_email_confirm failed post-finalize')
