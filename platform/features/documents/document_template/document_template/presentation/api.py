import logging
import time
from datetime import datetime, timedelta, timezone

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, AppException, NotFoundException
from core.storage.domain.schemas import PresignedUrlMethod, PresignedUrlSchema
from core.storage.infrastructure.minio_storage import MinioStorageService
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.documents.document_template.document_template.application.blocks import (
    PathResolver,
    RenderResolver,
    SystemVarsBuilder,
    TemplateLoader,
)
from platform.features.documents.document_template.document_template.application.preview_context import (
    enrich_preview_path_context,
)
from platform.features.documents.document_template.document_template.application.blocks.path_resolver import (
    extract_path_variable,
    extract_static_prefix,
)
from platform.features.documents.document_template.document_template.application.use_cases import (
    CreateDocumentTemplateUseCase,
    DeleteDocumentTemplateUseCase,
    GetAllDocumentTemplatesUseCase,
    GetDocumentTemplateByIdUseCase,
    UpdateDocumentTemplateUseCase,
)
from platform.features.documents.document_template.document_template.domain.enums import (
    DocumentFormat,
    FORMAT_EXTENSIONS,
)
from platform.features.documents.document_template.document_template.domain.schemas import (
    CreateDocumentTemplateSchema,
    UpdateDocumentTemplateSchema,
)
from platform.features.documents.document_template.document_template.infrastructure.renderer_registry import (
    get_renderer_registry,
    get_template_engine,
)
from platform.features.documents.document_template.document_template.infrastructure.repositories import DjangoDocumentTemplateRepository
from platform.features.documents.document_template.document_template.presentation.bodies import (
    CreateDocumentTemplateBody, UpdateDocumentTemplateBody,
    DocumentPreviewBody, DocumentGeneratedDownloadBody,
)
from platform.features.documents.document_template.document_template.presentation.queries import (
    DocumentGeneratedListQuery,
    DocumentTemplateListQuery,
)


_render_logger = logging.getLogger('documents.render')


def _repo():
    return DjangoDocumentTemplateRepository()


def _catalog_response(query, items, total: int):
    dumped = [item.model_dump(mode='json') for item in items]
    if query.unpaginated:
        return wrap_response(dumped)
    return wrap_response({
        'items': dumped,
        'total': total,
        'page': query.page,
        'page_size': query.page_size,
        'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 1,
    })


class DocumentTemplateListCreateView(APIView):
    """List all document templates or create a new one."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(DocumentTemplateListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        limit = None if query.unpaginated else query.page_size
        offset = 0 if query.unpaginated else query.offset
        items, total = GetAllDocumentTemplatesUseCase(_repo()).execute(
            filters=query.filters, offset=offset, limit=limit,
        )
        return _catalog_response(query, items, total)

    @validated_body(CreateDocumentTemplateBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateDocumentTemplateSchema(**body)
        result = CreateDocumentTemplateUseCase(_repo()).execute(schema)
        audit_log(
            request, 'DocumentTemplate', result.id, 'CREATE',
            f'Document template created: {result.code} (kind={result.kind})',
        )
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='The document template has been created successfully.',
        )


class DocumentTemplateDetailView(APIView):
    """Retrieve, update or delete a single document template."""
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetDocumentTemplateByIdUseCase(_repo()).execute(pk)
        if not result:
            raise NotFoundException(
                AppErrorCode.DOC_TEMPLATE_NOT_FOUND,
                override_detail='Document template not found.',
            )
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateDocumentTemplateBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = UpdateDocumentTemplateSchema(**body)
        result = UpdateDocumentTemplateUseCase(_repo()).execute(pk, schema)
        if not result:
            raise NotFoundException(
                AppErrorCode.DOC_TEMPLATE_NOT_FOUND,
                override_detail='Document template not found.',
            )
        audit_log(
            request, 'DocumentTemplate', pk, 'UPDATE',
            changes = body,
        )
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        deleted = DeleteDocumentTemplateUseCase(_repo()).execute(pk)
        if not deleted:
            raise NotFoundException(
                AppErrorCode.DOC_TEMPLATE_NOT_FOUND,
                override_detail='Document template not found.',
            )
        audit_log(request, 'DocumentTemplate', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class _PreviewThrottle(UserRateThrottle):
    """30 preview renders per minute per user — protects CPU from runaway PDFs."""
    rate = '30/minute'


class DocumentTemplatePreviewView(APIView):
    """Render a template to its final format in memory and stream it back.

    Ephemeral by design: the blob is never written to disk and never
    uploaded to MinIO. Intended for the admin editor's "Download test"
    button. Persistence paths live in their respective feature modules
    (billing, quotations, etc.) — see plan section 5.7.1.
    """

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [_PreviewThrottle]

    @validated_body(DocumentPreviewBody)
    def post(self, request, code, *args, body: dict, **kwargs):
        fmt_raw = (body.get('format') or '').upper().strip()
        try:
            fmt = DocumentFormat(fmt_raw)
        except ValueError:
            raise AppException(
                AppErrorCode.DOC_FORMAT_NOT_ALLOWED,
                override_detail=f'Unknown format "{fmt_raw}". '
                                f'Valid: {DocumentFormat.values()}',
            )

        if not isinstance(body, dict):
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail='"body" must be a JSON object.',
            )

        template = TemplateLoader(_repo()).load(code)
        renderer = RenderResolver(get_renderer_registry()).resolve(template, fmt)
        sys_vars = SystemVarsBuilder().build(fmt, user=request.user)

        started = time.monotonic()
        try:
            blob, content_type = renderer.render(template, body, sys_vars)
        except Exception:
            _render_logger.exception(
                'render_failed',
                extra={
                    'template_code': code,
                    'format':        fmt.value,
                    'user_id':       str(getattr(request.user, 'id', '')),
                    'persist':       False,
                },
            )
            raise

        duration_ms = round((time.monotonic() - started) * 1000)
        _render_logger.info(
            'render_ok',
            extra={
                'template_code':   code,
                'format':          fmt.value,
                'user_id':         str(getattr(request.user, 'id', '')),
                'persist':         False,
                'duration_ms':     duration_ms,
                'blob_size_bytes': len(blob),
            },
        )

        audit_log(
            request, 'DocumentTemplate', str(template.id), 'PREVIEW_RENDER',
            f'Preview rendered: code={code} format={fmt.value} size={len(blob)}b',
        )

        response = HttpResponse(blob, content_type=content_type)
        filename = f'{code.lower()}_preview.{FORMAT_EXTENSIONS[fmt]}'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class DocumentTemplatePreviewPathView(APIView):
    """Resolve the storage_path_template for a hypothetical render.

    Used by the editor to show the admin how the MinIO object key would
    look with the current mock_data — no render, no upload happen.
    """

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(DocumentPreviewBody)
    def post(self, request, code, *args, body: dict, **kwargs):
        fmt_raw = (body.get('format') or 'PDF').upper().strip()
        try:
            fmt = DocumentFormat(fmt_raw)
        except ValueError:
            raise AppException(
                AppErrorCode.DOC_FORMAT_NOT_ALLOWED,
                override_detail=f'Unknown format "{fmt_raw}". '
                                f'Valid: {DocumentFormat.values()}',
            )

        if not isinstance(body, dict):
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail='"body" must be a JSON object.',
            )

        template = TemplateLoader(_repo()).load(code)

        if not template.is_storable:
            return wrap_response({
                'is_storable': False,
                'resolved_path': None,
                'bucket': None,
            })

        sys_vars = SystemVarsBuilder().build(fmt, user=request.user)
        preview_data, preview_vars = enrich_preview_path_context(body, sys_vars)
        path = PathResolver(get_template_engine()).resolve(
            template, preview_data, preview_vars,
        )

        from django.conf import settings as dj_settings
        bucket = template.storage_bucket or dj_settings.DOCUMENTS_DEFAULT_BUCKET

        return wrap_response({
            'is_storable':   True,
            'resolved_path': path,
            'bucket':        bucket,
        })


class DocumentTemplateGeneratedListView(APIView):
    """List documents in MinIO that were generated from a template.

    Listing strategy:
      - Compute the static prefix from `storage_path_template`
        (everything before the first placeholder, ending at `/`).
      - Call IStorageService.list_files(bucket, prefix=...).
      - Sort by last_modified DESC, slice [offset:offset+limit].

    For templates whose path starts with a placeholder (no static
    prefix), the whole bucket is listed — the admin is expected to
    use a dedicated bucket in that case.
    """

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(DocumentGeneratedListQuery)
    def get(self, request, code, *args, query: PaginatedQuery, **kwargs):
        template = TemplateLoader(_repo()).load(code)

        if not template.is_storable:
            return wrap_response({
                'items':  [],
                'total':  0,
                'limit':  0,
                'offset': 0,
                'bucket': None,
                'prefix': None,
            })

        from django.conf import settings as dj_settings
        bucket = template.storage_bucket or dj_settings.DOCUMENTS_DEFAULT_BUCKET
        prefix = extract_static_prefix(template.storage_path_template or '')

        _f = query.filters
        limit  = max(1, min(int(_f.get('limit', 50)), 200))
        offset = max(0, int(_f.get('offset', 0)))

        storage = MinioStorageService()
        list_cap = min(max(limit + offset, limit, 1), 2000)
        try:
            files = storage.list_files(
                bucket=bucket, prefix=prefix, recursive=True, max_keys=list_cap,
            )
        except NotFoundException:
            # Bucket doesn't exist yet → no generated docs.
            return wrap_response({
                'items':  [],
                'total':  0,
                'limit':  limit,
                'offset': offset,
                'bucket': bucket,
                'prefix': prefix,
            })

        def _ts(f):
            lm = f.last_modified or _EPOCH
            return lm if lm.tzinfo is not None else lm.replace(tzinfo=timezone.utc)
        files.sort(key=_ts, reverse=True)
        total = len(files)
        page = files[offset: offset + limit]

        return wrap_response({
            'items':  _serialize_generated_items(
                template.storage_path_template or '', page, template, bucket,
            ),
            'total':  total,
            'limit':  limit,
            'offset': offset,
            'bucket': bucket,
            'prefix': prefix,
        })


class DocumentTemplateGeneratedDownloadView(APIView):
    """Return a signed URL for a specific stored object of a template."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(DocumentGeneratedDownloadBody)
    def post(self, request, code, *args, body: dict, **kwargs):
        object_key = body['object_key'].strip()

        template = TemplateLoader(_repo()).load(code)
        if not template.is_storable:
            raise AppException(
                AppErrorCode.DOC_NOT_STORABLE,
                override_detail=f'Template "{code}" is not storable.',
            )

        from django.conf import settings as dj_settings
        bucket = template.storage_bucket or dj_settings.DOCUMENTS_DEFAULT_BUCKET
        prefix = extract_static_prefix(template.storage_path_template or '')

        # Defense-in-depth: only let admins request objects under THIS template's prefix.
        # Prevents using one template's endpoint to mint URLs for unrelated objects.
        if prefix and not object_key.startswith(prefix):
            raise AppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=f'object_key "{object_key}" is outside this template\'s prefix.',
            )

        ttl_seconds = dj_settings.DOCUMENTS_SIGNED_URL_TTL_SECONDS
        storage = MinioStorageService()
        signed_url = storage.get_presigned_url(PresignedUrlSchema(
            bucket=bucket,
            object_name=object_key,
            method=PresignedUrlMethod.GET,
            expires=timedelta(seconds=ttl_seconds),
        ))

        audit_log(
            request, 'DocumentTemplate', str(template.id), 'GENERATED_DOWNLOAD',
            f'Signed URL generated: bucket={bucket} key={object_key}',
        )

        return wrap_response({
            'signed_url':            signed_url,
            'signed_url_expires_in': ttl_seconds,
            'bucket':                bucket,
            'object_key':            object_key,
        })


_EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


def _serialize_generated_items(path_template: str, files, template, bucket: str) -> list[dict]:
    """Build list payload with tenant/company and template metadata per item."""
    from platform.features.company.tenant.company.models import Company

    tenant_codes: set[str] = set()
    codes_per_file: list[str | None] = []
    for f in files:
        code = extract_path_variable(path_template, f.object_name, 'tenant_code')
        codes_per_file.append(code)
        if code:
            tenant_codes.add(code)

    names_by_schema: dict[str, str] = {}
    if tenant_codes:
        for row in Company.objects.filter(schema_name__in=tenant_codes).values('schema_name', 'name'):
            names_by_schema[row['schema_name']] = row['name']

    items: list[dict] = []
    for f, tenant_code in zip(files, codes_per_file):
        items.append({
            'object_key':     f.object_name,
            'size':           f.size,
            'last_modified':  f.last_modified.isoformat() if f.last_modified else None,
            'etag':           f.etag,
            'tenant_code':    tenant_code,
            'company_name':   names_by_schema.get(tenant_code) if tenant_code else None,
            'template_code':  template.code,
            'template_name':  template.name,
            'template_kind':  template.kind,
            'bucket':         bucket,
        })
    return items
