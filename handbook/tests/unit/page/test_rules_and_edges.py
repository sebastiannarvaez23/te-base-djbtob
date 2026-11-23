"""Reglas puras y caminos de error del documento (sin base de datos)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from handbook.core.constants import APPROVE_FEATURE_KEY, HANDBOOK_BUCKET, PROPOSE_FEATURE_KEY
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.content.page.application.use_cases import (
    GetManagePageUseCase,
    ListFeaturesUseCase,
    SavePageDraftUseCase,
    SearchHandbookUseCase,
)
from handbook.features.docs.content.page.domain import rules
from handbook.features.docs.content.page.domain.schemas import (
    FeatureOptionView,
    LocaleVersionInput,
    SavePageDraftSchema,
)
from handbook.features.docs.content.page.infrastructure.memory import MemoryDocumentStore, MemoryMarkdownStore
from handbook.features.docs.content.page.infrastructure.repositories import MinioMarkdownStore
from handbook.features.docs.governance.change_request.application.use_cases import (
    ApproveChangeRequestUseCase,
    RejectChangeRequestUseCase,
    SubmitPageDraftUseCase,
)
from handbook.features.docs.governance.change_request.infrastructure.memory import (
    InMemoryChangeRequestRepository,
)

pytestmark = pytest.mark.unit

EDITOR = HandbookViewer.admin(
    user_id=str(uuid4()), features=frozenset({PROPOSE_FEATURE_KEY, APPROVE_FEATURE_KEY}), is_superuser=True,
)
WMS = FeatureOptionView(id=uuid4(), key='orders.view', label='Pedidos', module='Orders', audience='wms')
ADMIN = FeatureOptionView(id=uuid4(), key='support.inbox', label='Bandeja', module='Support', audience='admin')


def _code(exc_info):
    return exc_info.value.code


def _draft(slug='pedidos', **overrides):
    data = dict(slug=slug, versions=[
        LocaleVersionInput(locale='es', version='1.0', title='Pedidos', markdown='# Pedidos'),
    ])
    data.update(overrides)
    return SavePageDraftSchema(**data)


@pytest.mark.parametrize('call, code', [
    (lambda: rules.normalize_slug('Con Espacios'), AppErrorCode.HBK_INVALID_SLUG),
    (lambda: rules.normalize_locale('fr'), AppErrorCode.HBK_INVALID_LOCALE),
    (lambda: rules.normalize_semver('v1'), AppErrorCode.HBK_INVALID_VERSION),
    (lambda: rules.hash_markdown('   '), AppErrorCode.HBK_MARKDOWN_INVALID),
    (lambda: rules.hash_markdown('\ud800'), AppErrorCode.HBK_MARKDOWN_INVALID),
    (lambda: rules.feature_ids_for_audience('public', client_feature_id=uuid4(), admin_feature_id=None),
     AppErrorCode.HBK_FEATURE_INVALID),
    (lambda: rules.feature_ids_for_audience('wms', client_feature_id=None, admin_feature_id=uuid4()),
     AppErrorCode.HBK_FEATURE_INVALID),
    (lambda: rules.feature_ids_for_audience('admin', client_feature_id=uuid4(), admin_feature_id=None),
     AppErrorCode.HBK_FEATURE_INVALID),
])
def test_rules_reject_invalid_input(call, code):
    with pytest.raises(ValidationAppException) as exc:
        call()
    assert _code(exc) == code


def test_markdown_size_limit():
    with patch.object(rules, 'HANDBOOK_MARKDOWN_MAX_BYTES', 4):
        with pytest.raises(ValidationAppException):
            rules.hash_markdown('# demasiado')


def test_admin_audience_keeps_admin_feature():
    admin_id = uuid4()
    assert rules.feature_ids_for_audience('admin', client_feature_id=None, admin_feature_id=admin_id) == (None, admin_id)


def test_hierarchy_rules():
    a, b, c = uuid4(), uuid4(), uuid4()
    rules.assert_no_cycle(a, None, {})
    rules.assert_no_cycle(a, b, {b: None})
    for parents, parent in (({}, b), ({b: a}, b), ({b: c}, b)):
        with pytest.raises(ValidationAppException):
            rules.assert_no_cycle(a, parent, parents)
    with pytest.raises(ValidationAppException):
        rules.assert_no_cycle(a, b, {b: c, c: b})


def test_save_rejects_unknown_parent_and_duplicate_locale():
    docs, blobs = MemoryDocumentStore(), MemoryMarkdownStore()
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(_draft(parent_id=uuid4()), EDITOR)
    assert _code(exc) == AppErrorCode.HBK_HIERARCHY_CYCLE
    duplicated = _draft(versions=[
        LocaleVersionInput(locale='es', version='1.0', title='A', markdown='# A'),
        LocaleVersionInput(locale='es', version='1.1', title='B', markdown='# B'),
    ])
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(duplicated, EDITOR)
    assert _code(exc) == AppErrorCode.HBK_INVALID_LOCALE
    assert blobs.objects == {}


def test_save_compensates_uploaded_blobs_when_persistence_fails():
    docs, blobs = MemoryDocumentStore(), MemoryMarkdownStore()
    with patch.object(docs, 'save_draft', side_effect=RuntimeError('db down')):
        with pytest.raises(RuntimeError):
            SavePageDraftUseCase(docs, blobs).execute(_draft(), EDITOR)
    assert blobs.objects == {}


def test_manage_and_listing_errors():
    docs = MemoryDocumentStore([WMS, ADMIN])
    with pytest.raises(NotFoundException):
        GetManagePageUseCase(docs).execute(uuid4(), EDITOR)
    with pytest.raises(ValidationAppException) as exc:
        ListFeaturesUseCase(docs).execute(EDITOR, audience='public')
    assert _code(exc) == AppErrorCode.HBK_INVALID_AUDIENCE
    items, total = ListFeaturesUseCase(docs).execute(EDITOR, audience='admin', query=' BAND ')
    assert total == 1 and items[0].key == ADMIN.key
    api = FeatureOptionView(
        id=uuid4(), key='warehouse.api.list', label='API list', module='Warehouse',
        audience='wms', category='api',
    )
    docs = MemoryDocumentStore([WMS, api])
    only_api, total = ListFeaturesUseCase(docs).execute(EDITOR, audience='wms', category='api')
    assert total == 1 and only_api[0].key == api.key


@pytest.mark.parametrize('query', ['a', 'x' * 81])
def test_search_query_length_is_validated(query):
    with pytest.raises(ValidationAppException) as exc:
        SearchHandbookUseCase(MemoryDocumentStore()).execute('es', query, HandbookViewer.anonymous())
    assert _code(exc) == AppErrorCode.VALIDATION_ERROR


def test_memory_store_edges():
    docs, blobs = MemoryDocumentStore([WMS]), MemoryMarkdownStore()
    with pytest.raises(NotFoundException):
        blobs.get('missing')
    with pytest.raises(ValidationAppException):
        docs.resolve_feature_key('admin', WMS.id)
    assert docs.resolve_feature_key('wms', None) is None
    assert docs.get_manage(uuid4()) is None
    assert docs.page_summaries([uuid4()]) == {}
    assert docs.read_published_by_feature(' ', 'es') is None
    assert docs.draft_revision_id(uuid4()) is None
    assert docs.published_revision_id(uuid4()) is None

    page = SavePageDraftUseCase(docs, blobs).execute(_draft(show_in_sidebar=False), EDITOR)
    docs.pages[page.id].published = None
    assert docs.parent_map() == {page.id: None}
    docs.publish(page.id)
    other = SavePageDraftUseCase(docs, blobs).execute(_draft('vacia', versions=[], menu_title='Menú'), EDITOR)
    docs.pages[other.id].draft = None
    assert docs.parent_map() == {page.id: None}
    assert docs.list_catalog('es') == []
    assert docs.search('en', 'pedidos') == []
    assert docs.search('es', 'nada') == []
    assert docs.published_revision_id(page.id) is not None


def test_minio_store_delegates_and_logs_failed_delete():
    storage = MagicMock()
    storage.download_file.return_value = b'# md'
    store = MinioMarkdownStore(storage)
    store.put('k', b'# md')
    assert storage.upload_file.call_args.args[0].bucket == HANDBOOK_BUCKET
    assert store.get('k') == b'# md'
    storage.delete_file.side_effect = RuntimeError('minio down')
    with patch('handbook.features.docs.content.page.infrastructure.repositories.logger') as logger:
        store.delete('k')
    logger.warning.assert_called_once()
    with patch('handbook.features.docs.content.page.infrastructure.repositories.MinioStorageService') as service:
        assert MinioMarkdownStore().storage is service.return_value


def test_change_request_errors_and_republish():
    docs, blobs = MemoryDocumentStore(), MemoryMarkdownStore()
    requests = InMemoryChangeRequestRepository()
    with pytest.raises(NotFoundException):
        ApproveChangeRequestUseCase(requests).execute(uuid4(), EDITOR)
    with pytest.raises(NotFoundException):
        RejectChangeRequestUseCase(requests).execute(uuid4(), EDITOR)

    page = SavePageDraftUseCase(docs, blobs).execute(_draft(), EDITOR)
    with patch.object(docs, 'published_revision_id', return_value=docs.draft_revision_id(page.id)):
        submitted = SubmitPageDraftUseCase(requests, docs).execute(page_id=page.id, reason='x' * 20, viewer=EDITOR)
    assert submitted.published_version_id is None
    ApproveChangeRequestUseCase(requests).execute(submitted.id, EDITOR)
    with pytest.raises(ConflictException):
        ApproveChangeRequestUseCase(requests).execute(submitted.id, EDITOR)
    with pytest.raises(ConflictException):
        SubmitPageDraftUseCase(requests, docs).execute(page_id=uuid4(), reason='x' * 20, viewer=EDITOR)
