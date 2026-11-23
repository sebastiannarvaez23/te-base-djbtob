"""Unit tests for public published-policy lookup by code."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, NotFoundException
from platform.features.compliance.policy.policy.application.public_use_cases import (
    GetPublishedPolicyByCodeUseCase,
)
from platform.features.compliance.policy.policy.domain.enums import (
    PolicyAudience,
    PolicyCountryStatus,
)


def _run(repo, storage, code='PRIVACY-POLICY', country='CO', content=None):
    use_case = GetPublishedPolicyByCodeUseCase(repo, storage)
    with patch(
        'platform.features.compliance.policy.policy.application.public_use_cases'
        '.GetPolicyCountryContentUseCase',
    ) as content_cls:
        if content is not None:
            content_cls.return_value.execute.return_value = content
        return use_case.execute(code, country), content_cls


@pytest.mark.unit
def test_published_by_code_happy_path():
    policy_id = uuid4()
    policy = MagicMock(
        id=policy_id,
        code='PRIVACY-POLICY',
        is_active=True,
        audience=PolicyAudience.CLIENT,
    )
    content = MagicMock(
        policy_id=policy_id,
        status=PolicyCountryStatus.PUBLISHED,
        markdown='# Hi',
    )
    repo = MagicMock()
    repo.get_by_code.return_value = policy

    result, content_cls = _run(repo, MagicMock(), code='privacy-policy', country='co', content=content)

    assert result is content
    repo.get_by_code.assert_called_once_with('PRIVACY-POLICY')
    content_cls.return_value.execute.assert_called_once_with(policy_id, 'CO')


@pytest.mark.unit
def test_published_by_code_invalid_code():
    with pytest.raises(NotFoundException) as exc:
        GetPublishedPolicyByCodeUseCase(MagicMock(), MagicMock()).execute(
            'not valid!!', 'CO',
        )
    assert exc.value.code == AppErrorCode.POLICY_NOT_FOUND


@pytest.mark.unit
def test_published_by_code_invalid_country():
    with pytest.raises(NotFoundException) as exc:
        GetPublishedPolicyByCodeUseCase(MagicMock(), MagicMock()).execute(
            'PRIVACY-POLICY', 'Colombia',
        )
    assert exc.value.code == AppErrorCode.POLICY_NOT_FOUND


@pytest.mark.unit
def test_published_by_code_not_found():
    repo = MagicMock()
    repo.get_by_code.return_value = None
    with pytest.raises(NotFoundException) as exc:
        GetPublishedPolicyByCodeUseCase(repo, MagicMock()).execute(
            'PRIVACY-POLICY', 'CO',
        )
    assert exc.value.code == AppErrorCode.POLICY_NOT_FOUND


@pytest.mark.unit
def test_published_by_code_inactive_or_wrong_audience():
    repo = MagicMock()
    repo.get_by_code.return_value = MagicMock(
        is_active=False,
        audience=PolicyAudience.CLIENT,
    )
    with pytest.raises(NotFoundException) as exc:
        GetPublishedPolicyByCodeUseCase(repo, MagicMock()).execute(
            'PRIVACY-POLICY', 'CO',
        )
    assert exc.value.code == AppErrorCode.POLICY_NOT_FOUND

    repo.get_by_code.return_value = MagicMock(
        is_active=True,
        audience=PolicyAudience.ADMIN,
    )
    with pytest.raises(NotFoundException) as exc2:
        GetPublishedPolicyByCodeUseCase(repo, MagicMock()).execute(
            'PRIVACY-POLICY', 'CO',
        )
    assert exc2.value.code == AppErrorCode.POLICY_NOT_FOUND


@pytest.mark.unit
def test_published_by_code_rejects_non_published_status():
    policy_id = uuid4()
    repo = MagicMock()
    repo.get_by_code.return_value = MagicMock(
        id=policy_id,
        is_active=True,
        audience=PolicyAudience.CLIENT,
    )
    content = MagicMock(status=PolicyCountryStatus.DRAFT)

    with pytest.raises(NotFoundException) as exc:
        _run(repo, MagicMock(), content=content)
    assert exc.value.code == AppErrorCode.POLICY_COUNTRY_NOT_FOUND
