from typing import List, Optional
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone as django_timezone

from core.errors import AppErrorCode, ConflictException, NotFoundException

from platform.features.configuration.landing.testimonial.domain.interfaces import (
    ITestimonialPromptReceiptRepository,
    ITestimonialPromptSettingsRepository,
    ITestimonialRepository,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    AuthorSnapshot,
    CreateTestimonialSchema,
    SignedTestimonialDraft,
    TestimonialListFilters,
    TestimonialPromptReceiptSchema,
    TestimonialPromptSettingsSchema,
    TestimonialSchema,
    UpdateTestimonialSchema,
)
from platform.features.configuration.landing.testimonial.models import (
    Testimonial,
    TestimonialPromptReceipt,
    TestimonialPromptSettings,
)


def _to_schema(obj: Testimonial) -> TestimonialSchema:
    return TestimonialSchema(
        id=obj.id,
        author_id=obj.author_id,
        score=obj.score,
        message=obj.message,
        author_name=obj.author_name,
        author_role=obj.author_role,
        company_name=obj.company_name,
        locale=obj.locale,
        is_published=obj.is_published,
        sort_order=obj.sort_order,
        content_hash=obj.content_hash,
        seal=obj.seal,
        seal_algorithm=obj.seal_algorithm,
        canonical_payload=obj.canonical_payload,
        signed_at=obj.signed_at,
        signatory_id=obj.signatory_id,
        tenant_id=obj.tenant_id,
        ip_address=obj.ip_address,
        user_agent=obj.user_agent,
        request_id=obj.request_id,
        channel=obj.channel,
        revoked_at=obj.revoked_at,
        superseded_by=obj.superseded_by_id,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _author_snapshot(user) -> AuthorSnapshot:
    name = ' '.join(
        part for part in (user.first_name or '', user.last_name or '') if part
    ).strip()
    company_name = ''
    if getattr(user, 'company', None) is not None:
        company_name = user.company.name or ''
    role = ''
    if getattr(user, 'rol', None) is not None:
        role = user.rol.name or ''
    return AuthorSnapshot(
        id=user.id,
        display_name=name or user.username,
        company_name=company_name,
        is_active=bool(user.is_active),
        role=role,
    )


def _lock_author(author_id: UUID):
    User = get_user_model()
    try:
        return User.objects.select_for_update().select_related(
            'company', 'rol',
        ).get(pk=author_id)
    except User.DoesNotExist:
        raise NotFoundException(AppErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND)


class DjangoTestimonialRepository(ITestimonialRepository):

    def _qs(self, *, live_only: bool = True):
        qs = Testimonial.objects.all()
        if live_only:
            qs = qs.filter(revoked_at__isnull=True)
        return qs

    def _apply_filters(self, qs, filters: TestimonialListFilters):
        if filters.author_id is not None:
            qs = qs.filter(author_id=filters.author_id)
        if filters.score is not None:
            qs = qs.filter(score=filters.score)
        if filters.is_published is not None:
            qs = qs.filter(is_published=filters.is_published)
        if filters.locale is not None:
            qs = qs.filter(locale=filters.locale)
        if filters.signed is not None:
            if filters.signed:
                qs = qs.exclude(seal='').filter(signed_at__isnull=False)
            else:
                qs = qs.filter(Q(seal='') | Q(signed_at__isnull=True))
        if filters.q:
            q = filters.q
            qs = qs.filter(
                Q(message__icontains=q)
                | Q(author_name__icontains=q)
                | Q(company_name__icontains=q)
                | Q(author_role__icontains=q)
            )
        return qs

    def list_page(
        self,
        filters: TestimonialListFilters,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> tuple[List[TestimonialSchema], int]:
        qs = self._apply_filters(
            self._qs().order_by('sort_order', '-created_at'),
            filters,
        )
        total = qs.count()
        if limit is None:
            return [_to_schema(obj) for obj in qs], total
        start = offset or 0
        return [_to_schema(obj) for obj in qs[start:start + limit]], total

    def get_by_id(self, testimonial_id: UUID) -> Optional[TestimonialSchema]:
        try:
            return _to_schema(self._qs().get(id=testimonial_id))
        except Testimonial.DoesNotExist:
            return None

    def get_by_author(self, author_id: UUID) -> Optional[TestimonialSchema]:
        try:
            return _to_schema(self._qs().get(author_id=author_id))
        except Testimonial.DoesNotExist:
            return None

    def list_by_author_ids(self, author_ids: List[UUID]) -> List[TestimonialSchema]:
        if not author_ids:
            return []
        qs = self._qs().filter(author_id__in=author_ids)
        return [_to_schema(obj) for obj in qs]

    def get_author(self, author_id: UUID) -> Optional[AuthorSnapshot]:
        User = get_user_model()
        try:
            user = User.objects.select_related('company', 'rol').get(id=author_id)
        except User.DoesNotExist:
            return None
        return _author_snapshot(user)

    def create(self, data: CreateTestimonialSchema) -> TestimonialSchema:
        with transaction.atomic():
            _lock_author(data.author_id)
            payload = data.model_dump(exclude_none=True)
            try:
                obj = Testimonial.objects.create(**payload)
            except IntegrityError as exc:
                if 'author' in str(exc).lower() or 'uniq_tst_live_author' in str(exc):
                    raise ConflictException(AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)
                raise
            return _to_schema(obj)

    def replace_live(
        self, author_id: UUID, data: SignedTestimonialDraft,
    ) -> TestimonialSchema:
        with transaction.atomic():
            _lock_author(author_id)
            live = (
                self._qs()
                .select_for_update()
                .filter(author_id=author_id)
                .first()
            )
            now = django_timezone.now()
            if live is not None:
                live.revoked_at = now
                live.save(update_fields=['revoked_at', 'updated_at'])
            payload = data.model_dump()
            try:
                created = Testimonial.objects.create(**payload)
            except IntegrityError as exc:
                if 'author' in str(exc).lower() or 'uniq_tst_live_author' in str(exc):
                    raise ConflictException(AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)
                raise
            if live is not None:
                live.superseded_by_id = created.id
                live.save(update_fields=['superseded_by_id', 'updated_at'])
            return _to_schema(created)

    def update(
        self, testimonial_id: UUID, data: UpdateTestimonialSchema,
    ) -> Optional[TestimonialSchema]:
        with transaction.atomic():
            try:
                obj = self._qs().select_for_update().get(id=testimonial_id)
            except Testimonial.DoesNotExist:
                return None
            fields = data.model_dump(exclude_unset=True)
            for field, value in fields.items():
                setattr(obj, field, value)
            try:
                obj.save()
            except IntegrityError as exc:
                if 'author' in str(exc).lower() or 'uniq_tst_live_author' in str(exc):
                    raise ConflictException(AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)
                raise
            return _to_schema(obj)


def _settings_schema(obj: TestimonialPromptSettings) -> TestimonialPromptSettingsSchema:
    return TestimonialPromptSettingsSchema(
        prompt_enabled=obj.prompt_enabled,
        frequency_days=obj.frequency_days,
        first_appearance_days=obj.first_appearance_days,
        login_delay_seconds=obj.login_delay_seconds,
        ask_after_submit=obj.ask_after_submit,
    )


def _receipt_schema(obj: TestimonialPromptReceipt) -> TestimonialPromptReceiptSchema:
    return TestimonialPromptReceiptSchema(
        user_id=obj.user_id,
        last_prompted_at=obj.last_prompted_at,
        first_seen_at=obj.first_seen_at,
        pending_reprompt=obj.pending_reprompt,
    )


class DjangoTestimonialPromptSettingsRepository(ITestimonialPromptSettingsRepository):

    def get(self) -> Optional[TestimonialPromptSettingsSchema]:
        obj = TestimonialPromptSettings.objects.filter(
            singleton_key=TestimonialPromptSettings.SINGLETON_KEY,
        ).first()
        if obj is None:
            return None
        return _settings_schema(obj)

    def save(
        self, data: TestimonialPromptSettingsSchema,
    ) -> TestimonialPromptSettingsSchema:
        obj, _ = TestimonialPromptSettings.objects.update_or_create(
            singleton_key=TestimonialPromptSettings.SINGLETON_KEY,
            defaults={
                'prompt_enabled': data.prompt_enabled,
                'frequency_days': data.frequency_days,
                'first_appearance_days': data.first_appearance_days,
                'login_delay_seconds': data.login_delay_seconds,
                'ask_after_submit': data.ask_after_submit,
            },
        )
        return _settings_schema(obj)


class DjangoTestimonialPromptReceiptRepository(ITestimonialPromptReceiptRepository):

    def get(self, user_id: UUID) -> Optional[TestimonialPromptReceiptSchema]:
        try:
            return _receipt_schema(TestimonialPromptReceipt.objects.get(user_id=user_id))
        except TestimonialPromptReceipt.DoesNotExist:
            return None

    def upsert(
        self, data: TestimonialPromptReceiptSchema,
    ) -> TestimonialPromptReceiptSchema:
        obj, _ = TestimonialPromptReceipt.objects.update_or_create(
            user_id=data.user_id,
            defaults={
                'last_prompted_at': data.last_prompted_at,
                'first_seen_at': data.first_seen_at,
                'pending_reprompt': data.pending_reprompt,
            },
        )
        return _receipt_schema(obj)

    def mark_pending_reprompt(self, user_ids: List[UUID]) -> int:
        unique = list(dict.fromkeys(user_ids))
        if not unique:
            return 0
        with transaction.atomic():
            existing = {
                row.user_id: row
                for row in list(
                    TestimonialPromptReceipt.objects.select_for_update().filter(
                        user_id__in=unique,
                    )
                )
            }
            to_update = []
            for row in existing.values():
                if row.pending_reprompt:
                    continue
                row.pending_reprompt = True
                to_update.append(row)
            if to_update:
                TestimonialPromptReceipt.objects.bulk_update(
                    to_update, ['pending_reprompt'],
                )
            missing = [uid for uid in unique if uid not in existing]
            if missing:
                TestimonialPromptReceipt.objects.bulk_create([
                    TestimonialPromptReceipt(user_id=uid, pending_reprompt=True)
                    for uid in missing
                ])
            return len(unique)
