"""Repositorios ORM del handbook contra PostgreSQL (blobs en memoria)."""

from uuid import uuid4

import pytest

from core.errors import AppErrorCode, ConflictException, ValidationAppException
from handbook.core.constants import APPROVE_FEATURE_KEY, PROPOSE_FEATURE_KEY
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.content.page.application.use_cases import (
    DeleteHandbookChildUseCase,
    GetPublishedHelpUseCase,
    ListCatalogUseCase,
    SavePageDraftUseCase,
)
from handbook.features.docs.content.page.domain.schemas import LocaleVersionInput, SavePageDraftSchema
from handbook.features.docs.content.page.infrastructure.memory import MemoryMarkdownStore
from handbook.features.docs.content.page.infrastructure.repositories import DjangoHandbookDocumentStore
from handbook.features.docs.content.page.models import HandbookLocaleVersion, HandbookRevision
from handbook.features.docs.governance.change_request.application.use_cases import (
    ApproveChangeRequestUseCase,
    ListPendingChangeRequestsUseCase,
    RejectChangeRequestUseCase,
    SubmitPageDraftUseCase,
)
from handbook.features.docs.governance.change_request.infrastructure.repositories import (
    DjangoChangeRequestRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

REASON = 'Actualizamos la guía con el flujo vigente de bodega.'


@pytest.fixture
def blobs():
    return MemoryMarkdownStore()


@pytest.fixture
def docs(blobs):
    return DjangoHandbookDocumentStore(blobs)


@pytest.fixture
def requests_repo():
    return DjangoChangeRequestRepository()


@pytest.fixture
def editor():
    return HandbookViewer.admin(
        user_id=str(uuid4()),
        features=frozenset({PROPOSE_FEATURE_KEY, APPROVE_FEATURE_KEY}),
        is_superuser=True,
    )


@pytest.fixture
def wms_feature():
    from platform.features.security.access.functionalities.models import Functionality
    from platform.features.security.access.modules.models import Module
    from platform.features.security.access.sections.models import Section

    suffix = uuid4().hex[:8]
    section = Section.objects.create(code=f'sec-{suffix}', name='Almacenes')
    module = Module.objects.create(code=f'mod-{suffix}', name='Espacios', icon='box', route='/x', section=section)
    return Functionality.objects.create(key=f'location.spaces.{suffix}', label='Espacios', module=module)


@pytest.fixture
def admin_feature():
    from platform.features.security.access.roles.models import AdminFeature, AdminModule, AdminSection

    suffix = uuid4().hex[:8]
    section = AdminSection.objects.create(code=f'asec-{suffix}', name='Soporte')
    module = AdminModule.objects.create(code=f'amod-{suffix}', name='Bandeja', icon='inbox', route='/y', section=section)
    return AdminFeature.objects.create(key=f'support.inbox.{suffix}', label='Bandeja', module=module)


def _draft(slug, *, versions=None, **overrides):
    data = dict(slug=slug, audience='public', kind='manual', versions=versions if versions is not None else [
        LocaleVersionInput(locale='es', version='1.0', title=slug.title(), markdown=f'# {slug} contenido'),
    ])
    data.update(overrides)
    return SavePageDraftSchema(**data)


def _publish(docs, requests_repo, editor, page_id):
    saved = SubmitPageDraftUseCase(requests_repo, docs).execute(page_id=page_id, reason=REASON, viewer=editor)
    return ApproveChangeRequestUseCase(requests_repo).execute(saved.id, editor)


def _save(docs, blobs, editor, draft, page_id=None):
    return SavePageDraftUseCase(docs, blobs).execute(draft, editor, page_id=page_id)


def test_draft_publish_and_read_cycle(docs, blobs, requests_repo, editor):
    page = _save(docs, blobs, editor, _draft('pedidos'))
    assert page.status == 'draft'
    assert docs.read_published('pedidos', 'es') is None

    _publish(docs, requests_repo, editor, page.id)

    published = docs.read_published('pedidos', 'es')
    assert published.published_markdown == '# pedidos contenido'
    assert docs.read_published('pedidos', 'en') is None
    assert docs.taken_versions(page.id) == {('es', '1.0')}
    assert [row.locale for row in docs.published_locales(page.id)] == ['es']
    assert docs.get_manage(page.id).status == 'published'
    assert [hit.slug for hit in docs.search('es', 'contenido')] == ['pedidos']
    assert docs.search('es', 'inexistente') == []


def test_new_draft_replaces_previous_draft_and_keeps_published(docs, blobs, requests_repo, editor):
    page = _save(docs, blobs, editor, _draft('picking'))
    _publish(docs, requests_repo, editor, page.id)
    first = _save(docs, blobs, editor, _draft('picking', versions=[
        LocaleVersionInput(locale='es', version='1.1', title='Picking', markdown='# v1.1'),
    ]), page_id=page.id)
    second = _save(docs, blobs, editor, _draft('picking', versions=[
        LocaleVersionInput(locale='es', version='1.2', title='Picking', markdown='# v1.2'),
    ]), page_id=page.id)

    draft = HandbookRevision.objects.get(pk=docs.draft_revision_id(page.id))
    assert list(draft.locales.values_list('version', flat=True)) == ['1.2']
    assert HandbookRevision.objects.filter(page_id=page.id).count() == 2
    assert not HandbookLocaleVersion.objects.filter(page_id=page.id, version='1.1').exists()
    assert docs.read_published('picking', 'es').published_markdown == '# picking contenido'
    assert first.id == second.id
    assert second.status == 'draft'


def test_published_version_is_immutable_unless_unchanged(docs, blobs, requests_repo, editor):
    page = _save(docs, blobs, editor, _draft('packing'))
    _publish(docs, requests_repo, editor, page.id)

    same = _save(docs, blobs, editor, _draft('packing', menu_title=''), page_id=page.id)
    assert [row.version for row in same.versions] == ['1.0']
    with pytest.raises(ConflictException):
        _save(docs, blobs, editor, _draft('packing', versions=[
            LocaleVersionInput(locale='es', version='1.0', title='Packing', markdown='# otro'),
        ]), page_id=page.id)


def test_reject_discards_draft_and_pending_blocks_edits(docs, blobs, requests_repo, editor):
    page = _save(docs, blobs, editor, _draft('despachos'))
    pending = SubmitPageDraftUseCase(requests_repo, docs).execute(page_id=page.id, reason=REASON, viewer=editor)

    assert docs.has_pending(page.id)
    assert docs.list_manage(offset=0, limit=50)[0][0].status == 'pending'
    with pytest.raises(ConflictException):
        _save(docs, blobs, editor, _draft('despachos'), page_id=page.id)
    rows, total = ListPendingChangeRequestsUseCase(requests_repo, docs).execute(editor)
    assert total == 1
    assert rows[0].page_slug == 'despachos'
    assert rows[0].locales == ['es']

    RejectChangeRequestUseCase(requests_repo).execute(pending.id, editor, review_note='No aplica')
    assert docs.draft_revision_id(page.id) is None
    assert not docs.has_pending(page.id)


def test_menu_page_and_hierarchy_in_catalog(docs, blobs, requests_repo, editor):
    menu = _save(docs, blobs, editor, _draft('modulos', versions=[], menu_title='Módulos operativos'))
    child = _save(docs, blobs, editor, _draft('recepcion', parent_id=menu.id))
    hidden = _save(docs, blobs, editor, _draft('interna', show_in_sidebar=False))
    for page in (menu, child, hidden):
        _publish(docs, requests_repo, editor, page.id)

    nodes = {node.slug: node for node in ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous())}
    assert set(nodes) == {'modulos', 'recepcion'}
    assert nodes['modulos'].has_content is False
    assert nodes['recepcion'].parent_id == menu.id
    assert docs.parent_map()[child.id] == menu.id
    assert docs.slug_owner('recepcion') == child.id
    with pytest.raises(ValidationAppException):
        _save(docs, blobs, editor, _draft('modulos', versions=[], menu_title='', parent_id=child.id), page_id=menu.id)


def test_feature_bound_pages_follow_feature_state(docs, blobs, requests_repo, editor, wms_feature):
    page = _save(docs, blobs, editor, _draft('espacios', audience='wms', client_feature_id=wms_feature.id))
    _publish(docs, requests_repo, editor, page.id)
    reader = HandbookViewer.client(user_id=str(uuid4()), schema_name='acme', features=frozenset({wms_feature.key}))

    assert docs.read_published_by_feature(wms_feature.key, 'es').slug == 'espacios'
    assert docs.read_published_by_feature(wms_feature.key, 'en') is None
    assert docs.read_published_by_feature('  ', 'es') is None
    assert GetPublishedHelpUseCase(docs).execute(wms_feature.key, 'en', reader).locale == 'es'
    assert docs.get_manage(page.id).feature_label == f'Espacios · {wms_feature.key}'
    assert docs.list_catalog('es')[0].feature_key == wms_feature.key

    wms_feature.is_active = False
    wms_feature.save(update_fields=['is_active'])
    assert docs.list_catalog('es') == []
    assert docs.read_published('espacios', 'es') is None
    assert docs.search('es', 'contenido') == []
    with pytest.raises(ValidationAppException):
        docs.resolve_feature_key('wms', wms_feature.id)


def test_feature_catalog_listing(docs, wms_feature, admin_feature):
    assert docs.resolve_feature_key('admin', admin_feature.id) == admin_feature.key
    assert docs.resolve_feature_key('wms', None) is None
    items, total = docs.list_features(audience='wms', query=wms_feature.key, offset=0, limit=10)
    assert total == 1 and items[0].module == 'Espacios' and items[0].audience == 'wms'
    items, total = docs.list_features(audience='admin', query='bandeja', offset=0, limit=10)
    assert admin_feature.id in {item.id for item in items}


def test_page_summaries_in_batch(docs, blobs, editor):
    page = _save(docs, blobs, editor, _draft('inventario'))
    summaries = docs.page_summaries([page.id, uuid4()])
    assert list(summaries) == [page.id]
    assert summaries[page.id].slug == 'inventario'
    assert docs.page_summaries([]) == {}


def test_change_request_repository_edges(requests_repo):
    assert requests_repo.get(uuid4()) is None
    assert requests_repo.get_pending_for_page(uuid4()) is None


def test_drop_draft_never_deletes_published_or_reviewed_revisions(docs, blobs, requests_repo, editor):
    from handbook.features.docs.content.page.models import HandbookPage

    assert docs.get_manage(uuid4()) is None
    page = _save(docs, blobs, editor, _draft('ubicaciones'))
    _publish(docs, requests_repo, editor, page.id)
    row = HandbookPage.objects.get(pk=page.id)
    row.draft_revision_id = row.published_revision_id
    row.save(update_fields=['draft_revision'])

    _save(docs, blobs, editor, _draft('ubicaciones', versions=[
        LocaleVersionInput(locale='es', version='2.0', title='Ubicaciones', markdown='# v2'),
    ]), page_id=page.id)
    assert HandbookRevision.objects.filter(pk=row.published_revision_id).exists()
    assert docs.read_published('ubicaciones', 'es').published_markdown == '# ubicaciones contenido'


def test_delete_published_child_drops_rows_and_markdown(docs, blobs, requests_repo, editor):
    from handbook.features.docs.content.page.models import HandbookPage
    from handbook.features.docs.governance.change_request.models import HandbookChangeRequest

    parent = _save(docs, blobs, editor, _draft('modulos', menu_title='Módulos', versions=[]))
    child = _save(docs, blobs, editor, _draft('recepcion', parent_id=parent.id))
    _publish(docs, requests_repo, editor, child.id)
    key = child.versions[0].object_key
    assert key in blobs.objects

    slug = DeleteHandbookChildUseCase(docs, blobs).execute(child.id, editor)

    assert slug == 'recepcion'
    assert not HandbookPage.objects.filter(pk=child.id).exists()
    assert not HandbookRevision.objects.filter(page_id=child.id).exists()
    assert not HandbookLocaleVersion.objects.filter(page_id=child.id).exists()
    assert not HandbookChangeRequest.objects.filter(page_id=child.id).exists()
    assert HandbookPage.objects.filter(pk=parent.id).exists()
    assert key not in blobs.objects
    assert docs.read_published('recepcion', 'es') is None


def test_delete_blocked_while_published_grandchild_still_hangs_from_it(docs, blobs, requests_repo, editor):
    from handbook.features.docs.content.page.models import HandbookPage

    root = _save(docs, blobs, editor, _draft('modulos', menu_title='Módulos', versions=[]))
    child = _save(docs, blobs, editor, _draft('recepcion', parent_id=root.id))
    grandchild = _save(docs, blobs, editor, _draft('muelles', parent_id=child.id))
    _publish(docs, requests_repo, editor, grandchild.id)
    _save(docs, blobs, editor, _draft('muelles', parent_id=root.id, versions=[
        LocaleVersionInput(locale='es', version='1.1', title='Muelles', markdown='# v1.1'),
    ]), page_id=grandchild.id)

    with pytest.raises(ConflictException) as exc:
        DeleteHandbookChildUseCase(docs, blobs).execute(child.id, editor)

    assert exc.value.code == AppErrorCode.HBK_HAS_CHILDREN
    assert HandbookPage.objects.filter(pk=child.id).exists()
    assert child.versions[0].object_key in blobs.objects


def test_save_draft_rejects_parent_deleted_after_validation(docs, editor):
    draft = _draft('huerfana', parent_id=uuid4())

    with pytest.raises(ValidationAppException):
        docs.save_draft(uuid4(), draft, author_id=None, stored=[], carried=[])


def test_delete_page_of_unknown_id_is_noop(docs):
    assert docs.delete_page(uuid4()) == []


def test_drop_draft_keeps_revisions_referenced_by_resolved_requests(docs, blobs, requests_repo, editor):
    page = _save(docs, blobs, editor, _draft('kardex'))
    submitted = SubmitPageDraftUseCase(requests_repo, docs).execute(page_id=page.id, reason=REASON, viewer=editor)
    requests_repo.save(submitted.model_copy(update={'status': 'rejected'}))

    _save(docs, blobs, editor, _draft('kardex', versions=[
        LocaleVersionInput(locale='es', version='1.1', title='Kardex', markdown='# v1.1'),
    ]), page_id=page.id)
    assert HandbookRevision.objects.filter(pk=submitted.working_version_id).exists()
