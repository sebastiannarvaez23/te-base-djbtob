"""ExpirePeriodUseCase and the lazy Celery task that wraps it."""
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from platform.features.billing.subscription.subscription.application.expire_period import (
    ExpirePeriodUseCase,
)
from platform.features.billing.subscription.subscription.tasks.expire import (
    expire_subscription_for_company,
)

pytestmark = pytest.mark.unit


def test_expire_period_delegates_to_repo_with_company():
    repo = MagicMock()
    repo.expire_due.return_value = 2
    company_id = uuid.uuid4()
    assert ExpirePeriodUseCase(repo).execute(company_id) == 2
    repo.expire_due.assert_called_once_with(company_id)


def test_expire_period_without_company_sweeps_all():
    repo = MagicMock()
    repo.expire_due.return_value = 5
    assert ExpirePeriodUseCase(repo).execute() == 5
    repo.expire_due.assert_called_once_with(None)


def _lock(acquired):
    @contextmanager
    def _cm(*args, **kwargs):
        yield acquired
    return _cm


@patch('platform.features.billing.subscription.subscription.tasks.expire._build_use_case')
@patch('platform.features.billing.subscription.subscription.tasks.expire.redis_lock')
def test_expire_task_skips_when_lock_held(mock_lock, mock_build):
    mock_lock.side_effect = _lock(False)
    result = expire_subscription_for_company.run(str(uuid.uuid4()))
    assert result == {'skipped': True}
    mock_build.assert_not_called()


@patch('platform.features.billing.subscription.subscription.tasks.expire._build_use_case')
@patch('platform.features.billing.subscription.subscription.tasks.expire.redis_lock')
def test_expire_task_runs_use_case(mock_lock, mock_build):
    mock_lock.side_effect = _lock(True)
    uc = MagicMock()
    uc.execute.return_value = 1
    mock_build.return_value = uc
    company_id = str(uuid.uuid4())
    result = expire_subscription_for_company.run(company_id)
    uc.execute.assert_called_once_with(company_id)
    assert result == {'expired': 1}


@patch('platform.features.billing.subscription.subscription.tasks.expire._build_use_case')
@patch('platform.features.billing.subscription.subscription.tasks.expire.redis_lock')
def test_expire_task_reraises_use_case_failure(mock_lock, mock_build):
    mock_lock.side_effect = _lock(True)
    mock_build.return_value.execute.side_effect = RuntimeError('db down')
    with pytest.raises(RuntimeError, match='db down'):
        expire_subscription_for_company.run(str(uuid.uuid4()))
