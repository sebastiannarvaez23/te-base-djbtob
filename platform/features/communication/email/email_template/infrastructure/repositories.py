import uuid
from typing import List, Optional

from platform.features.communication.email.email_sender.domain.schemas import EmailSenderSchema

from ..domain.interfaces import IEmailTemplateRepository
from ..domain.schemas import CreateEmailTemplateSchema, EmailTemplateSchema, UpdateEmailTemplateSchema
from ..models import EmailTemplate


def _to_schema(obj: EmailTemplate) -> EmailTemplateSchema:
    sender_detail = None
    if obj.sender_id and getattr(obj, 'sender', None) is not None:
        sender_detail = EmailSenderSchema.model_validate(obj.sender)
    return EmailTemplateSchema(
        id=obj.id,
        code=obj.code,
        name=obj.name,
        subject=obj.subject,
        body=obj.body,
        html_template=obj.html_template,
        sender=obj.sender_id,
        sender_detail=sender_detail,
        mock_data=obj.mock_data or {},
        description=obj.description,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class DjangoEmailTemplateRepository(IEmailTemplateRepository):

    def _qs(self):
        return EmailTemplate.objects.select_related('sender').all()

    def get_all(self, filters: dict | None = None) -> List[EmailTemplateSchema]:
        from django.db.models import Q

        qs = self._qs().order_by('code')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'sender_id' in f:
            qs = qs.filter(sender_id=f['sender_id'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        return [_to_schema(obj) for obj in qs]

    def get_by_id(self, id: uuid.UUID) -> Optional[EmailTemplateSchema]:
        try:
            return _to_schema(self._qs().get(id=id))
        except EmailTemplate.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> Optional[EmailTemplateSchema]:
        try:
            return _to_schema(self._qs().get(code=code))
        except EmailTemplate.DoesNotExist:
            return None

    def create(self, data: CreateEmailTemplateSchema) -> EmailTemplateSchema:
        fields = data.model_dump()
        fields['sender_id'] = fields.pop('sender', None)
        obj = EmailTemplate.objects.create(**fields)
        return _to_schema(self._qs().get(id=obj.id))

    def update(self, id: uuid.UUID, data: UpdateEmailTemplateSchema) -> Optional[EmailTemplateSchema]:
        try:
            obj = self._qs().get(id=id)
            fields = data.model_dump(exclude_unset=True)
            if 'sender' in fields:
                fields['sender_id'] = fields.pop('sender')
            for field, value in fields.items():
                setattr(obj, field, value)
            obj.save()
            return _to_schema(self._qs().get(id=obj.id))
        except EmailTemplate.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            obj = EmailTemplate.objects.get(id=id)
            obj.delete()
            return True
        except EmailTemplate.DoesNotExist:
            return False
