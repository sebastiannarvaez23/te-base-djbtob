"""EnsureModelTable: crea la tabla heredada solo si falta."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.migration_operations import EnsureModelTable

pytestmark = pytest.mark.unit


def _editor(tables):
    connection = MagicMock(alias='default')
    connection.introspection.table_names.return_value = tables
    return MagicMock(connection=connection)


def _state(model):
    return SimpleNamespace(apps=SimpleNamespace(get_model=lambda app, name: model))


def _model(table='security_logs'):
    return SimpleNamespace(_meta=SimpleNamespace(db_table=table))


def test_creates_missing_table():
    op, editor, model = EnsureModelTable('SecurityLog'), _editor(['other']), _model()
    with patch.object(EnsureModelTable, 'allow_migrate_model', return_value=True):
        op.database_forwards('logging_security', editor, None, _state(model))
    editor.create_model.assert_called_once_with(model)


def test_skips_existing_table():
    op, editor = EnsureModelTable('SecurityLog'), _editor(['security_logs'])
    with patch.object(EnsureModelTable, 'allow_migrate_model', return_value=True):
        op.database_forwards('logging_security', editor, None, _state(_model()))
    editor.create_model.assert_not_called()


def test_respects_router():
    op, editor = EnsureModelTable('AuditLog'), _editor([])
    with patch.object(EnsureModelTable, 'allow_migrate_model', return_value=False):
        op.database_forwards('logging_audit', editor, None, _state(_model('audit_logs')))
    editor.create_model.assert_not_called()
    editor.connection.introspection.table_names.assert_not_called()


def test_backwards_never_drops_and_state_is_untouched():
    op, editor = EnsureModelTable('AuditLog'), _editor([])
    state = MagicMock()
    op.state_forwards('logging_audit', state)
    op.database_backwards('logging_audit', editor, None, None)
    assert not state.method_calls
    assert not editor.method_calls


def test_describes_and_deconstructs():
    op = EnsureModelTable('AuditLog')
    assert op.deconstruct() == ('EnsureModelTable', ['AuditLog'], {})
    assert op.describe() == 'Ensure table for AuditLog exists'
    assert op.migration_name_fragment == 'ensure_auditlog_table'
