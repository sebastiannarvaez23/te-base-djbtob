from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.errors import AppErrorCode, ConflictException, OnboardingException

from ..domain.enums import OnboardingStatus, OnboardingStep
from ..domain.interfaces import ICompanyRegistrationRepository
from ..domain.schemas import (
    AdminUserStepSchema,
    CompanyStepSchema,
    PaymentStepSchema,
    SubscriptionStepSchema,
)
from ..models import CompanyRegistration


def _parse_birth_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


class DjangoCompanyRegistrationRepository(ICompanyRegistrationRepository):

    def create(self, email: str, ttl_seconds: int) -> CompanyRegistration:
        return CompanyRegistration.objects.create(
            email=email,
            status=OnboardingStatus.IN_PROGRESS.value,
            current_step=OnboardingStep.COMPANY.value,
            expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
        )

    def get(self, registration_id: UUID) -> Optional[CompanyRegistration]:
        return CompanyRegistration.objects.filter(id=registration_id).first()

    def get_active_by_email(self, email: str) -> Optional[CompanyRegistration]:
        return CompanyRegistration.objects.filter(
            email=email,
            status=OnboardingStatus.IN_PROGRESS.value,
        ).first()

    def username_taken(self, username: str) -> bool:
        cleaned = (username or '').strip()
        if not cleaned:
            return False
        from client.features.security.lifecycle.registration.models import User
        return User.objects.filter(username__iexact=cleaned).exists()

    def email_taken(self, email: str) -> bool:
        cleaned = (email or '').strip()
        if not cleaned:
            return False
        from client.features.security.lifecycle.registration.models import User
        return User.objects.filter(email__iexact=cleaned).exists()

    def provision_admin_user(self, company_id: UUID, user_data: dict) -> UUID:
        from client.features.security.lifecycle.registration.models import Rol, User
        from platform.features.company.tenant.company.models import Company

        company = Company.objects.get(id=company_id)
        admin_role = Rol.objects.filter(
            name='Administrator', company__isnull=True,
        ).first()
        if admin_role is None:
            admin_role, _ = Rol.objects.get_or_create(
                name='Administrator', company=None,
            )

        phone_country = (user_data.get('phone_country_code') or 'CO').strip().upper()
        user = User(
            username=user_data['username'],
            email=user_data['email'],
            first_name=user_data['first_name'],
            second_name=user_data.get('second_name') or '',
            last_name=user_data['last_name'],
            second_last_name=user_data.get('second_last_name') or '',
            document_type=user_data.get('document_type') or '',
            document_number=user_data.get('document_number') or '',
            birth_date=_parse_birth_date(user_data.get('birth_date')),
            telephone=user_data['telephone'],
            phone_country_code=phone_country,
            company=company,
            rol=admin_role,
        )
        user.password = user_data['password_hash']
        user.password_changed_at = timezone.now()
        try:
            user.save()
        except IntegrityError as exc:
            if 'uniq_user_company_document' in str(exc).lower():
                raise ConflictException(AppErrorCode.USER_DUPLICATE_DOCUMENT) from exc
            raise
        return user.id

    def lock_for_finalize(self, registration_id: UUID) -> CompanyRegistration:
        """SELECT … FOR UPDATE to serialise concurrent /finalize calls."""
        return (
            CompanyRegistration.objects
            .select_for_update()
            .get(id=registration_id)
        )

    # ── Step writes ────────────────────────────────────────────────────────

    def save_company_step(
        self,
        registration_id: UUID,
        data: CompanyStepSchema,
        schema_name: str,
    ) -> None:
        try:
            CompanyRegistration.objects.filter(id=registration_id).update(
                nit=data.nit,
                schema_name=schema_name,
                company_data=data.to_storage_dict(),
                company_data_completed=True,
                current_step=self._next_step_after_company(),
            )
        except IntegrityError as exc:
            msg = str(exc).lower()
            if 'uniq_active_onboarding_nit' in msg:
                raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_NIT) from exc
            if 'uniq_active_onboarding_schema' in msg:
                raise OnboardingException(AppErrorCode.ONBOARDING_SCHEMA_TAKEN) from exc
            raise

    def save_admin_user_step(
        self,
        registration_id: UUID,
        data: AdminUserStepSchema,
        hashed_password: str,
    ) -> None:
        CompanyRegistration.objects.filter(id=registration_id).update(
            admin_user_data=data.to_storage_dict(hashed_password),
            admin_user_completed=True,
            current_step=OnboardingStep.SUBSCRIPTION.value,
        )

    def save_subscription_step(
        self,
        registration_id: UUID,
        data: SubscriptionStepSchema,
        requires_payment: bool,
        subscription_payload: dict,
    ) -> None:
        # Read + write under a row lock so a concurrent submit cannot leave
        # the registration with stale payment_data after a plan change.
        with transaction.atomic():
            try:
                reg = (
                    CompanyRegistration.objects
                    .select_for_update()
                    .get(id=registration_id)
                )
            except CompanyRegistration.DoesNotExist:
                return

            previous_required = reg.requires_payment
            payment_completed = reg.payment_completed
            payment_data = reg.payment_data
            if previous_required != requires_payment:
                payment_completed = False
                payment_data = {}

            next_step = (
                OnboardingStep.PAYMENT.value
                if requires_payment and not payment_completed
                else OnboardingStep.CONFIRMATION.value
            )

            CompanyRegistration.objects.filter(id=registration_id).update(
                subscription_id=data.subscription_id,
                subscription_data=subscription_payload,
                subscription_selected=True,
                requires_payment=requires_payment,
                payment_completed=payment_completed,
                payment_data=payment_data,
                current_step=next_step,
            )

    def save_payment_step(self, registration_id: UUID, data: PaymentStepSchema) -> None:
        CompanyRegistration.objects.filter(id=registration_id).update(
            payment_data={
                'processor_token': data.processor_token,
                'holder': data.holder,
                'last4': data.last4,
                'expiry_month': data.expiry_month,
                'expiry_year': data.expiry_year,
            },
            payment_completed=True,
            current_step=OnboardingStep.CONFIRMATION.value,
        )

    # ── Terminal transitions ───────────────────────────────────────────────

    def mark_completed(self, registration_id: UUID, company_id: UUID) -> None:
        CompanyRegistration.objects.filter(id=registration_id).update(
            status=OnboardingStatus.COMPLETED.value,
            finalized_company_id=company_id,
            current_step=OnboardingStep.CONFIRMATION.value,
        )

    def mark_failed_provisioning(self, registration_id: UUID, reason: str) -> None:
        CompanyRegistration.objects.filter(id=registration_id).update(
            status=OnboardingStatus.FAILED_PROVISIONING.value,
            failure_reason=(reason or '')[:500],
        )

    def save_promotion_apply(
        self,
        registration_id: UUID,
        *,
        serial: str,
        promotion_preview: dict,
    ) -> None:
        from ..application.step_resolver import StepState
        from ..domain.enums import OnboardingStep

        with transaction.atomic():
            reg = CompanyRegistration.objects.select_for_update().get(id=registration_id)
            sub_data = dict(reg.subscription_data or {})
            sub_data['applied_voucher_serial'] = serial
            sub_data['promotion_preview'] = promotion_preview
            sub_data['adjusted_price'] = promotion_preview.get('final_amount')

            requires_payment = (promotion_preview.get('voucher_type') or '').upper() != 'GIFT'
            previous_required = reg.requires_payment
            payment_completed = reg.payment_completed
            payment_data = reg.payment_data
            if previous_required != requires_payment:
                payment_completed = False
                payment_data = {}

            state = StepState(
                company_data_completed=reg.company_data_completed,
                admin_user_completed=reg.admin_user_completed,
                subscription_selected=reg.subscription_selected,
                payment_completed=payment_completed,
                requires_payment=requires_payment,
            )
            next_step = (
                OnboardingStep.PAYMENT.value
                if requires_payment and not payment_completed
                else OnboardingStep.CONFIRMATION.value
            )
            CompanyRegistration.objects.filter(id=registration_id).update(
                subscription_data=sub_data,
                requires_payment=requires_payment,
                payment_completed=payment_completed,
                payment_data=payment_data,
                current_step=next_step,
            )

    @staticmethod
    def _next_step_after_company() -> str:
        return OnboardingStep.ADMIN_USER.value
