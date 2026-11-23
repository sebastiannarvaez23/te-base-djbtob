"""Unit tests for FinalizeOnboardingUseCase privacy gate (pre-provision)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import pytest

from client.features.security.lifecycle.onboarding.application.use_cases.finalize import (
    FinalizeOnboardingUseCase,
)
from client.features.security.lifecycle.onboarding.domain.enums import (
    OnboardingStatus,
    OnboardingStep,
)
from core.errors import AppErrorCode, OnboardingException
from platform.features.compliance.policy.policy.domain.enums import (
    PolicyAudience,
    PolicyCountryStatus,
)
from platform.features.compliance.policy.policy.domain.schemas import PolicyCountryContentSchema


FINALIZE_MOD = 'client.features.security.lifecycle.onboarding.application.use_cases.finalize'


def _use_case(repo, **kwargs):
    return FinalizeOnboardingUseCase(
        repo,
        kwargs.get('company_repository') or MagicMock(),
        kwargs.get('policy_repository') or MagicMock(),
        kwargs.get('side_effects') or MagicMock(),
    )


def _reg(**overrides):
    base = dict(
        id=uuid4(),
        status=OnboardingStatus.IN_PROGRESS.value,
        email='owner@example.com',
        nit='900111222',
        schema_name='acme',
        company_data_completed=True,
        admin_user_completed=True,
        subscription_selected=True,
        payment_completed=True,
        requires_payment=False,
        subscription_id=uuid4(),
        company_data={
            'name': 'Acme',
            'nit': '900111222',
            'address': '1 St',
            'country': 'Colombia',
            'country_code': 'CO',
            'state': 'Cundinamarca',
            'city': 'Bogota',
            'city_id': '0f15d58f-1ed6-4019-a3b7-22861f9dbc82',
        },
        admin_user_data={
            'email': 'owner@example.com',
            'username': 'owner1',
            'telephone': '3001234567',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'password_hash': 'pbkdf2_sha256$dummy',
        },
        subscription_data={'subscription_id': str(uuid4())},
        payment_data={},
    )
    base.update(overrides)
    reg = MagicMock()
    for k, v in base.items():
        setattr(reg, k, v)
    reg.is_expired = lambda: False
    return reg


def _privacy_content():
    return PolicyCountryContentSchema(
        policy_id=uuid4(),
        policy_code='PRIVACY-POLICY',
        audience=PolicyAudience.CLIENT,
        country='CO',
        version=1,
        status=PolicyCountryStatus.PUBLISHED,
        title='Privacy',
        markdown='',
        object_key='x.md',
        content_hash='a' * 64,
        byte_size=1,
    )


@pytest.mark.unit
def test_finalize_rejects_when_privacy_not_accepted():
    repo = MagicMock()
    repo.get.return_value = _reg()

    with patch(f'{FINALIZE_MOD}.StepResolver.resolve', return_value=OnboardingStep.CONFIRMATION), \
         patch(f'{FINALIZE_MOD}.bind_privacy_country_to_company', return_value='CO'), \
         patch(
             f'{FINALIZE_MOD}.collect_onboarding_policies_to_seal',
             side_effect=OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_REQUIRED),
         ):
        with pytest.raises(OnboardingException) as exc:
            _use_case(repo).execute(
                repo.get.return_value.id,
                privacy_accepted=False,
                privacy_content_hash='a' * 64,
                privacy_country='CO',
                terms_accepted=True,
                terms_content_hash='b' * 64,
            )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_REQUIRED


@pytest.mark.unit
def test_finalize_rejects_when_terms_not_accepted():
    repo = MagicMock()
    repo.get.return_value = _reg()

    with patch(f'{FINALIZE_MOD}.StepResolver.resolve', return_value=OnboardingStep.CONFIRMATION), \
         patch(f'{FINALIZE_MOD}.bind_privacy_country_to_company', return_value='CO'), \
         patch(
             f'{FINALIZE_MOD}.collect_onboarding_policies_to_seal',
             side_effect=OnboardingException(AppErrorCode.ONBOARDING_TERMS_REQUIRED),
         ):
        with pytest.raises(OnboardingException) as exc:
            _use_case(repo).execute(
                repo.get.return_value.id,
                privacy_accepted=True,
                privacy_content_hash='a' * 64,
                privacy_country='CO',
                terms_accepted=False,
                terms_content_hash='b' * 64,
            )
    assert exc.value.code == AppErrorCode.ONBOARDING_TERMS_REQUIRED


@pytest.mark.unit
def test_finalize_rejects_country_mismatch_before_provision():
    repo = MagicMock()
    repo.get.return_value = _reg()

    with patch(f'{FINALIZE_MOD}.StepResolver.resolve', return_value=OnboardingStep.CONFIRMATION), \
         patch(
             f'{FINALIZE_MOD}.bind_privacy_country_to_company',
             side_effect=OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_STALE),
         ):
        with pytest.raises(OnboardingException) as exc:
            _use_case(repo).execute(
                repo.get.return_value.id,
                privacy_accepted=True,
                privacy_content_hash='a' * 64,
                privacy_country='MX',
                terms_accepted=True,
                terms_content_hash='b' * 64,
            )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE
    repo.lock_for_finalize.assert_not_called()


@pytest.mark.unit
def test_finalize_rejects_stale_privacy_before_provision():
    repo = MagicMock()
    repo.get.return_value = _reg()

    with patch(f'{FINALIZE_MOD}.StepResolver.resolve', return_value=OnboardingStep.CONFIRMATION), \
         patch(f'{FINALIZE_MOD}.bind_privacy_country_to_company', return_value='CO'), \
         patch(
             f'{FINALIZE_MOD}.collect_onboarding_policies_to_seal',
             side_effect=OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_STALE),
         ):
        with pytest.raises(OnboardingException) as exc:
            _use_case(repo).execute(
                repo.get.return_value.id,
                privacy_accepted=True,
                privacy_content_hash='b' * 64,
                privacy_country='CO',
                terms_accepted=True,
                terms_content_hash='b' * 64,
            )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE
    repo.lock_for_finalize.assert_not_called()


@pytest.mark.unit
def test_finalize_rejects_out_of_order_step():
    repo = MagicMock()
    repo.get.return_value = _reg(company_data_completed=False)

    with patch(f'{FINALIZE_MOD}.StepResolver.resolve', return_value=OnboardingStep.COMPANY):
        with pytest.raises(OnboardingException) as exc:
            _use_case(repo).execute(
                repo.get.return_value.id,
                privacy_accepted=True,
                privacy_content_hash='a' * 64,
                privacy_country='CO',
                terms_accepted=True,
                terms_content_hash='b' * 64,
            )
    assert exc.value.code == AppErrorCode.ONBOARDING_STEP_OUT_OF_ORDER


@pytest.mark.unit
def test_finalize_calls_assert_then_signs_on_happy_path():
    """Privacy assert runs first; after user create, signature is sealed."""
    reg = _reg()
    repo = MagicMock()
    repo.get.return_value = reg
    repo.lock_for_finalize.return_value = reg
    repo.username_taken.return_value = False
    repo.email_taken.return_value = False

    company_id = uuid4()
    user_id = uuid4()
    created = MagicMock(id=company_id)
    repo.provision_admin_user.return_value = user_id
    company_repo = MagicMock()
    company_repo.get_by_nit.return_value = None
    company_repo.get_by_schema_name.return_value = None
    side_effects = MagicMock()
    privacy = _privacy_content()

    with patch(f'{FINALIZE_MOD}.StepResolver.resolve', return_value=OnboardingStep.CONFIRMATION), \
         patch(f'{FINALIZE_MOD}.bind_privacy_country_to_company', return_value='CO') as bind_country, \
         patch(
             f'{FINALIZE_MOD}.collect_onboarding_policies_to_seal',
             return_value=[privacy],
         ) as collect_policies, \
         patch(f'{FINALIZE_MOD}.sign_onboarding_policies') as sign_policies, \
         patch(f'{FINALIZE_MOD}.transaction.atomic') as atomic, \
         patch(
             'platform.features.company.tenant.company.application.use_cases.CreateCompanyUseCase',
         ) as create_company_cls, \
         patch(f'{FINALIZE_MOD}.get_parameter', return_value=False):

        atomic.return_value.__enter__ = MagicMock(return_value=None)
        atomic.return_value.__exit__ = MagicMock(return_value=False)
        create_company_cls.return_value.execute.return_value = created

        result = _use_case(
            repo,
            company_repository=company_repo,
            side_effects=side_effects,
        ).execute(
            reg.id,
            privacy_accepted=True,
            privacy_content_hash='a' * 64,
            privacy_country='CO',
            terms_accepted=True,
            terms_content_hash='b' * 64,
        )

    bind_country.assert_called_once()
    collect_policies.assert_called_once()
    collect_kwargs = collect_policies.call_args.kwargs
    assert collect_kwargs['accepted_by_code'] == {
        'PRIVACY-POLICY': True,
        'TERMS-AND-CONDITIONS': True,
    }
    assert collect_kwargs['content_hashes']['PRIVACY-POLICY'] == 'a' * 64
    assert collect_kwargs['content_hashes']['TERMS-AND-CONDITIONS'] == 'b' * 64
    assert 'repository' in collect_kwargs
    sign_policies.assert_called_once()
    sign_kwargs = sign_policies.call_args.kwargs
    assert sign_kwargs['user_id'] == user_id
    assert sign_kwargs['company_id'] == company_id
    assert sign_kwargs['contents'] == [privacy]
    repo.provision_admin_user.assert_called_once()
    repo.mark_completed.assert_called_once_with(reg.id, company_id=company_id)
    side_effects.after_commit.assert_called_once()
    assert result.company_id == company_id