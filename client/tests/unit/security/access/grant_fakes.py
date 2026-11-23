"""Fakes en memoria del L4 entity_grants (sin DB)."""
import uuid

from client.features.security.access.entity_grants.domain.interfaces import (
    ICompanyUserDirectory,
    IEntityGrantRepository,
    IGrantableCatalog,
    IGrantScopeInvalidator,
)
from client.features.security.access.entity_grants.domain.schemas import (
    GrantAxis,
    GrantDiff,
    entity_type_key,
)

COMPANY = uuid.uuid4()
ADMIN = uuid.uuid4()
USER = uuid.uuid4()
OTHER_USER = uuid.uuid4()
FOREIGN_USER = uuid.uuid4()
NORTH = uuid.uuid4()
SOUTH = uuid.uuid4()
GONE = uuid.uuid4()


class FakeRepository(IEntityGrantRepository):
    """Filas ``(user_id, entity_type, entity_id)``."""

    def __init__(self):
        self.rows: set[tuple[uuid.UUID, str, uuid.UUID]] = set()

    @staticmethod
    def _row(scope, value):
        if scope.axis is GrantAxis.USER:
            return scope.key_id, entity_type_key(scope.entity_type), value
        return value, entity_type_key(scope.entity_type), scope.key_id

    def list_ids(self, scope):
        kind = entity_type_key(scope.entity_type)
        if scope.axis is GrantAxis.USER:
            return {e for u, t, e in self.rows if u == scope.key_id and t == kind}
        return {u for u, t, e in self.rows if e == scope.key_id and t == kind}

    def replace(self, scope, ids, granted_by):
        current, wanted = self.list_ids(scope), set(ids)
        self.rows -= {self._row(scope, item) for item in current - wanted}
        self.rows |= {self._row(scope, item) for item in wanted - current}
        return GrantDiff(added=sorted(wanted - current, key=str), removed=sorted(current - wanted, key=str))

    def granted_keys(self, entity_type, axis):
        rows = [(u, e) for u, t, e in self.rows if t == entity_type_key(entity_type)]
        return {u for u, _ in rows} if axis is GrantAxis.USER else {e for _, e in rows}

    def delete_keys(self, entity_type, user_ids, entity_ids):
        users, entities = set(user_ids), set(entity_ids)
        doomed = {
            row for row in self.rows
            if row[1] == entity_type_key(entity_type) and (row[0] in users or row[2] in entities)
        }
        self.rows -= doomed
        return len(doomed)


class FakeCatalog(IGrantableCatalog):
    def __init__(self):
        self.calls = 0

    def existing_ids(self, ids):
        self.calls += 1
        return {item for item in ids if item in {NORTH, SOUTH}}


class FakeDirectory(ICompanyUserDirectory):
    def __init__(self):
        self.calls = 0

    def member_ids(self, company_id, ids):
        self.calls += 1
        members = {ADMIN, USER, OTHER_USER} if company_id == COMPANY else set()
        return {item for item in ids if item in members}


class SpyInvalidator(IGrantScopeInvalidator):
    def __init__(self):
        self.calls: list[tuple[set, object]] = []

    def invalidate(self, user_ids, entity_type):
        self.calls.append((set(user_ids), entity_type))
