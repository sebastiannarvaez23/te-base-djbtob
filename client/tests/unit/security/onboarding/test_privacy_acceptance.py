"""Unit tests for onboarding privacy acceptance gate and signature seal."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from client.features.security.lifecycle.onboarding.application.privacy import (
    assert_privacy_acceptance,
    collect_onboarding_policies_to_seal,
    resolve_registration_country_code,
    sign_onboarding_privacy,
)
from core.errors import AppErrorCode, ConflictException, OnboardingException
from platform.features.compliance.policy.policy.domain.enums import (
    PolicyAudience,
    PolicyCountryStatus,
)
from platform.features.compliance.policy.policy.domain.required_codes import (
    ONBOARDING_PRIVACY_POLICY_CODE,
    ONBOARDING_TERMS_POLICY_CODE,
)
from platform.features.compliance.policy.policy.domain.schemas import (
    PolicyCountryContentSchema,
    SignPolicyContextSchema,
)


def _policy(**overrides):
    base = dict(
        id=uuid4(),
        code='PRIVACY-POLICY',
        is_active=True,
        audience=PolicyAudience.CLIENT,
    )
    base.update(overrides)
    return MagicMock(**base)


def _row(**overrides):
    base = dict(
        country='CO',
        version=2,
        status=PolicyCountryStatus.PUBLISHED,
        title='Privacy',
        object_key='client/policies/PRIVACY-POLICY/CO/v2.md',
        content_hash='a' * 64,
        byte_size=42,
        change_summary='',
        updated_at=None,
    )
    base.update(overrides)
    return MagicMock(**base)


# ── resolve_registration_country_code ───────────────────────────────────────


@pytest.mark.unit
def test_resolve_country_code_prefers_explicit_field():
    assert resolve_registration_country_code({
        'country': 'Colombia',
        'country_code': 'co',
    }) == 'CO'


@pytest.mark.unit
def test_resolve_country_code_accepts_iso_in_country():
    assert resolve_registration_country_code({'country': 'CO'}) == 'CO'


@pytest.mark.unit
def test_resolve_country_code_rejects_name_only():
    assert resolve_registration_country_code({'country': 'Colombia'}) is None


@pytest.mark.unit
def test_resolve_country_code_none_or_empty():
    assert resolve_registration_country_code(None) is None
    assert resolve_registration_country_code({}) is None
    assert resolve_registration_country_code({'country_code': '  '}) is None


@pytest.mark.unit
def test_resolve_country_code_rejects_invalid_iso():
    assert resolve_registration_country_code({'country_code': 'COL'}) is None
    assert resolve_registration_country_code({'country_code': 'C1'}) is None


# ── assert_privacy_acceptance ───────────────────────────────────────────────


@pytest.mark.unit
def test_assert_privacy_requires_acceptance():
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=False,
            content_hash='a' * 64,
            country='CO',
            repository=MagicMock(),
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_REQUIRED


@pytest.mark.unit
def test_assert_privacy_requires_hash():
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=True,
            content_hash='   ',
            country='CO',
            repository=MagicMock(),
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_REQUIRED


@pytest.mark.unit
def test_assert_privacy_rejects_invalid_country():
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=True,
            content_hash='a' * 64,
            country='Colombia',
            repository=MagicMock(),
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE


@pytest.mark.unit
def test_assert_privacy_rejects_missing_policy():
    repo = MagicMock()
    repo.get_by_code.return_value = None
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=True,
            content_hash='a' * 64,
            country='CO',
            repository=repo,
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE


@pytest.mark.unit
def test_assert_privacy_rejects_inactive_policy():
    repo = MagicMock()
    repo.get_by_code.return_value = _policy(is_active=False)
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=True,
            content_hash='a' * 64,
            country='CO',
            repository=repo,
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE


@pytest.mark.unit
def test_assert_privacy_rejects_admin_audience():
    repo = MagicMock()
    repo.get_by_code.return_value = _policy(audience=PolicyAudience.ADMIN)
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=True,
            content_hash='a' * 64,
            country='CO',
            repository=repo,
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE


@pytest.mark.unit
def test_assert_privacy_rejects_missing_published_country():
    repo = MagicMock()
    repo.get_by_code.return_value = _policy()
    repo.get_country.return_value = None
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=True,
            content_hash='a' * 64,
            country='CO',
            repository=repo,
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE


@pytest.mark.unit
def test_assert_privacy_rejects_stale_hash():
    repo = MagicMock()
    repo.get_by_code.return_value = _policy()
    repo.get_country.return_value = _row(content_hash='b' * 64)
    with pytest.raises(OnboardingException) as exc:
        assert_privacy_acceptance(
            accepted=True,
            content_hash='a' * 64,
            country='CO',
            repository=repo,
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE


@pytest.mark.unit
def test_assert_privacy_happy_path_returns_content():
    policy_id = uuid4()
    repo = MagicMock()
    repo.get_by_code.return_value = _policy(id=policy_id)
    repo.get_country.return_value = _row()
    result = assert_privacy_acceptance(
        accepted=True,
        content_hash='A' * 64,
        country='co',
        repository=repo,
    )

    assert result.policy_id == policy_id
    assert result.content_hash == 'a' * 64
    assert result.country == 'CO'
    assert result.markdown == ''


# ── collect_onboarding_policies_to_seal (per-code) ───────────────────────────


def _dual_policy_repo(*, privacy_hash='a' * 64, terms_hash='b' * 64):
    """Repo that returns published privacy + terms by code."""
    privacy_id = uuid4()
    terms_id = uuid4()
    privacy = _policy(id=privacy_id, code=ONBOARDING_PRIVACY_POLICY_CODE)
    terms = _policy(id=terms_id, code=ONBOARDING_TERMS_POLICY_CODE)

    def get_by_code(code):
        code = str(code).upper()
        if code == ONBOARDING_PRIVACY_POLICY_CODE:
            return privacy
        if code == ONBOARDING_TERMS_POLICY_CODE:
            return terms
        return None

    def get_country(policy_id, country):
        if policy_id == privacy_id:
            return _row(content_hash=privacy_hash, title='Privacy')
        if policy_id == terms_id:
            return _row(
                content_hash=terms_hash,
                title='Terms',
                object_key='client/policies/TERMS-AND-CONDITIONS/CO/v1.md',
            )
        return None

    repo = MagicMock()
    repo.get_by_code.side_effect = get_by_code
    repo.get_country.side_effect = get_country
    return repo


@pytest.mark.unit
def test_collect_rejects_terms_not_accepted():
    repo = _dual_policy_repo()
    with pytest.raises(OnboardingException) as exc:
        collect_onboarding_policies_to_seal(
            country='CO',
            content_hashes={
                ONBOARDING_PRIVACY_POLICY_CODE: 'a' * 64,
                ONBOARDING_TERMS_POLICY_CODE: 'b' * 64,
            },
            accepted_by_code={
                ONBOARDING_PRIVACY_POLICY_CODE: True,
                ONBOARDING_TERMS_POLICY_CODE: False,
            },
            repository=repo,
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_TERMS_REQUIRED


@pytest.mark.unit
def test_collect_rejects_stale_terms_hash():
    repo = _dual_policy_repo(terms_hash='c' * 64)
    with pytest.raises(OnboardingException) as exc:
        collect_onboarding_policies_to_seal(
            country='CO',
            content_hashes={
                ONBOARDING_PRIVACY_POLICY_CODE: 'a' * 64,
                ONBOARDING_TERMS_POLICY_CODE: 'b' * 64,
            },
            accepted_by_code={
                ONBOARDING_PRIVACY_POLICY_CODE: True,
                ONBOARDING_TERMS_POLICY_CODE: True,
            },
            repository=repo,
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_TERMS_STALE


@pytest.mark.unit
def test_collect_happy_path_returns_privacy_and_terms():
    repo = _dual_policy_repo()
    sealed = collect_onboarding_policies_to_seal(
        country='CO',
        content_hashes={
            ONBOARDING_PRIVACY_POLICY_CODE: 'a' * 64,
            ONBOARDING_TERMS_POLICY_CODE: 'b' * 64,
        },
        accepted_by_code={
            ONBOARDING_PRIVACY_POLICY_CODE: True,
            ONBOARDING_TERMS_POLICY_CODE: True,
        },
        repository=repo,
    )
    assert [c.policy_code for c in sealed] == [
        ONBOARDING_PRIVACY_POLICY_CODE,
        ONBOARDING_TERMS_POLICY_CODE,
    ]


# ── sign_onboarding_privacy ─────────────────────────────────────────────────


def _content():
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
def test_sign_onboarding_privacy_delegates_to_sign_use_case():
    content = _content()
    user_id = uuid4()
    company_id = uuid4()
    ctx = SignPolicyContextSchema(channel='web', ip_address='1.2.3.4')

    with patch(
        'client.features.security.lifecycle.onboarding.application.privacy.SignPolicyUseCase',
    ) as sign_cls, patch(
        'client.features.security.lifecycle.onboarding.application.privacy.DjangoPolicyRepository',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.privacy.DjangoPolicySignatureRepository',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.privacy.MinioStorageService',
    ):
        sign_cls.return_value.execute.return_value = MagicMock()
        sign_onboarding_privacy(
            user_id=user_id,
            company_id=company_id,
            content=content,
            context=ctx,
        )
        schema = sign_cls.return_value.execute.call_args.args[0]
        assert schema.policy_id == content.policy_id
        assert schema.country == 'CO'
        assert schema.signatory.subject_id == str(user_id)
        assert schema.signatory.tenant_id == str(company_id)
        assert schema.signatory.subject_type.value == 'client'


@pytest.mark.unit
def test_sign_onboarding_privacy_ignores_already_signed():
    with patch(
        'client.features.security.lifecycle.onboarding.application.privacy.SignPolicyUseCase',
    ) as sign_cls, patch(
        'client.features.security.lifecycle.onboarding.application.privacy.DjangoPolicyRepository',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.privacy.DjangoPolicySignatureRepository',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.privacy.MinioStorageService',
    ):
        sign_cls.return_value.execute.side_effect = ConflictException(
            AppErrorCode.POLICY_ALREADY_SIGNED,
        )
        sign_onboarding_privacy(
            user_id=uuid4(),
            company_id=uuid4(),
            content=_content(),
            context=SignPolicyContextSchema(),
        )


@pytest.mark.unit
def test_sign_onboarding_privacy_reraises_other_conflicts():
    with patch(
        'client.features.security.lifecycle.onboarding.application.privacy.SignPolicyUseCase',
    ) as sign_cls, patch(
        'client.features.security.lifecycle.onboarding.application.privacy.DjangoPolicyRepository',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.privacy.DjangoPolicySignatureRepository',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.privacy.MinioStorageService',
    ):
        sign_cls.return_value.execute.side_effect = ConflictException(
            AppErrorCode.POLICY_NOT_SIGNABLE,
        )
        with pytest.raises(ConflictException) as exc:
            sign_onboarding_privacy(
                user_id=uuid4(),
                company_id=uuid4(),
                content=_content(),
                context=SignPolicyContextSchema(),
            )
    assert exc.value.code == AppErrorCode.POLICY_NOT_SIGNABLE
