"""Cancelar la suscripción no suspende la empresa mientras end_date no venció."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import TestCase

import pytest
from django.utils import timezone

from core.access.entitlement import acquisition_grants_access, entitled_acquisition_q

pytestmark = pytest.mark.unit


def _acquisition(status, end_date=None):
    class Row:
        pass

    row = Row()
    row.status = status
    row.end_date = end_date
    return row


class TestAcquisitionGrantsAccess(TestCase):

    def test_active_grants_access(self):
        self.assertTrue(acquisition_grants_access(_acquisition('active')))

    def test_cancelled_before_end_date_grants_access(self):
        end = timezone.now() + timedelta(days=4)
        self.assertTrue(acquisition_grants_access(_acquisition('cancelled', end)))

    def test_cancelled_after_end_date_denies_access(self):
        end = timezone.now() - timedelta(days=1)
        self.assertFalse(acquisition_grants_access(_acquisition('cancelled', end)))

    def test_cancelled_without_end_date_denies_access(self):
        self.assertFalse(acquisition_grants_access(_acquisition('cancelled')))

    def test_suspended_does_not_grant_full_access(self):
        end = timezone.now() + timedelta(days=4)
        self.assertFalse(acquisition_grants_access(_acquisition('suspended', end)))

    def test_missing_acquisition_denies_access(self):
        self.assertFalse(acquisition_grants_access(None))


class TestEntitledAcquisitionQuery(TestCase):

    def test_includes_active_and_open_cancellation(self):
        moment = datetime(2026, 11, 11, tzinfo=dt_timezone.utc)
        rendered = str(entitled_acquisition_q(moment))
        self.assertIn('ACTIVE', rendered)
        self.assertIn('CANCELLED', rendered)
        self.assertIn('end_date__gt', rendered)
