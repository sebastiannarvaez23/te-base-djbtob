import uuid
from typing import Optional

from django.db.models import CharField, F, Q, Value
from django.utils import timezone

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.billing.complement.entitlement.domain.interfaces import ICompanyComplementRepository
from platform.features.billing.complement.entitlement.domain.schemas import (
    CompanyComplementSchema,
    ComplementCatalogItemSchema,
    ComplementFunctionalitySchema,
    GrantComplementSchema,
)
from platform.features.billing.complement.entitlement.models import CompanyComplement
from platform.features.company.tenant.company.models import Company
from platform.features.security.access.functionalities.models import Functionality
from platform.features.security.access.modules.models import Module


def _to_license(obj: CompanyComplement) -> CompanyComplementSchema:
    if obj.functionality_id:
        key = obj.functionality.key
        label = obj.functionality.label
        module_code = obj.functionality.module.code
    else:
        key = obj.module.code
        label = obj.module.name
        module_code = obj.module.code
    return CompanyComplementSchema(
        id=obj.id,
        company_id=obj.company_id,
        functionality_id=obj.functionality_id,
        module_id=obj.module_id,
        functionality_key=key,
        functionality_label=label,
        module_code=module_code,
        billing_mode=obj.billing_mode,
        status=obj.status,
        source=obj.source,
        starts_at=obj.starts_at,
        ends_at=obj.ends_at,
        notes=obj.notes or '',
        auto_renew=obj.auto_renew,
        catalog_service_id=obj.catalog_service_id,
        price_paid=obj.price_paid,
        currency=obj.currency or '',
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _page(qs, query: PaginatedQuery, mapper) -> PaginatedResult:
    total = qs.count()
    items = [mapper(row) for row in qs[query.offset: query.offset + query.limit]]
    total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
    return PaginatedResult(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
        total_pages=total_pages,
    )


class DjangoCompanyComplementRepository(ICompanyComplementRepository):

    def company_exists(self, company_id: uuid.UUID) -> bool:
        return Company.objects.filter(id=company_id).exists()

    def get_grantable(self, functionality_id: uuid.UUID) -> Optional[ComplementFunctionalitySchema]:
        obj = (
            Functionality.objects.filter(
                id=functionality_id,
                is_active=True,
                offering=Functionality.Offering.COMPLEMENT,
                module__is_active=True,
                module__section__is_active=True,
            )
            .only('id', 'key', 'billing_mode')
            .first()
        )
        if obj is None:
            return None
        return ComplementFunctionalitySchema(id=obj.id, key=obj.key, billing_mode=obj.billing_mode)

    def get_grantable_module(self, module_id: uuid.UUID) -> Optional[ComplementFunctionalitySchema]:
        obj = (
            Module.objects.filter(
                id=module_id,
                is_active=True,
                offering='complement',
                section__is_active=True,
            )
            .only('id', 'code', 'billing_mode')
            .first()
        )
        if obj is None:
            return None
        return ComplementFunctionalitySchema(id=obj.id, key=obj.code, billing_mode=obj.billing_mode)

    def create_active(self, data: GrantComplementSchema, billing_mode: str) -> CompanyComplementSchema:
        catalog_service_id = None
        if data.functionality_id:
            catalog_service_id = (
                Functionality.objects.filter(id=data.functionality_id)
                .values_list('catalog_service_id', flat=True)
                .first()
            )
        elif data.module_id:
            catalog_service_id = (
                Module.objects.filter(id=data.module_id)
                .values_list('catalog_service_id', flat=True)
                .first()
            )
        obj = CompanyComplement.objects.create(
            company_id=data.company_id,
            functionality_id=data.functionality_id,
            module_id=data.module_id,
            billing_mode=billing_mode,
            source=CompanyComplement.Source.ADMIN_GRANT,
            status=CompanyComplement.Status.ACTIVE,
            starts_at=timezone.now(),
            ends_at=None,
            notes=data.notes or '',
            auto_renew=False,
            catalog_service_id=catalog_service_id,
            granted_by_id=data.granted_by_id,
        )
        obj = (
            CompanyComplement.objects
            .select_related('functionality', 'functionality__module', 'module')
            .get(id=obj.id)
        )
        return _to_license(obj)

    def get_for_company(
        self, company_id: uuid.UUID, entitlement_id: uuid.UUID, *, lock: bool = False,
    ) -> Optional[CompanyComplementSchema]:
        qs = CompanyComplement.objects.select_related(
            'functionality', 'functionality__module', 'module',
        ).filter(
            id=entitlement_id,
            company_id=company_id,
        )
        if lock:
            qs = qs.select_for_update(of=('self',))
        obj = qs.first()
        if obj is None:
            return None
        return _to_license(obj)

    def mark_revoked(self, entitlement_id: uuid.UUID, notes: str) -> CompanyComplementSchema:
        obj = CompanyComplement.objects.select_related(
            'functionality', 'functionality__module', 'module',
        ).get(id=entitlement_id)
        text = (notes or '').strip()
        if text:
            obj.notes = f'{obj.notes}\n{text}'.strip() if obj.notes else text
        obj.status = CompanyComplement.Status.REVOKED
        if obj.ends_at is None:
            obj.ends_at = timezone.now()
        obj.save(update_fields=['status', 'notes', 'ends_at', 'updated_at'])
        return _to_license(obj)

    def list_catalog(self, query: PaginatedQuery) -> PaginatedResult:
        filters = query.filters
        functionalities = Functionality.objects.filter(
            offering=Functionality.Offering.COMPLEMENT,
            is_active=True,
            module__is_active=True,
            module__section__is_active=True,
        )
        modules = Module.objects.filter(
            offering='complement',
            is_active=True,
            section__is_active=True,
        )
        if 'label' in filters:
            functionalities = functionalities.filter(label__icontains=filters['label'])
            modules = modules.filter(name__icontains=filters['label'])
        if 'key' in filters:
            functionalities = functionalities.filter(key__icontains=filters['key'])
            modules = modules.filter(code__icontains=filters['key'])
        if 'billing_mode' in filters:
            functionalities = functionalities.filter(billing_mode=filters['billing_mode'])
            modules = modules.filter(billing_mode=filters['billing_mode'])
        if 'q' in filters:
            text = filters['q']
            functionalities = functionalities.filter(Q(label__icontains=text) | Q(key__icontains=text))
            modules = modules.filter(Q(name__icontains=text) | Q(code__icontains=text))

        text_field = CharField()
        combined = functionalities.annotate(
            kind=Value('functionality', output_field=text_field),
            item_key=F('key'),
            item_label=F('label'),
            item_module=F('module__code'),
            item_category=F('category'),
        ).values(
            'id', 'kind', 'item_key', 'item_label', 'item_module', 'billing_mode', 'item_category',
        ).union(
            modules.annotate(
                kind=Value('module', output_field=text_field),
                item_key=F('code'),
                item_label=F('name'),
                item_module=F('code'),
                item_category=Value('module', output_field=text_field),
            ).values(
                'id', 'kind', 'item_key', 'item_label', 'item_module', 'billing_mode', 'item_category',
            ),
            all=True,
        ).order_by('item_label', 'item_key')
        total = combined.count()
        page_rows = combined[query.offset: query.offset + query.limit]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        items = [
            ComplementCatalogItemSchema(
                id=row['id'],
                kind=row['kind'],
                key=row['item_key'],
                label=row['item_label'],
                module=row['item_module'],
                billing_mode=row['billing_mode'],
                category=row['item_category'],
            )
            for row in page_rows
        ]
        return PaginatedResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )

    def list_for_company(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        qs = (
            CompanyComplement.objects.filter(company_id=company_id)
            .select_related('functionality', 'functionality__module', 'module')
            .order_by('-starts_at', '-created_at')
        )
        filters = query.filters
        if 'status' in filters:
            qs = qs.filter(status=filters['status'])
        if 'key' in filters:
            text = filters['key']
            qs = qs.filter(
                Q(functionality__key__icontains=text) | Q(module__code__icontains=text),
            )
        return _page(qs, query, _to_license)
