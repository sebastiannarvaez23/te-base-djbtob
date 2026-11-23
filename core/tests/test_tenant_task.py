"""Unit tests for ``core.tasks.base.TenantTask``.

``TenantTask`` is the base class for jobs that run inside a tenant
schema. The contract is narrow but easy to break:

  * Callers pass ``schema_name`` as a kwarg.
  * The class pops that kwarg (it must NOT leak into the task body —
    use cases stay free of django-tenants knowledge).
  * Execution is wrapped in :func:`schema_context` so the ORM resolves
    against the tenant's schema for the duration of the call.
  * If ``schema_name`` is omitted the task runs in the public schema
    (no schema_context wrap) — useful for cross-tenant maintenance.

We verify these by patching ``schema_context`` so the test never needs
django-tenants' real connection wiring.
"""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from contextlib import contextmanager
from unittest import TestCase, mock

from celery import Celery

from core.tasks.base import TenantTask


def _build_task(observer):
    """Create a one-off Celery task bound to ``TenantTask`` so each
    test can inspect what was passed to the body. We run inside a
    standalone Celery app so registration does not pollute the main
    ``base`` app's task registry."""
    app = Celery('test-tenanttask')

    @app.task(base=TenantTask, name=f'test.tenant_task.{id(observer)}')
    def _job(*args, **kwargs):
        observer['called_with'] = {'args': args, 'kwargs': kwargs}
        return 'ok'

    return _job


class TestTenantTask(TestCase):

    def setUp(self):
        # Replace schema_context with a recording no-op CM so we can
        # assert which schema the wrap was entered with — without
        # touching django-tenants connection state.
        self.entered_schemas: list = []

        @contextmanager
        def _fake_schema_context(schema):
            self.entered_schemas.append(schema)
            yield

        patcher = mock.patch(
            'core.tasks.base.schema_context', side_effect=_fake_schema_context,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_pops_schema_name_before_calling_body(self):
        """The body must NOT receive ``schema_name`` — leaving it in
        kwargs would force every use case to ignore it manually, which
        defeats the abstraction."""
        observed: dict = {}
        job = _build_task(observed)

        job.apply(kwargs={'schema_name': 'acme', 'payload': 42}).get()

        self.assertNotIn('schema_name', observed['called_with']['kwargs'])
        self.assertEqual(observed['called_with']['kwargs'], {'payload': 42})

    def test_wraps_body_in_schema_context_for_given_tenant(self):
        """The schema name passed by the caller must be the one fed
        to ``schema_context`` — a regression here would silently run
        the job in the wrong tenant."""
        observed: dict = {}
        job = _build_task(observed)

        job.apply(kwargs={'schema_name': 'acme'}).get()

        self.assertEqual(self.entered_schemas, ['acme'])

    def test_no_schema_name_runs_without_schema_context(self):
        """Omitting ``schema_name`` is the documented escape hatch for
        cross-tenant / public-schema jobs. The wrap MUST be skipped —
        entering ``schema_context(None)`` would error inside
        django-tenants."""
        observed: dict = {}
        job = _build_task(observed)

        job.apply(kwargs={'payload': 'x'}).get()

        self.assertEqual(self.entered_schemas, [])
        self.assertEqual(observed['called_with']['kwargs'], {'payload': 'x'})

    def test_positional_args_pass_through(self):
        """``schema_name`` is a kwarg by contract; positional args
        must reach the body untouched."""
        observed: dict = {}
        job = _build_task(observed)

        job.apply(args=(1, 2, 3), kwargs={'schema_name': 'acme'}).get()

        self.assertEqual(observed['called_with']['args'], (1, 2, 3))
