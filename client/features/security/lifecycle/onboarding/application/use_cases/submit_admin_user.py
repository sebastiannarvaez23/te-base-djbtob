from uuid import UUID

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password

from core.errors import AppErrorCode, OnboardingException, ValidationAppException

from ...domain.enums import OnboardingStep
from ...domain.interfaces import ICompanyRegistrationRepository
from ...domain.schemas import AdminUserStepSchema, OnboardingStateSchema
from ._common import build_state_schema, ensure_active, ensure_step_writable
from core.trace import trace_layer


class SubmitAdminUserStepUseCase:

    def __init__(self, repository: ICompanyRegistrationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, registration_id: UUID, data: AdminUserStepSchema) -> OnboardingStateSchema:
        reg = self.repository.get(registration_id)
        ensure_active(reg)
        ensure_step_writable(reg, OnboardingStep.ADMIN_USER)

        # On re-edit the user is not required to retype the password: an
        # empty password means "keep the hash already on file". On the first
        # submit there is no stored hash yet, so password is mandatory.
        existing_hash = (reg.admin_user_data or {}).get('password_hash') if reg.admin_user_data else None
        password_provided = bool(data.password) or bool(data.password_confirmation)

        if password_provided:
            if data.password != data.password_confirmation:
                raise ValidationAppException(
                    AppErrorCode.VALIDATION_ERROR,
                    override_detail="Passwords don't match.",
                )
            validate_password(data.password)
            hashed = make_password(data.password)
        elif existing_hash:
            hashed = existing_hash
        else:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail="Password is required.",
            )

        if self.repository.username_taken(data.username):
            raise OnboardingException(
                AppErrorCode.ONBOARDING_DUPLICATE_EMAIL,
                override_detail='That username is already in use.',
            )
        if self.repository.email_taken(data.email):
            raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_EMAIL)

        self.repository.save_admin_user_step(registration_id, data, hashed_password=hashed)

        stored = data.to_storage_dict(hashed)
        reg.admin_user_completed = True
        reg.admin_user_data = stored
        return build_state_schema(reg)
