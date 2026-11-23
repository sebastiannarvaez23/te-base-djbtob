"""
Shared DATABASES builders for OLTP (default) and analytics (wadw).

``DW_*`` defaults to the same host/credentials as ``DB_*`` in local so a
second database on the same Postgres container is zero-config. Production
can point ``DW_HOST`` at a dedicated instance without touching OLTP.
"""

from __future__ import annotations

from typing import Any


def build_default_database(env) -> dict[str, Any]:
    return {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': env.str('DB_NAME'),
        'USER': env.str('DB_USER'),
        'PASSWORD': env.str('DB_PASSWORD'),
        'HOST': env.str('DB_HOST'),
        'PORT': env.str('DB_PORT'),
        'CHARSET': 'UTF8',
    }


def build_analytics_database(env) -> dict[str, Any]:
    """Alias ``analytics`` → physical DB ``wadw`` (not django-tenants)."""
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env.str('DW_NAME', default='wadw'),
        'USER': env.str('DW_USER', default=env.str('DB_USER')),
        'PASSWORD': env.str('DW_PASSWORD', default=env.str('DB_PASSWORD')),
        'HOST': env.str('DW_HOST', default=env.str('DB_HOST')),
        'PORT': env.str('DW_PORT', default=env.str('DB_PORT')),
        'CHARSET': 'UTF8',
        # Conservative pool; analytics workers can raise later if needed.
        'CONN_MAX_AGE': env.int('DW_CONN_MAX_AGE', default=60),
        # Unqualified ORM names resolve across ctl / dw / stg.
        'OPTIONS': {
            'options': '-c search_path=ctl,dw,stg,public',
        },
        # The test runner migrates every alias with ``migrate``, which
        # django-tenants replaces by ``migrate_schemas`` (tenant backend only).
        'TEST': {'MIRROR': 'default'},
    }
