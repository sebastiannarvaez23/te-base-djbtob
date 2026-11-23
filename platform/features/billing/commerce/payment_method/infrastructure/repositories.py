import uuid
from typing import Optional, List
from django.db.models import Q
from django.utils import timezone

from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.interfaces import IPaymentMethodRepository
from ..domain.schemas import PaymentMethodSchema, CreatePaymentMethodSchema, UpdatePaymentMethodSchema
from ..models import PaymentMethod

_FIELDS = ('id', 'company_id', 'name', 'provider', 'holder', 'last4', 'expiry', 'is_active', 'created_at', 'updated_at')


class DjangoPaymentMethodRepository(IPaymentMethodRepository):

    def get_all(self) -> List[PaymentMethodSchema]:
        rows = PaymentMethod.objects.order_by('-created_at').values(*_FIELDS)
        return [PaymentMethodSchema(**row) for row in rows]

    def get_all_by_company(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        qs = PaymentMethod.objects.filter(company_id=company_id).order_by('-created_at')
        f = query.filters
        if 'is_active' in f:
            qs = qs.filter(is_active=bool(f['is_active']))
        if 'provider' in f:
            qs = qs.filter(provider__icontains=f['provider'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'q' in f:
            qs = qs.filter(
                Q(name__icontains=f['q'])
                | Q(provider__icontains=f['q'])
                | Q(holder__icontains=f['q'])
                | Q(last4__icontains=f['q'])
            )

        if query.unpaginated:
            items = [PaymentMethodSchema(**row) for row in qs.values(*_FIELDS)]
            return PaginatedResult(
                items=items, total=len(items), page=0, page_size=0, total_pages=1,
            )

        total = qs.count()
        items = [
            PaymentMethodSchema(**row)
            for row in qs.values(*_FIELDS)[query.offset: query.offset + query.limit]
        ]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items, total=total, page=query.page,
            page_size=query.page_size, total_pages=total_pages,
        )

    def get_by_id(self, id: uuid.UUID) -> Optional[PaymentMethodSchema]:
        row = PaymentMethod.objects.filter(id=id).values(*_FIELDS).first()
        return PaymentMethodSchema(**row) if row else None

    def create(self, data: CreatePaymentMethodSchema) -> PaymentMethodSchema:
        obj = PaymentMethod.objects.create(**data.model_dump())
        return PaymentMethodSchema.model_validate(obj)

    def partial_update(self, id: uuid.UUID, data: UpdatePaymentMethodSchema) -> Optional[PaymentMethodSchema]:
        changes = data.model_dump(exclude_none=True)
        if not changes:
            return self.get_by_id(id)
        changes['updated_at'] = timezone.now()
        updated = PaymentMethod.objects.filter(id=id).update(**changes)
        if not updated:
            return None
        return self.get_by_id(id)

    def update(self, id: uuid.UUID, data: CreatePaymentMethodSchema) -> Optional[PaymentMethodSchema]:
        fields = data.model_dump()
        fields['updated_at'] = timezone.now()
        updated = PaymentMethod.objects.filter(id=id).update(**fields)
        if not updated:
            return None
        return self.get_by_id(id)

    def delete(self, id: uuid.UUID) -> bool:
        deleted, _ = PaymentMethod.objects.filter(id=id).delete()
        return deleted > 0
