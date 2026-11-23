"""Unit tests — firma obligatoria de COMPANY-DEREGISTRATION en el self-close."""

from __future__ import annotations

import uuid
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.application.deregistration_policy import (
    RequireDeregistrationPolicySignatureUseCase,
)
from platform.features.company.tenant.company.domain.lifecycle import (
    COMPANY_DEREGISTRATION_POLICY_CODE,
)
from platform.features.compliance.policy.policy.domain.enums import (
    PolicyAudience,
    PolicyCountryStatus,
)

pytestmark = pytest.mark.unit

ACTOR_ID = uuid.uuid4()
COMPANY_ID = uuid.uuid4()
POLICY_ID = uuid.uuid4()
COUNTRY_ID = uuid.uuid4()


def _policy(**overrides):
    payload = dict(
        id=POLICY_ID,
        is_active=True,
        audience=PolicyAudience.CLIENT,
    )
    payload.update(overrides)
    return MagicMock(**payload)


def _country(**overrides):
    payload = dict(
        id=COUNTRY_ID,
        status=PolicyCountryStatus.PUBLISHED,
        content_hash='hash-1',
    )
    payload.update(overrides)
    return MagicMock(**payload)


class TestRequireDeregistrationPolicySignatureUseCase(TestCase):
    def setUp(self):
        self.policies = MagicMock()
        self.signatures = MagicMock()
        self.use_case = RequireDeregistrationPolicySignatureUseCase(
            self.policies, self.signatures,
        )

    def _execute(self, country='CO'):
        return self.use_case.execute(
            actor_user_id=ACTOR_ID,
            company_id=COMPANY_ID,
            country=country,
        )

    def test_passes_when_current_version_is_signed(self):
        self.policies.get_by_code.return_value = _policy()
        self.policies.get_country.return_value = _country()
        self.signatures.find_for_version.return_value = MagicMock()
        self._execute()
        self.policies.get_by_code.assert_called_once_with(COMPANY_DEREGISTRATION_POLICY_CODE)
        self.policies.get_country.assert_called_once_with(POLICY_ID, 'CO')
        kwargs = self.signatures.find_for_version.call_args.kwargs
        self.assertEqual(kwargs['policy_country_id'], COUNTRY_ID)
        self.assertEqual(kwargs['content_hash'], 'hash-1')
        self.assertEqual(kwargs['subject'].subject_id, str(ACTOR_ID))
        self.assertEqual(kwargs['subject'].tenant_id, str(COMPANY_ID))

    def test_rejects_missing_country(self):
        with self.assertRaises(ValidationAppException) as ctx:
            self._execute(country=None)
        self.assertEqual(ctx.exception.code, AppErrorCode.POLICY_INVALID_COUNTRY)
        self.policies.get_by_code.assert_not_called()

    def test_rejects_missing_policy(self):
        self.policies.get_by_code.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self._execute()
        self.assertEqual(ctx.exception.code, AppErrorCode.POLICY_NOT_FOUND)

    def test_rejects_unpublished_country(self):
        self.policies.get_by_code.return_value = _policy()
        self.policies.get_country.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self._execute()
        self.assertEqual(ctx.exception.code, AppErrorCode.POLICY_COUNTRY_NOT_FOUND)

    def test_rejects_non_published_status(self):
        self.policies.get_by_code.return_value = _policy()
        self.policies.get_country.return_value = _country(status=PolicyCountryStatus.DRAFT)
        with self.assertRaises(ConflictException) as ctx:
            self._execute()
        self.assertEqual(ctx.exception.code, AppErrorCode.POLICY_NOT_SIGNABLE)

    def test_rejects_unsigned_current_version(self):
        self.policies.get_by_code.return_value = _policy()
        self.policies.get_country.return_value = _country()
        self.signatures.find_for_version.return_value = None
        with self.assertRaises(ValidationAppException) as ctx:
            self._execute()
        self.assertEqual(ctx.exception.code, AppErrorCode.COMPANY_CLOSE_POLICY_REQUIRED)
