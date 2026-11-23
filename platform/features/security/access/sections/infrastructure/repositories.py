from typing import Optional
from uuid import UUID

from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException
from platform.features.security.catalog_order import apply_order, next_order
from platform.features.security.access.sections.domain.interfaces import ISectionRepository
from platform.features.security.access.sections.domain.schemas import (
    CreateSectionSchema, SectionSchema, UpdateSectionSchema,
)
from platform.features.security.access.sections.models import Section


def _ensure_unique_section_code(code: str, exclude_id: Optional[UUID] = None) -> None:
    qs = Section.objects.filter(code=code)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ConflictException(
            AppErrorCode.SECTION_DUPLICATE_CODE,
            override_detail=f"A section with code '{code}' already exists.",
        )


class DjangoSectionRepository(ISectionRepository):
    def get_all(self, filters: dict | None = None) -> list[SectionSchema]:
        from django.db.models import Q

        qs = Section.objects.all()
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        return [SectionSchema.model_validate(s) for s in qs]

    def get_by_id(self, section_id: UUID) -> Optional[SectionSchema]:
        try:
            return SectionSchema.model_validate(Section.objects.get(id=section_id))
        except Section.DoesNotExist:
            return None

    def create(self, data: CreateSectionSchema) -> SectionSchema:
        _ensure_unique_section_code(data.code)
        try:
            section = Section.objects.create(
                code=data.code,
                name=data.name,
                icon=data.icon or '',
                order=data.order or next_order(Section),
            )
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.SECTION_DUPLICATE_CODE,
                override_detail=f"A section with code '{data.code}' already exists.",
            )
        return SectionSchema.model_validate(section)

    def update(self, section_id: UUID, data: UpdateSectionSchema) -> Optional[SectionSchema]:
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            return None
        if data.code is not None:
            _ensure_unique_section_code(data.code, exclude_id=section_id)
            section.code = data.code
        if data.name is not None:
            section.name = data.name
        if data.icon is not None:
            section.icon = data.icon
        if data.order is not None:
            section.order = data.order
        if data.is_active is not None:
            section.is_active = data.is_active
        try:
            section.save()
        except IntegrityError:
            code = data.code if data.code is not None else section.code
            raise ConflictException(
                AppErrorCode.SECTION_DUPLICATE_CODE,
                override_detail=f"A section with code '{code}' already exists.",
            )
        if data.is_active is not None:
            from core.access.invalidation import invalidate_on_section_change
            invalidate_on_section_change(section.id)
        return SectionSchema.model_validate(section)

    def delete(self, section_id: UUID) -> bool:
        deleted, _ = Section.objects.filter(id=section_id).delete()
        if deleted:
            from core.access.invalidation import invalidate_on_section_change
            invalidate_on_section_change(section_id)
        return deleted > 0

    def reorder(self, ids: list[UUID]) -> int:
        return apply_order(Section, ids)
