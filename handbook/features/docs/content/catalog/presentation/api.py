"""Lectura y CMS del handbook. ACL en los casos de uso."""

from uuid import UUID

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import validated_query
from core.validators import validated_body
from handbook.core.authentication import HandbookAccessAuthentication
from handbook.core.session import resolve_viewer
from handbook.features.docs.content.catalog.presentation.queries import (
    HandbookFeatureQuery,
    HandbookHelpQuery,
    HandbookLocaleQuery,
    HandbookManagePageQuery,
    HandbookRequestQuery,
    HandbookSearchQuery,
)
from handbook.features.docs.content.page.application.use_cases import (
    DeleteHandbookChildUseCase,
    GetManagePageUseCase,
    GetPublishedHelpUseCase,
    GetPublishedPageUseCase,
    ListCatalogUseCase,
    ListFeaturesUseCase,
    ListManagePagesUseCase,
    SavePageDraftUseCase,
    SearchHandbookUseCase,
)
from handbook.features.docs.content.page.domain.schemas import SavePageDraftSchema
from handbook.features.docs.content.page.infrastructure.repositories import (
    DjangoHandbookDocumentStore,
    MinioMarkdownStore,
)
from handbook.features.docs.content.page.presentation.bodies import (
    ReviewChangeBody,
    SavePageBody,
    SubmitChangeBody,
)
from handbook.features.docs.governance.change_request.application.use_cases import (
    ApproveChangeRequestUseCase,
    ListPendingChangeRequestsUseCase,
    RejectChangeRequestUseCase,
    SubmitPageDraftUseCase,
    describe_requests,
)
from handbook.features.docs.governance.change_request.infrastructure.repositories import (
    DjangoChangeRequestRepository,
)


def _blobs():
    return MinioMarkdownStore()


def _documents(blobs=None):
    return DjangoHandbookDocumentStore(blobs or _blobs())


def _requests():
    return DjangoChangeRequestRepository()


def _dump(item):
    return item.model_dump(mode='json')


def _paginated(items, total: int, query, message: str):
    page_size = query.page_size
    return wrap_response({
        'items': [_dump(item) for item in items],
        'total': total,
        'page': query.page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size if page_size else 1,
    }, message=message)


class HandbookTreeView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_query(HandbookLocaleQuery)
    def get(self, request, *, query, **kwargs):
        nodes = ListCatalogUseCase(_documents()).execute(query.filters.get('locale') or 'es', resolve_viewer(request))
        return wrap_response([_dump(node) for node in nodes], message='Handbook tree loaded.')


class HandbookPageView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_query(HandbookLocaleQuery)
    def get(self, request, slug, *, query, **kwargs):
        page = GetPublishedPageUseCase(_documents()).execute(slug, query.filters.get('locale') or 'es', resolve_viewer(request))
        return wrap_response(_dump(page), message='Handbook page loaded.')


class HandbookHelpView(APIView):
    """Guía publicada de la funcionalidad del apartado activo."""

    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_query(HandbookHelpQuery)
    def get(self, request, *, query, **kwargs):
        page = GetPublishedHelpUseCase(_documents()).execute(
            query.filters['feature_key'],
            query.filters.get('locale') or 'es',
            resolve_viewer(request),
        )
        return wrap_response(_dump(page), message='Handbook help loaded.')


class HandbookSearchView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_query(HandbookSearchQuery)
    def get(self, request, *, query, **kwargs):
        hits = SearchHandbookUseCase(_documents()).execute(
            query.filters.get('locale') or 'es',
            query.filters.get('q') or '',
            resolve_viewer(request),
        )
        return wrap_response([_dump(hit) for hit in hits], message='Handbook search completed.')


class ManagePageListView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_query(HandbookManagePageQuery)
    def get(self, request, *, query, **kwargs):
        pages, total = ListManagePagesUseCase(_documents()).execute(
            resolve_viewer(request), offset=query.offset, limit=query.page_size,
        )
        return _paginated(pages, total, query, 'Handbook pages loaded.')

    @validated_body(SavePageBody)
    def post(self, request, *, body: dict, **kwargs):
        blobs = _blobs()
        saved = SavePageDraftUseCase(_documents(blobs), blobs).execute(
            SavePageDraftSchema(**body), resolve_viewer(request),
        )
        audit_log(request, 'HandbookPage', saved.id, 'CREATE', f'Handbook draft created: {saved.slug}')
        return wrap_response(_dump(saved), status_code=201, message='Handbook draft saved.')


class ManagePageDetailView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, page_id, **kwargs):
        page = GetManagePageUseCase(_documents()).execute(UUID(str(page_id)), resolve_viewer(request))
        return wrap_response(_dump(page), message='Handbook page loaded.')

    @validated_body(SavePageBody)
    def put(self, request, page_id, *, body: dict, **kwargs):
        blobs = _blobs()
        saved = SavePageDraftUseCase(_documents(blobs), blobs).execute(
            SavePageDraftSchema(**body), resolve_viewer(request), page_id=UUID(str(page_id)),
        )
        audit_log(request, 'HandbookPage', saved.id, 'UPDATE', f'Handbook draft updated: {saved.slug}')
        return wrap_response(_dump(saved), message='Handbook draft saved.')

    def delete(self, request, page_id, **kwargs):
        blobs = _blobs()
        slug = DeleteHandbookChildUseCase(_documents(blobs), blobs).execute(
            UUID(str(page_id)), resolve_viewer(request),
        )
        audit_log(request, 'HandbookPage', page_id, 'DELETE', f'Handbook child page deleted: {slug}')
        return wrap_response(None, message='Handbook page deleted.')


class ManageFeatureListView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_query(HandbookFeatureQuery)
    def get(self, request, *, query, **kwargs):
        items, total = ListFeaturesUseCase(_documents()).execute(
            resolve_viewer(request),
            audience=query.filters.get('audience') or '',
            query=query.filters.get('q') or '',
            page=query.page,
            page_size=query.page_size,
            category=query.filters.get('category') or None,
        )
        return _paginated(items, total, query, 'Handbook features loaded.')


def _request_view(saved, documents) -> dict:
    return _dump(describe_requests([saved], documents)[0])


class ManageChangeRequestListView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_query(HandbookRequestQuery)
    def get(self, request, *, query, **kwargs):
        rows, total = ListPendingChangeRequestsUseCase(_requests(), _documents()).execute(
            resolve_viewer(request), offset=query.offset, limit=query.page_size,
        )
        return _paginated(rows, total, query, 'Handbook change requests loaded.')

    @validated_body(SubmitChangeBody)
    def post(self, request, *, body: dict, **kwargs):
        documents = _documents()
        saved = SubmitPageDraftUseCase(_requests(), documents).execute(
            page_id=body['page_id'],
            reason=body['reason'],
            viewer=resolve_viewer(request),
        )
        audit_log(request, 'HandbookChangeRequest', saved.id, 'CREATE', 'Handbook change submitted.')
        return wrap_response(_request_view(saved, documents), status_code=201, message='Handbook change submitted.')


class ManageChangeApproveView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_body(ReviewChangeBody)
    def post(self, request, request_id, *, body: dict, **kwargs):
        saved = ApproveChangeRequestUseCase(_requests()).execute(
            UUID(str(request_id)), resolve_viewer(request), review_note=body.get('review_note') or '',
        )
        audit_log(request, 'HandbookChangeRequest', saved.id, 'UPDATE', 'Handbook change approved.')
        return wrap_response(_request_view(saved, _documents()), message='Handbook change approved.')


class ManageChangeRejectView(APIView):
    authentication_classes = [HandbookAccessAuthentication]
    permission_classes = [AllowAny]

    @validated_body(ReviewChangeBody)
    def post(self, request, request_id, *, body: dict, **kwargs):
        saved = RejectChangeRequestUseCase(_requests()).execute(
            UUID(str(request_id)), resolve_viewer(request), review_note=body.get('review_note') or '',
        )
        audit_log(request, 'HandbookChangeRequest', saved.id, 'UPDATE', 'Handbook change rejected.')
        return wrap_response(_request_view(saved, _documents()), message='Handbook change rejected.')
