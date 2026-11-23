"""Lectura publicada: funcionalidades inactivas, ayuda por funcionalidad y reglas de catálogo."""

from uuid import uuid4

import pytest

from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from handbook.core.constants import PROPOSE_FEATURE_KEY
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.content.page.application.use_cases import (
    GetPublishedHelpUseCase,
    GetPublishedPageUseCase,
    ListCatalogUseCase,
    SavePageDraftUseCase,
    SearchHandbookUseCase,
)
from handbook.features.docs.content.page.domain.rules import catalog_title, feature_display, feature_ref
from handbook.features.docs.content.page.domain.schemas import (
    FeatureOptionView,
    LocaleVersionInput,
    SavePageDraftSchema,
)
from handbook.features.docs.content.page.infrastructure.memory import MemoryDocumentStore, MemoryMarkdownStore

pytestmark = pytest.mark.unit

FEATURE = FeatureOptionView(id=uuid4(), key='warehouse.spaces.view', label='Espacios', module='Warehouse', audience='wms')
READER = HandbookViewer.client(user_id=str(uuid4()), schema_name='acme', features=frozenset({FEATURE.key}))


def _tech():
    return HandbookViewer.admin(user_id=str(uuid4()), features=frozenset({PROPOSE_FEATURE_KEY}))


def _version(locale='es', title='Espacios'):
    return LocaleVersionInput(locale=locale, version='1.0', title=title, description='Red física', markdown=f'# {title}')


def _publish(docs, **overrides):
    data = dict(
        slug='espacios', parent_id=None, show_in_sidebar=True, audience='wms', kind='manual',
        client_feature_id=FEATURE.id, admin_feature_id=None, sort_order=1, versions=[_version()],
    )
    data.update(overrides)
    saved = SavePageDraftUseCase(docs, MemoryMarkdownStore()).execute(SavePageDraftSchema(**data), _tech())
    docs.publish(saved.id)
    return saved


def test_deactivated_feature_hides_its_page_without_breaking_the_tree():
    docs = MemoryDocumentStore([FEATURE])
    _publish(docs)
    _publish(docs, slug='inicio', audience='public', client_feature_id=None, versions=[_version(title='Inicio')])
    docs.features.pop(FEATURE.id)

    assert [node.slug for node in ListCatalogUseCase(docs).execute('es', READER)] == ['inicio']
    assert SearchHandbookUseCase(docs).execute('es', 'espacios', READER) == []
    with pytest.raises(NotFoundException):
        GetPublishedPageUseCase(docs).execute('espacios', 'es', READER)


def test_help_skips_menu_pages_and_falls_back_to_the_other_language():
    docs = MemoryDocumentStore([FEATURE])
    _publish(docs, slug='almacenes', sort_order=0, versions=[], menu_title='Almacenes')
    _publish(docs, versions=[_version(locale='en', title='Spaces')])

    page = GetPublishedHelpUseCase(docs).execute(FEATURE.key, 'es', READER)

    assert (page.slug, page.locale, page.title) == ('espacios', 'en', 'Spaces')


def test_help_requires_a_feature_key_and_reports_missing_guides():
    docs = MemoryDocumentStore([FEATURE])
    with pytest.raises(ValidationAppException) as exc:
        GetPublishedHelpUseCase(docs).execute('  ', 'es', READER)
    assert exc.value.code == AppErrorCode.VALIDATION_ERROR
    with pytest.raises(NotFoundException):
        GetPublishedHelpUseCase(docs).execute(FEATURE.key, 'es', READER)


def test_manage_view_labels_only_features_of_the_page_audience():
    docs = MemoryDocumentStore([FEATURE])
    saved = _publish(docs)
    assert docs.get_manage(saved.id).feature_label == 'Espacios · warehouse.spaces.view'
    docs.features.pop(FEATURE.id)
    assert docs.get_manage(saved.id).feature_label == ''


def test_catalog_rules():
    wms, admin = uuid4(), uuid4()
    assert feature_ref('wms', wms, admin) == wms
    assert feature_ref('admin', wms, admin) == admin
    assert feature_ref('public', wms, admin) is None
    assert catalog_title({'es': 'Pedidos'}, 'es', 'Menú') == ('Pedidos', True)
    assert catalog_title({'en': 'Orders'}, 'es', 'Menú') == ('', False)
    assert catalog_title({}, 'es', '  Menú ') == ('Menú', False)
    assert feature_display('Espacios', 'warehouse.spaces.view') == 'Espacios · warehouse.spaces.view'

