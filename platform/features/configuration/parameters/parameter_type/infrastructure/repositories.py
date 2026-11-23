import uuid
from typing import List, Optional

from ..domain.interfaces import IParameterTypeRepository
from ..domain.schemas import CreateParameterTypeSchema, ParameterTypeSchema, UpdateParameterTypeSchema
from ..models import ParameterType


def _to_schema(obj: ParameterType) -> ParameterTypeSchema:
    return ParameterTypeSchema(
        id=obj.id,
        code=obj.code,
        name=obj.name,
        description=obj.description,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class DjangoParameterTypeRepository(IParameterTypeRepository):

    def _qs(self):
        return ParameterType.objects.all()

    def get_all(self, filters: dict | None = None) -> List[ParameterTypeSchema]:
        qs = self._qs().order_by('code')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        return [_to_schema(obj) for obj in qs]

    def get_by_id(self, id: uuid.UUID) -> Optional[ParameterTypeSchema]:
        try:
            return _to_schema(self._qs().get(id=id))
        except ParameterType.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> Optional[ParameterTypeSchema]:
        try:
            return _to_schema(self._qs().get(code=code))
        except ParameterType.DoesNotExist:
            return None

    def create(self, data: CreateParameterTypeSchema) -> ParameterTypeSchema:
        obj = ParameterType.objects.create(**data.model_dump())
        return _to_schema(obj)

    def update(self, id: uuid.UUID, data: UpdateParameterTypeSchema) -> Optional[ParameterTypeSchema]:
        try:
            obj = self._qs().get(id=id)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(obj, field, value)
            obj.save()
            return _to_schema(obj)
        except ParameterType.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            obj = ParameterType.objects.get(id=id)
            obj.delete()
            return True
        except ParameterType.DoesNotExist:
            return False
