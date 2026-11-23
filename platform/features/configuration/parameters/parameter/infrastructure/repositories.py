import uuid
from typing import List, Optional

from django.db.models import Q

from ..domain.interfaces import IParameterRepository
from ..domain.schemas import CreateParameterSchema, ParameterSchema, UpdateParameterSchema
from ..models import Parameter


def _to_schema(obj: Parameter) -> ParameterSchema:
    return ParameterSchema(
        id=obj.id,
        parameter_type=obj.parameter_type_id,
        code=obj.code,
        name=obj.name,
        description=obj.description,
        data_type=obj.data_type,
        value=obj.value,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class DjangoParameterRepository(IParameterRepository):

    def _qs(self):
        return Parameter.objects.all()

    def get_all(self, filters: dict | None = None) -> List[ParameterSchema]:
        qs = self._qs().order_by('code')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'data_type' in f:
            qs = qs.filter(data_type=f['data_type'])
        if 'parameter_type_id' in f:
            qs = qs.filter(parameter_type_id=f['parameter_type_id'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        return [_to_schema(obj) for obj in qs]

    def get_by_id(self, id: uuid.UUID) -> Optional[ParameterSchema]:
        try:
            return _to_schema(self._qs().get(id=id))
        except Parameter.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> Optional[ParameterSchema]:
        try:
            return _to_schema(self._qs().get(code=code))
        except Parameter.DoesNotExist:
            return None

    def create(self, data: CreateParameterSchema) -> ParameterSchema:
        fields = data.model_dump()
        fields['parameter_type_id'] = fields.pop('parameter_type')
        obj = Parameter.objects.create(**fields)
        return _to_schema(obj)

    def update(self, id: uuid.UUID, data: UpdateParameterSchema) -> Optional[ParameterSchema]:
        try:
            obj = self._qs().get(id=id)
            fields = data.model_dump(exclude_unset=True)
            if 'parameter_type' in fields:
                fields['parameter_type_id'] = fields.pop('parameter_type')
            for field, value in fields.items():
                setattr(obj, field, value)
            obj.save()
            return _to_schema(obj)
        except Parameter.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            obj = Parameter.objects.get(id=id)
            obj.delete()
            return True
        except Parameter.DoesNotExist:
            return False
