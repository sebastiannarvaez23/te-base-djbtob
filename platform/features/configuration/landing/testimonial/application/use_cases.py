from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from core.cache import invalidate_cache, use_case_cache
from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from core.signing import (
    SignatoryContext,
    hash_content,
    require_document_binding,
    seal_signature,
    verify_signature,
)


from platform.features.configuration.landing.testimonial.domain.content import (
    DOCUMENT_TYPE,
    canonical_quote,
)
from platform.features.configuration.landing.testimonial.domain.interfaces import (
    ITestimonialRepository,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    AuthorSnapshot,
    CreateTestimonialSchema,
    PublicTestimonialPage,
    PublicTestimonialSchema,
    SignedTestimonialDraft,
    SubmitMyTestimonialSchema,
    TestimonialListFilters,
    TestimonialPage,
    TestimonialSchema,
    UpdateTestimonialSchema,
    project_public,
    resolve_attribution,
)
from core.trace import trace_layer

_CACHE_PREFIX = 'testimonials'
_QUOTE_FIELDS = frozenset({'score', 'message', 'locale', 'author_id'})


def _require_author(snapshot: Optional[AuthorSnapshot]) -> AuthorSnapshot:
    if snapshot is None:
        raise NotFoundException(AppErrorCode.TESTIMONIAL_AUTHOR_NOT_FOUND)
    if not snapshot.is_active:
        raise ConflictException(AppErrorCode.TESTIMONIAL_AUTHOR_INACTIVE)
    return snapshot


def _cleared_signature() -> dict:
    return {
        'content_hash': '',
        'seal': '',
        'seal_algorithm': '',
        'canonical_payload': '',
        'signed_at': None,
        'signatory_id': '',
        'tenant_id': '',
        'ip_address': '',
        'user_agent': '',
        'request_id': '',
        'channel': '',
    }


def _to_public(row: TestimonialSchema) -> Optional[PublicTestimonialSchema]:
    if not row.seal or not row.signed_at or not row.content_hash:
        return None
    live_hash = hash_content(canonical_quote(
        author_id=row.author_id,
        score=row.score,
        message=row.message,
        locale=row.locale,
    ))
    if live_hash != row.content_hash:
        return None
    check = verify_signature(
        require_document_binding(
            document_type=DOCUMENT_TYPE,
            document_version_id=str(row.id),
            content_hash=row.content_hash,
        ),
        SignatoryContext(
            subject_id=row.signatory_id or str(row.author_id),
            tenant_id=row.tenant_id or None,
            signed_at=row.signed_at,
            ip_address=row.ip_address or None,
            user_agent=row.user_agent or None,
            request_id=row.request_id or None,
            channel=row.channel or 'web',
        ),
        row.seal,
        seal_algorithm=row.seal_algorithm,
    )
    if not check.valid:
        return None
    return project_public(row)


class ListTestimonialsUseCase:
    def __init__(self, repository: ITestimonialRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=f'{_CACHE_PREFIX}_list')
    def execute(
        self,
        filters: TestimonialListFilters,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> TestimonialPage:
        items, total = self.repository.list_page(
            filters, offset=offset, limit=limit,
        )
        return TestimonialPage(items=items, total=total)


class ListPublicTestimonialsUseCase:
    def __init__(self, repository: ITestimonialRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=f'{_CACHE_PREFIX}_public')
    def execute(
        self,
        filters: TestimonialListFilters,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> PublicTestimonialPage:
        published = filters.model_copy(update={
            'is_published': True,
            'signed': True,
        })
        rows, _ = self.repository.list_page(published, offset=None, limit=None)
        public = [item for row in rows if (item := _to_public(row)) is not None]
        total = len(public)
        if limit is None:
            return PublicTestimonialPage(items=public, total=total)
        start = offset or 0
        return PublicTestimonialPage(items=public[start:start + limit], total=total)


class GetTestimonialUseCase:
    def __init__(self, repository: ITestimonialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, testimonial_id: UUID) -> TestimonialSchema:
        row = self.repository.get_by_id(testimonial_id)
        if not row:
            raise NotFoundException(AppErrorCode.TESTIMONIAL_NOT_FOUND)
        return row


class CreateTestimonialUseCase:
    def __init__(self, repository: ITestimonialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateTestimonialSchema) -> TestimonialSchema:
        snapshot = _require_author(self.repository.get_author(data.author_id))
        if self.repository.get_by_author(data.author_id):
            raise ConflictException(AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)
        author_name, company_name = resolve_attribution(
            snapshot,
            author_name=data.author_name,
            company_name=data.company_name,
        )
        role = (data.author_role or '').strip() or snapshot.role
        payload = data.model_copy(update={
            'author_name': author_name,
            'company_name': company_name,
            'author_role': role,
        })
        result = self.repository.create(payload)
        invalidate_cache(f'{_CACHE_PREFIX}_*')
        return result


class SubmitMyTestimonialUseCase:
    """Logged-in company user posts and digitally signs their own quote.

    One live review per author: a new submit revokes the previous signed
    document and inserts a fresh row. History stays in the table.
    """

    def __init__(self, repository: ITestimonialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: SubmitMyTestimonialSchema) -> TestimonialSchema:
        if data.accepted is not True:
            raise ValidationAppException(AppErrorCode.TESTIMONIAL_SIGNATURE_REQUIRED)

        snapshot = _require_author(self.repository.get_author(data.author_id))
        author_name, company_name = resolve_attribution(snapshot)
        row_id = uuid4()
        content_hash = hash_content(canonical_quote(
            author_id=data.author_id,
            score=data.score,
            message=data.message,
            locale=data.locale,
        ))
        signed_at = datetime.now(timezone.utc)
        evidence = seal_signature(
            require_document_binding(
                document_type=DOCUMENT_TYPE,
                document_version_id=str(row_id),
                content_hash=content_hash,
            ),
            SignatoryContext(
                subject_id=str(data.author_id),
                tenant_id=data.tenant_id,
                signed_at=signed_at,
                ip_address=data.ip_address,
                user_agent=data.user_agent,
                request_id=data.request_id,
                channel=data.channel or 'web',
            ),
        )
        payload = SignedTestimonialDraft(
            id=row_id,
            author_id=data.author_id,
            score=data.score,
            message=data.message,
            locale=data.locale,
            author_name=author_name,
            company_name=company_name,
            author_role=snapshot.role,
            is_published=True,
            sort_order=0,
            content_hash=content_hash,
            seal=evidence.seal,
            seal_algorithm=evidence.seal_algorithm,
            canonical_payload=evidence.canonical_payload,
            signed_at=signed_at,
            signatory_id=str(data.author_id),
            tenant_id=data.tenant_id or '',
            ip_address=data.ip_address or '',
            user_agent=data.user_agent or '',
            request_id=data.request_id or '',
            channel=data.channel or 'web',
        )
        result = self.repository.replace_live(data.author_id, payload)
        invalidate_cache(f'{_CACHE_PREFIX}_*')
        return result


class UpdateTestimonialUseCase:
    def __init__(self, repository: ITestimonialRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, testimonial_id: UUID, data: UpdateTestimonialSchema,
    ) -> TestimonialSchema:
        existing = self.repository.get_by_id(testimonial_id)
        if not existing:
            raise NotFoundException(AppErrorCode.TESTIMONIAL_NOT_FOUND)

        fields = data.model_fields_set
        updates: dict = {}

        if 'author_id' in fields and data.author_id != existing.author_id:
            snapshot = _require_author(self.repository.get_author(data.author_id))
            other = self.repository.get_by_author(data.author_id)
            if other and other.id != testimonial_id:
                raise ConflictException(AppErrorCode.TESTIMONIAL_DUPLICATE_AUTHOR)
            name, company = resolve_attribution(
                snapshot,
                author_name=data.author_name if 'author_name' in fields else None,
                company_name=data.company_name if 'company_name' in fields else None,
            )
            updates['author_name'] = name
            updates['company_name'] = company
            if 'author_role' not in fields:
                updates['author_role'] = snapshot.role
        elif 'author_name' in fields or 'company_name' in fields:
            snapshot = self.repository.get_author(existing.author_id)
            if snapshot is None:
                name = (data.author_name or '').strip() or existing.author_name
                company = (data.company_name or '').strip() or existing.company_name
            else:
                name, company = resolve_attribution(
                    snapshot,
                    author_name=data.author_name if 'author_name' in fields else None,
                    company_name=data.company_name if 'company_name' in fields else None,
                    existing=existing,
                )
            if 'author_name' in fields:
                updates['author_name'] = name
            if 'company_name' in fields:
                updates['company_name'] = company

        if existing.seal and fields & _QUOTE_FIELDS:
            updates.update(_cleared_signature())

        payload = data.model_copy(update=updates) if updates else data
        result = self.repository.update(testimonial_id, payload)
        if not result:
            raise NotFoundException(AppErrorCode.TESTIMONIAL_NOT_FOUND)
        invalidate_cache(f'{_CACHE_PREFIX}_*')
        return result
