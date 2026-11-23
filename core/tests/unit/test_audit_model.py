"""Auditoría de fila: campos abstractos pasivos."""

import pytest
from django.db import models

from core.models.audit import AuditModel

pytestmark = pytest.mark.unit


def test_audit_model_is_abstract():
    assert AuditModel._meta.abstract is True


def test_audit_model_declares_row_audit_fields():
    names = {field.name for field in AuditModel._meta.local_fields}
    assert names == {'created_at', 'updated_at', 'created_by'}


def test_created_by_is_nullable_uuid():
    field = AuditModel._meta.get_field('created_by')
    assert isinstance(field, models.UUIDField)
    assert field.null is True
    assert field.blank is True


def test_updated_at_uses_auto_now():
    field = AuditModel._meta.get_field('updated_at')
    assert isinstance(field, models.DateTimeField)
    assert field.auto_now is True
