"""
core/locks.py
─────────────
Locks transaccionales de PostgreSQL acotados al schema del tenant.

``advisory_xact_lock('entity_grants', 'warehouse')`` serializa las escrituras de
ese ámbito hasta el COMMIT/ROLLBACK, sin bloquear filas (sirve también cuando el
conjunto está vacío, donde ``select_for_update`` no bloquea nada).
"""

from __future__ import annotations

import hashlib

from django.db import connection


def advisory_lock_key(schema: str, namespace: str, *parts: object) -> int:
    """Clave estable signed 64-bit; incluye el schema para no cruzar tenants."""
    raw = ':'.join([schema, namespace, *(str(part) for part in parts)])
    digest = hashlib.sha256(raw.encode()).digest()
    return int.from_bytes(digest[:8], 'big', signed=True)


def advisory_xact_lock(namespace: str, *parts: object) -> None:
    """Debe llamarse dentro de ``transaction.atomic()``."""
    if not connection.in_atomic_block:
        raise RuntimeError('advisory_xact_lock requires an atomic block')
    if connection.vendor != 'postgresql':
        return
    schema = getattr(connection, 'schema_name', None) or 'public'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT pg_advisory_xact_lock(%s)',
            [advisory_lock_key(schema, namespace, *parts)],
        )
