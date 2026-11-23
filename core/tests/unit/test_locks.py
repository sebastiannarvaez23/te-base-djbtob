from unittest.mock import MagicMock, patch

import pytest

from core import locks
from core.locks import advisory_lock_key, advisory_xact_lock

pytestmark = pytest.mark.unit


def test_lock_key_is_stable_signed_int64():
    key = advisory_lock_key('tenant_a', 'entity_grants', 'warehouse')

    assert key == advisory_lock_key('tenant_a', 'entity_grants', 'warehouse')
    assert -(2 ** 63) <= key < 2 ** 63


def test_lock_key_differs_per_tenant_and_scope():
    keys = {
        advisory_lock_key('tenant_a', 'entity_grants', 'warehouse'),
        advisory_lock_key('tenant_b', 'entity_grants', 'warehouse'),
        advisory_lock_key('tenant_a', 'entity_grants', 'zone'),
    }
    assert len(keys) == 3


def _connection(vendor='postgresql', atomic=True, schema='tenant_a'):
    conn = MagicMock(vendor=vendor, in_atomic_block=atomic, schema_name=schema)
    cursor = conn.cursor.return_value.__enter__.return_value
    return conn, cursor


def test_takes_the_postgres_lock_with_the_tenant_key():
    conn, cursor = _connection()
    with patch.object(locks, 'connection', conn):
        advisory_xact_lock('entity_grants', 'warehouse')

    cursor.execute.assert_called_once_with(
        'SELECT pg_advisory_xact_lock(%s)',
        [advisory_lock_key('tenant_a', 'entity_grants', 'warehouse')],
    )


def test_falls_back_to_public_schema():
    conn, cursor = _connection(schema=None)
    with patch.object(locks, 'connection', conn):
        advisory_xact_lock('ns')

    assert cursor.execute.call_args.args[1] == [advisory_lock_key('public', 'ns')]


def test_requires_an_atomic_block():
    conn, _ = _connection(atomic=False)
    with patch.object(locks, 'connection', conn), pytest.raises(RuntimeError):
        advisory_xact_lock('ns')


def test_is_a_noop_outside_postgres():
    conn, cursor = _connection(vendor='sqlite')
    with patch.object(locks, 'connection', conn):
        advisory_xact_lock('ns')

    cursor.execute.assert_not_called()
