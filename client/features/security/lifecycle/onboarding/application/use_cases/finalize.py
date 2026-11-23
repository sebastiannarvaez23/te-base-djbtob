import logging
from uuid import UUID

from django.db import transaction

from core.errors import AppErrorCode, ConflictException, OnboardingException
from core.parameters import get_parameter
from platform.features.company.tenant.company.domain.interfaces import ICompanyRepository
from platform.features.compliance.policy.policy.domain.interfaces import IPolicyRepository

from ...domain.enums import OnboardingStep
from ...domain.interfaces import (
    ICompanyRegistrationRepository,
    IFinalizeSideEffects,
)
from ...domain.schemas import FinalizeResultSchema
from ..privacy import (
    bind_privacy_country_to_company,
    build_onboarding_acceptances,
    build_onboarding_content_hashes,
    collect_onboarding_policies_to_seal,
    sign_onboarding_policies,
)
from ..step_resolver import StepResolver
from ._common import build_step_state, ensure_active
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class FinalizeOnboardingUseCase:
    """Create the tenant (Company + Domain + admin User + CompanySubscription).

    Delegates Company/Domain/Subscription creation to CreateCompanyUseCase.
    Admin user attachment is owned by the onboarding repository port.
    """

    def __init__(
        self,
        repository: ICompanyRegistrationRepository,
        company_repository: ICompanyRepository,
        policy_repository: IPolicyRepository,
        side_effects: IFinalizeSideEffects,
    ):
        self.repository = repository
        self.company_repository = company_repository
        self.policy_repository = policy_repository
        self.side_effects = side_effects

    @staticmethod
    def _assert_promotion_matches_subscription(reg) -> None:
        from core.errors import AppErrorCode, AppException

        sub_data = reg.subscription_data or {}
        preview = sub_data.get('promotion_preview')
        if not preview:
            return
        preview_sub_id = preview.get('subscription_id')
        if preview_sub_id and str(reg.subscription_id) != str(preview_sub_id):
            raise AppException(AppErrorCode.PROMO_INCOMPATIBLE)

    @trace_layer('application')
    def execute(
        self,
        registration_id: UUID,
        *,
        privacy_accepted: bool,
        privacy_content_hash: str,
        privacy_country: str,
        terms_accepted: bool,
        terms_content_hash: str,
        sign_context=None,
    ) -> FinalizeResultSchema:
        reg = self.repository.get(registration_id)
        ensure_active(reg)

        if StepResolver.resolve(build_step_state(reg)) != OnboardingStep.CONFIRMATION:
            raise OnboardingException(AppErrorCode.ONBOARDING_STEP_OUT_OF_ORDER)

        self._assert_promotion_matches_subscription(reg)

        company_country = bind_privacy_country_to_company(
            privacy_country=privacy_country,
            company_data=reg.company_data,
        )

        policies_to_seal = collect_onboarding_policies_to_seal(
            country=company_country,
            content_hashes=build_onboarding_content_hashes(
                privacy_content_hash=privacy_content_hash,
                terms_content_hash=terms_content_hash,
            ),
            accepted_by_code=build_onboarding_acceptances(
                privacy_accepted=privacy_accepted,
                terms_accepted=terms_accepted,
            ),
            repository=self.policy_repository,
        )

        from platform.features.company.tenant.company.application.use_cases import CreateCompanyUseCase
        from platform.features.company.tenant.company.domain.schemas import CreateCompanySchema
        from platform.features.compliance.policy.policy.domain.schemas import SignPolicyContextSchema

        company_data = reg.company_data
        user_data = reg.admin_user_data
        ctx = sign_context or SignPolicyContextSchema(channel='web')

        try:
            with transaction.atomic():
                nit = (company_data.get('nit') or '').strip()
                if nit and self.company_repository.get_by_nit(nit):
                    raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_NIT)
                if self.company_repository.get_by_schema_name(reg.schema_name):
                    raise OnboardingException(AppErrorCode.ONBOARDING_SCHEMA_TAKEN)
                if self.repository.username_taken(user_data['username']):
                    raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)
                if self.repository.email_taken(user_data['email']):
                    raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)

                reg = self.repository.lock_for_finalize(registration_id)
                if reg.status != 'in_progress':
                    raise OnboardingException(AppErrorCode.ONBOARDING_ALREADY_COMPLETED)

                sub_data = reg.subscription_data or {}
                preview = sub_data.get('promotion_preview') or {}
                interval = sub_data.get('billing_interval') or 'monthly'
                if (preview.get('voucher_type') or '').upper() == 'GIFT':
                    interval = 'monthly'
                created = CreateCompanyUseCase(self.company_repository).execute(
                    CreateCompanySchema(
                        schema_name=reg.schema_name,
                        nit=nit,
                        name=company_data['name'],
                        address=company_data['address'],
                        geo_city_id=company_data['city_id'],
                        subscription_id=reg.subscription_id,
                        billing_interval=interval,
                    )
                )
                user_id = self.repository.provision_admin_user(created.id, user_data)
                sign_onboarding_policies(
                    user_id=user_id,
                    company_id=created.id,
                    contents=policies_to_seal,
                    context=ctx,
                )
                self.repository.mark_completed(registration_id, company_id=created.id)
        except OnboardingException:
            raise
        except ConflictException as exc:
            if exc.code == AppErrorCode.COMPANY_DUPLICATE_NIT:
                raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_NIT) from exc
            raise
        except Exception as exc:
            logger.exception(
                'Finalize onboarding failed',
                extra={'registration_id': str(registration_id)},
            )
            self.repository.mark_failed_provisioning(registration_id, reason=str(exc))
            raise

        email_confirm_required = bool(get_parameter('REG_EMAIL_CONFIRM', default=False))
        self.side_effects.after_commit(
            company_id=created.id,
            user_id=user_id,
            registration_id=registration_id,
            email_confirm_required=email_confirm_required,
        )
        return FinalizeResultSchema(
            registration_id=registration_id,
            company_id=created.id,
            email_confirmation_required=email_confirm_required,
        )
