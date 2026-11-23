from uuid import UUID

from core.errors import AppErrorCode, OnboardingException
from core.identifiers import to_schema_name

from platform.features.company.tenant.company.application.geo_city import (
    assert_active_geo_city,
)
from platform.features.company.tenant.company.domain.interfaces import ICompanyRepository

from ...domain.enums import OnboardingStep
from ...domain.interfaces import ICompanyRegistrationRepository
from ...domain.schemas import CompanyStepSchema, OnboardingStateSchema
from ._common import build_state_schema, ensure_active, ensure_step_writable
from core.trace import trace_layer


class SubmitCompanyStepUseCase:

    def __init__(
        self,
        repository: ICompanyRegistrationRepository,
        company_repository: ICompanyRepository,
    ):
        self.repository = repository
        self.company_repository = company_repository

    @trace_layer('application')
    def execute(self, registration_id: UUID, data: CompanyStepSchema) -> OnboardingStateSchema:
        reg = self.repository.get(registration_id)
        ensure_active(reg)
        ensure_step_writable(reg, OnboardingStep.COMPANY)

        schema_name = to_schema_name(data.name)
        if not schema_name:
            raise OnboardingException(
                AppErrorCode.ONBOARDING_SCHEMA_TAKEN,
                override_detail='Company name cannot be reduced to a valid identifier.',
            )

        assert_active_geo_city(
            data.city_id,
            expected_country_code=data.country_code,
        )
        if data.is_registered and self.company_repository.get_by_nit(data.nit):
            raise OnboardingException(AppErrorCode.ONBOARDING_DUPLICATE_NIT)
        if self.company_repository.get_by_schema_name(schema_name):
            raise OnboardingException(AppErrorCode.ONBOARDING_SCHEMA_TAKEN)

        self.repository.save_company_step(registration_id, data, schema_name)

        reg.nit = data.nit
        reg.schema_name = schema_name
        reg.company_data = data.to_storage_dict()
        reg.company_data_completed = True
        return build_state_schema(reg)
