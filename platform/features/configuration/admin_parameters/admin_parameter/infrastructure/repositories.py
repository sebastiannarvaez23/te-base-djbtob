import uuid
from typing import List, Optional

from django.db import IntegrityError
from django.db.models import Q

from core.errors import AppErrorCode, ConflictException

from ..domain.interfaces import IAdminParameterRepository
from ..domain.schemas import (
    AdminParameterSchema,
    CreateAdminParameterSchema,
    UpdateAdminParameterSchema,
)
from ..models import AdminParameter


def _to_schema(obj: AdminParameter) -> AdminParameterSchema:
    return AdminParameterSchema(
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


class DjangoAdminParameterRepository(IAdminParameterRepository):

    def _qs(self):
        return AdminParameter.objects.all()

    def get_all(self, filters: dict | None = None) -> List[AdminParameterSchema]:
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

    def get_by_id(self, id: uuid.UUID) -> Optional[AdminParameterSchema]:
        try:
            return _to_schema(self._qs().get(id=id))
        except AdminParameter.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> Optional[AdminParameterSchema]:
        try:
            return _to_schema(self._qs().get(code=code))
        except AdminParameter.DoesNotExist:
            return None

    def create(self, data: CreateAdminParameterSchema) -> AdminParameterSchema:
        fields = data.model_dump()
        fields['parameter_type_id'] = fields.pop('parameter_type')
        try:
            obj = AdminParameter.objects.create(**fields)
        except IntegrityError as exc:
            raise ConflictException(
                AppErrorCode.APARAM_DUPLICATE_CODE,
                override_detail=(
                    f"An admin parameter with code '{data.code}' already exists."
                ),
            ) from exc
        return _to_schema(obj)

    def update(
        self, id: uuid.UUID, data: UpdateAdminParameterSchema,
    ) -> Optional[AdminParameterSchema]:
        try:
            obj = self._qs().get(id=id)
            fields = data.model_dump(exclude_unset=True)
            if 'parameter_type' in fields:
                fields['parameter_type_id'] = fields.pop('parameter_type')
            for field, value in fields.items():
                setattr(obj, field, value)
            try:
                obj.save()
            except IntegrityError as exc:
                raise ConflictException(
                    AppErrorCode.APARAM_DUPLICATE_CODE,
                    override_detail=(
                        f"An admin parameter with code '{data.code or obj.code}' "
                        'already exists.'
                    ),
                ) from exc
            return _to_schema(obj)
        except AdminParameter.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            obj = AdminParameter.objects.get(id=id)
            obj.delete()
            return True
        except AdminParameter.DoesNotExist:
            return False

    def count_by_type(self, parameter_type_id: uuid.UUID) -> int:
        return self._qs().filter(parameter_type_id=parameter_type_id).count()
