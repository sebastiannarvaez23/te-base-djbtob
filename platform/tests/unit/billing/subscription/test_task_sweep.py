"""Tests del andamiaje compartido ``run_company_sweep`` (capa de tareas):
lock por-empresa, mapeo de outcomes a buckets y aislamiento de fallos. El lock
de Redis se parchea — sin Redis, sin BD, sin Celery."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from platform.features.billing.subscription.subscription.tasks._common import run_company_sweep

_LOCK = 'platform.features.billing.subscription.subscription.tasks._common.redis_lock'


def _task(name='subscription.test'):
    return SimpleNamespace(name=name, request=SimpleNamespace(id='task-1'))


def _lock(acquired=True):
    @contextmanager
    def _cm(*args, **kwargs):
        yield acquired
    return _cm


class TestRunCompanySweep(TestCase):

    def test_tallies_outcomes_into_buckets(self):
        outcomes = {'a': 'renewed', 'b': 'renewed', 'c': 'not_due'}
        with patch(_LOCK, _lock(acquired=True)):
            result = run_company_sweep(
                _task(), ['a', 'b', 'c'],
                process=lambda cid: outcomes[cid],
                tally=lambda o: 'noop' if o == 'not_due' else o,
            )
        self.assertEqual(result['due'], 3)
        self.assertEqual(result['renewed'], 2)
        self.assertEqual(result['noop'], 1)

    def test_isolates_per_company_failures(self):
        def process(cid):
            if cid == 'b':
                raise RuntimeError('boom')
            return 'ok'

        with patch(_LOCK, _lock(acquired=True)):
            result = run_company_sweep(
                _task(), ['a', 'b', 'c'], process=process, tally=lambda o: o,
            )
        # b failed but a and c still processed.
        self.assertEqual(result['due'], 3)
        self.assertEqual(result['ok'], 2)
        self.assertEqual(result['failed'], 1)

    def test_skips_companies_whose_lock_is_held(self):
        process = MagicMock()
        with patch(_LOCK, _lock(acquired=False)):
            result = run_company_sweep(
                _task(), ['a', 'b'], process=process, tally=lambda o: o,
            )
        process.assert_not_called()
        self.assertEqual(result, {'due': 2, 'skipped_locked': 2})
