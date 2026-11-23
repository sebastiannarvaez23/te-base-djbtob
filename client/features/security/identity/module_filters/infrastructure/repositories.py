from typing import NoReturn, Optional
from uuid import UUID

from django.db import IntegrityError, transaction

from core.errors import AppErrorCode, ConflictException, NotFoundException
from core.locks import advisory_xact_lock
from client.features.security.identity.module_filters.domain.interfaces import (
    IModuleFilterRepository,
)
from client.features.security.identity.module_filters.domain.schemas import (
    MAX_FILTERS_PER_MODULE,
    FilterCriteria,
    ModuleFilterInput,
    ModuleFilterRecord,
    ModuleKey,
)
from client.features.security.identity.module_filters.models import ModuleFilter

# Filas legacy previas al rename location → warehouse (command + lectura tolerante).
_LEGACY_MODULE_KEYS: dict[str, ModuleKey] = {
    'location': ModuleKey.WAREHOUSE,
}


def _coerce_module_key(raw: str) -> ModuleKey:
    if raw in _LEGACY_MODULE_KEYS:
        return _LEGACY_MODULE_KEYS[raw]
    return ModuleKey(raw)


def _stored_module_keys(module_key: ModuleKey) -> tuple[str, ...]:
    if module_key is ModuleKey.WAREHOUSE:
        return (ModuleKey.WAREHOUSE.value, 'location')
    return (module_key.value,)


def _record(obj: ModuleFilter) -> ModuleFilterRecord:
    return ModuleFilterRecord(
        id=obj.id,
        module_key=_coerce_module_key(obj.module_key),
        name=obj.name,
        criteria=FilterCriteria(**(obj.criteria or {})),
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _normalize_legacy_key(obj: ModuleFilter) -> list[str]:
    """Reescribe ``location`` → ``warehouse`` en la fila al tocarla."""
    if obj.module_key != 'location':
        return []
    obj.module_key = ModuleKey.WAREHOUSE.value
    return ['module_key']


def _criteria_json(criteria: FilterCriteria) -> dict:
    return criteria.model_dump(mode='json')


def _duplicate_name(name: str) -> ConflictException:
    return ConflictException(AppErrorCode.MFLT_DUPLICATE_NAME, context={'name': name})


def _limit_reached() -> ConflictException:
    return ConflictException(
        AppErrorCode.MFLT_LIMIT_REACHED,
        context={'limit': MAX_FILTERS_PER_MODULE},
    )


def _missing(filter_id: UUID) -> NotFoundException:
    return NotFoundException(AppErrorCode.MFLT_NOT_FOUND, context={'filter_id': str(filter_id)})


def name_conflict_or_none(exc: IntegrityError, name: str) -> Optional[ConflictException]:
    """Map the case-insensitive name constraint. Other constraints stay unexpected."""
    if 'mflt_user_module_name' in str(exc).lower():
        return _duplicate_name(name)
    return None


def _lock_scope(user_id: UUID, module_key: str) -> None:
    """Serialize writes for one user and module, including the first insert.

    ``select_for_update`` locks nothing when the set is empty, so two creates
    could both pass the cap. The transaction-scoped advisory lock closes that gap.
    """
    advisory_xact_lock('module_filters', user_id, module_key)


def _reraise_integrity(exc: IntegrityError, name: str) -> NoReturn:
    conflict = name_conflict_or_none(exc, name)
    if conflict is not None:
        raise conflict from exc
    raise exc


def _reload(obj: ModuleFilter, filter_id: UUID) -> ModuleFilter:
    try:
        obj.refresh_from_db()
    except ModuleFilter.DoesNotExist as exc:
        raise _missing(filter_id) from exc
    return obj


class DjangoModuleFilterRepository(IModuleFilterRepository):

    def list_for_user(self, user_id, module_key):
        rows = ModuleFilter.objects.filter(
            user_id=user_id, module_key__in=_stored_module_keys(module_key),
        ).order_by('name')
        return [_record(obj) for obj in rows]

    def get(self, user_id, filter_id):
        obj = ModuleFilter.objects.filter(user_id=user_id, id=filter_id).first()
        return _record(obj) if obj else None

    def count_for_user(self, user_id, module_key):
        return ModuleFilter.objects.filter(
            user_id=user_id, module_key__in=_stored_module_keys(module_key),
        ).count()

    def name_taken(self, user_id, module_key, name, exclude_id: Optional[UUID] = None):
        queryset = ModuleFilter.objects.filter(
            user_id=user_id,
            module_key__in=_stored_module_keys(module_key),
            name__iexact=name,
        )
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()

    def create(self, user_id, data: ModuleFilterInput):
        module_key = data.module_key.value
        try:
            with transaction.atomic():
                _lock_scope(user_id, module_key)
                if self.count_for_user(user_id, data.module_key) >= MAX_FILTERS_PER_MODULE:
                    raise _limit_reached()
                if self.name_taken(user_id, data.module_key, data.name):
                    raise _duplicate_name(data.name)
                if data.activate:
                    ModuleFilter.objects.filter(
                        user_id=user_id,
                        module_key__in=_stored_module_keys(data.module_key),
                        is_active=True,
                    ).update(is_active=False)
                obj = ModuleFilter.objects.create(
                    user_id=user_id,
                    module_key=module_key,
                    name=data.name,
                    criteria=_criteria_json(data.criteria),
                    is_active=data.activate,
                )
                return _record(obj)
        except IntegrityError as exc:
            _reraise_integrity(exc, data.name)

    def update(self, user_id, filter_id, name, criteria):
        try:
            with transaction.atomic():
                obj = self._row(user_id, filter_id)
                _lock_scope(user_id, obj.module_key)
                obj = _reload(obj, filter_id)
                fields = _normalize_legacy_key(obj)
                canonical = _coerce_module_key(obj.module_key)
                if name is not None and name != obj.name:
                    if self.name_taken(user_id, canonical, name, filter_id):
                        raise _duplicate_name(name)
                    obj.name = name
                    fields.append('name')
                if criteria is not None:
                    encoded = _criteria_json(criteria)
                    if encoded != (obj.criteria or {}):
                        obj.criteria = encoded
                        fields.append('criteria')
                if fields:
                    fields.append('updated_at')
                    obj.save(update_fields=fields)
                return _record(obj)
        except IntegrityError as exc:
            _reraise_integrity(exc, name or '')

    def delete(self, user_id, filter_id):
        with transaction.atomic():
            obj = self._row(user_id, filter_id)
            _lock_scope(user_id, obj.module_key)
            obj.delete()

    def activate(self, user_id, filter_id):
        with transaction.atomic():
            obj = self._row(user_id, filter_id)
            _lock_scope(user_id, obj.module_key)
            obj = _reload(obj, filter_id)
            fields = _normalize_legacy_key(obj)
            canonical = _coerce_module_key(obj.module_key)
            ModuleFilter.objects.filter(
                user_id=user_id,
                module_key__in=_stored_module_keys(canonical),
                is_active=True,
            ).exclude(id=obj.id).update(is_active=False)
            if not obj.is_active:
                obj.is_active = True
                fields.append('is_active')
            if fields:
                fields.append('updated_at')
                obj.save(update_fields=fields)
        return _record(obj)

    def deactivate_all(self, user_id, module_key):
        with transaction.atomic():
            _lock_scope(user_id, module_key.value)
            return ModuleFilter.objects.filter(
                user_id=user_id,
                module_key__in=_stored_module_keys(module_key),
                is_active=True,
            ).update(is_active=False)

    def _row(self, user_id: UUID, filter_id: UUID) -> ModuleFilter:
        try:
            return ModuleFilter.objects.get(user_id=user_id, id=filter_id)
        except ModuleFilter.DoesNotExist as exc:
            raise _missing(filter_id) from exc
