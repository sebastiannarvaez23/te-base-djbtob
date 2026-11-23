"""Unit tests del factory de casos de uso de incidencias."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

from platform.features.support.incidents.incident.application.factory import (
    build_report_task_failure_use_case,
    build_report_use_case,
)
from platform.features.support.incidents.incident.application.report_incident import ReportIncidentUseCase
from platform.features.support.incidents.incident.application.report_task_failure import (
    ReportTaskFailureUseCase,
)


class IncidentFactoryTests(TestCase):

    def test_build_report_use_case_returns_configured_instance(self):
        uc = build_report_use_case()
        self.assertIsInstance(uc, ReportIncidentUseCase)
        self.assertIsNotNone(uc._repo)
        self.assertIsNotNone(uc._draft_store)
        self.assertIsNotNone(uc._notifier)
        self.assertIsNotNone(uc._feature_resolver)

    def test_build_report_task_failure_use_case_returns_configured_instance(self):
        uc = build_report_task_failure_use_case()
        self.assertIsInstance(uc, ReportTaskFailureUseCase)
        self.assertIsNotNone(uc._repo)
        self.assertIsNotNone(uc._notifier)
