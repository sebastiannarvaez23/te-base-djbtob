"""Apply migrations on ``DATABASES['analytics']`` (wadw).

django-tenants replaces ``migrate`` with ``migrate_schemas``, which calls
``connection.set_schema`` and only works on the tenants backend. The
analytics alias uses stock Postgres — use this command instead::

    python manage.py migrate_analytics

Only the ``analytics_ctl`` app is migrated by default. Passing extra app
labels is allowed for future analytics apps, but OLTP apps are still
blocked by ``AnalyticsRouter``.
"""

from __future__ import annotations

from django.core.management.commands.migrate import Command as DjangoMigrateCommand

from core.analytics.infrastructure.db_router import ANALYTICS_DB_ALIAS

_DEFAULT_APPS = ('analytics_ctl',)


class Command(DjangoMigrateCommand):
    help = 'Run Django migrations against the analytics database (wadw).'

    def handle(self, *args, **options):
        options['database'] = ANALYTICS_DB_ALIAS
        # Avoid recording every OLTP migration as "applied" on wadw
        # (Django marks migrations applied even when all ops are skipped).
        if not args:
            args = _DEFAULT_APPS
        return super().handle(*args, **options)
