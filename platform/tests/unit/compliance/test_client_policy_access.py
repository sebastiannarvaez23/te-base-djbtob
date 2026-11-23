"""Unit tests — acceso client a políticas (audiencia tenant)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, NotFoundException
from core.signing import hash_content
from platform.features.compliance.policy.policy.application.client_use_cases import (
    GetClientPolicyCountryContentUseCase,
    RequireActiveClientPolicyUseCase,
)
from platform.features.compliance.policy.policy.domain.enums import PolicyAudience
from platform.features.compliance.policy.policy.domain.schemas import (
    PolicyCountryContentSchema,
    PolicySchema,
)

pytestmark = pytest.mark.unit


def _policy(**overrides) -> PolicySchema:
    base = dict(
        id=uuid4(),
        code='DATA-PROCESSING',
        name='Datos',
        audience=PolicyAudience.CLIENT,
        description='',
        is_active=True,
        countries=[],
        drafts=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return PolicySchema(**base)


class TestRequireActiveClientPolicy:

    def test_ok_for_active_client(self):
        repo = MagicMock()
        policy = _policy()
        repo.get_by_id.return_value = policy
        assert RequireActiveClientPolicyUseCase(repo).execute(policy.id).id == policy.id

    def test_hides_admin_audience(self):
        repo = MagicMock()
        repo.get_by_id.return_value = _policy(audience=PolicyAudience.ADMIN)
        with pytest.raises(NotFoundException) as exc:
            RequireActiveClientPolicyUseCase(repo).execute(uuid4())
        assert exc.value.code == AppErrorCode.POLICY_NOT_FOUND

    def test_hides_inactive(self):
        repo = MagicMock()
        repo.get_by_id.return_value = _policy(is_active=False)
        with pytest.raises(NotFoundException):
            RequireActiveClientPolicyUseCase(repo).execute(uuid4())

    def test_missing(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            RequireActiveClientPolicyUseCase(repo).execute(uuid4())


class TestGetClientPolicyCountryContent:

    def test_delegates_after_audience_check(self, monkeypatch):
        repo = MagicMock()
        storage = MagicMock()
        policy = _policy()
        repo.get_by_id.return_value = policy
        expected = PolicyCountryContentSchema(
            policy_id=policy.id,
            policy_code=policy.code,
            audience=PolicyAudience.CLIENT,
            country='CO',
            version=1,
            status='published',
            title='Datos',
            markdown='# hi',
            object_key='client/policies/DATA-PROCESSING/CO/v1.md',
            content_hash=hash_content(b'# hi'),
            byte_size=4,
        )

        from platform.features.compliance.policy.policy.application import use_cases as uc

        monkeypatch.setattr(
            uc.GetPolicyCountryContentUseCase,
            'execute',
            lambda self, pid, country: expected,
        )
        result = GetClientPolicyCountryContentUseCase(repo, storage).execute(policy.id, 'CO')
        assert result.markdown == '# hi'

    def test_blocks_admin_before_download(self):
        repo = MagicMock()
        storage = MagicMock()
        repo.get_by_id.return_value = _policy(audience=PolicyAudience.ADMIN)
        with pytest.raises(NotFoundException):
            GetClientPolicyCountryContentUseCase(repo, storage).execute(uuid4(), 'CO')
        storage.download_file.assert_not_called()
