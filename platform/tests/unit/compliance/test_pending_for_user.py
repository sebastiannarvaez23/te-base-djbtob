"""Unit tests for pending_policies_for_user helper."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from platform.features.compliance.policy.policy.application.pending_for_user import (
    pending_policies_for_user,
)
from platform.features.compliance.policy.policy.domain.schemas import PendingPolicySchema
from platform.features.compliance.policy.policy.domain.enums import PolicyAudience


@pytest.mark.unit
def test_pending_empty_when_country_unresolved():
    user = MagicMock()
    user.company = MagicMock(country='Narnia')
    with patch(
        'platform.features.compliance.policy.policy.application.pending_for_user'
        '.resolve_company_policy_country',
        return_value=None,
    ):
        items, country = pending_policies_for_user(user)
    assert items == []
    assert country is None


@pytest.mark.unit
def test_pending_delegates_list_use_case():
    user = MagicMock()
    user.id = uuid4()
    user.company_id = uuid4()
    pending = [
        PendingPolicySchema(
            policy_id=uuid4(),
            code='PRIVACY-POLICY',
            name='Privacy',
            audience=PolicyAudience.CLIENT,
            country='CO',
            version=2,
            title='Privacy v2',
            content_hash='a' * 64,
            policy_country_id=uuid4(),
        ),
    ]
    with patch(
        'platform.features.compliance.policy.policy.application.pending_for_user'
        '.resolve_company_policy_country',
        return_value='CO',
    ), patch(
        'platform.features.compliance.policy.policy.application.pending_for_user'
        '.ListPendingPoliciesUseCase',
    ) as list_cls, patch(
        'platform.features.compliance.policy.policy.application.pending_for_user'
        '.DjangoPolicySignatureRepository',
    ), patch(
        'platform.features.compliance.policy.policy.application.pending_for_user'
        '.get_client_login_required_policy_codes',
        return_value=('PRIVACY-POLICY',),
    ):
        list_cls.return_value.execute.return_value = pending
        items, country = pending_policies_for_user(user)

    assert country == 'CO'
    assert items == pending
    kwargs = list_cls.return_value.execute.call_args.kwargs
    assert kwargs['country'] == 'CO'
    assert kwargs['subject'].subject_id == str(user.id)
    assert kwargs['policy_codes'] == ('PRIVACY-POLICY',)
