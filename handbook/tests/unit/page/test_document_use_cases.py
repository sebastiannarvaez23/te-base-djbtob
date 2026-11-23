"""Borrador, jerarquía, semver y visibilidad del handbook."""

from uuid import uuid4

import pytest

from core.errors import (
    AppErrorCode,
    AuthException,
    ConflictException,
    NotFoundException,
    PermissionException,
    ValidationAppException,
)
from handbook.core.constants import APPROVE_FEATURE_KEY, PROPOSE_FEATURE_KEY
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.content.page.application.use_cases import (
    DeleteHandbookChildUseCase,
    GetPublishedHelpUseCase,
    GetPublishedPageUseCase,
    ListCatalogUseCase,
    SavePageDraftUseCase,
)
from handbook.features.docs.content.page.domain.schemas import (
    FeatureOptionView,
    LocaleVersionInput,
    SavePageDraftSchema,
)
from handbook.features.docs.content.page.infrastructure.memory import MemoryDocumentStore, MemoryMarkdownStore
from handbook.features.docs.governance.change_request.application.use_cases import SubmitPageDraftUseCase
from handbook.features.docs.governance.change_request.infrastructure.memory import InMemoryChangeRequestRepository


pytestmark = pytest.mark.unit

FEATURE = FeatureOptionView(
    id=uuid4(), key='orders.view', label='Orders', module='Warehouse', audience='wms',
)


def _tech():
    return HandbookViewer.admin(user_id=str(uuid4()), features=frozenset({PROPOSE_FEATURE_KEY}))


def _draft(**overrides):
    data = dict(
        slug='pedidos',
        parent_id=None,
        show_in_sidebar=True,
        audience='public',
        kind='manual',
        client_feature_id=None,
        admin_feature_id=None,
        sort_order=1,
        versions=[LocaleVersionInput(
            locale='es', version='1.0', title='Pedidos', description='Flujo', markdown='# Pedidos',
        )],
    )
    data.update(overrides)
    return SavePageDraftSchema(**data)


def test_save_public_draft_and_hide_until_published():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    saved = SavePageDraftUseCase(docs, blobs).execute(_draft(), _tech())
    assert saved.status == 'draft'
    assert blobs.objects[saved.versions[0].object_key] == b'# Pedidos'
    assert ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous()) == []
    with pytest.raises(NotFoundException):
        GetPublishedPageUseCase(docs).execute('pedidos', 'es', HandbookViewer.anonymous())


def test_help_returns_the_published_page_of_the_feature():
    docs = MemoryDocumentStore([FEATURE])
    blobs = MemoryMarkdownStore()
    saved = SavePageDraftUseCase(docs, blobs).execute(
        _draft(
            slug='espacios',
            audience='wms',
            client_feature_id=FEATURE.id,
            versions=[LocaleVersionInput(
                locale='es', version='1.0', title='Espacios', description='Red física', markdown='# Espacios',
            )],
        ),
        _tech(),
    )
    docs.publish(saved.id)
    viewer = HandbookViewer.client(
        user_id=str(uuid4()), features=frozenset({FEATURE.key}), schema_name='acme',
    )
    page = GetPublishedHelpUseCase(docs).execute(FEATURE.key, 'es', viewer)
    assert page.title == 'Espacios'
    assert page.published_markdown == '# Espacios'
    assert page.feature_key == FEATURE.key
    with pytest.raises(NotFoundException):
        GetPublishedHelpUseCase(docs).execute(
            FEATURE.key, 'es', HandbookViewer.client(user_id='u', features=frozenset(), schema_name='acme'),
        )
    with pytest.raises(NotFoundException):
        GetPublishedHelpUseCase(docs).execute('orders.other', 'es', viewer)


def test_rejects_cycle_slug_and_mixed_features():
    docs = MemoryDocumentStore([FEATURE])
    blobs = MemoryMarkdownStore()
    parent = SavePageDraftUseCase(docs, blobs).execute(_draft(slug='raiz'), _tech())
    child = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='hijo', parent_id=parent.id), _tech(),
    )
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(
            _draft(slug='raiz', parent_id=child.id), _tech(), page_id=parent.id,
        )
    assert exc.value.code == AppErrorCode.HBK_HIERARCHY_CYCLE
    with pytest.raises(ConflictException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(_draft(slug='hijo'), _tech())
    assert exc.value.code == AppErrorCode.HBK_SLUG_TAKEN
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(
            _draft(audience='public', client_feature_id=FEATURE.id), _tech(),
        )
    assert exc.value.code == AppErrorCode.HBK_FEATURE_INVALID


def test_api_page_requires_api_category_feature():
    ui = FeatureOptionView(
        id=uuid4(), key='orders.view', label='Orders', module='Warehouse',
        audience='wms', category='features',
    )
    api = FeatureOptionView(
        id=uuid4(), key='warehouse.api.warehouse-list', label='API warehouses',
        module='Warehouse', audience='wms', category='api',
    )
    docs = MemoryDocumentStore([ui, api])
    blobs = MemoryMarkdownStore()
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(
            _draft(
                slug='api-warehouses',
                audience='wms',
                kind='api',
                http_method='GET',
                client_feature_id=ui.id,
            ),
            _tech(),
        )
    assert exc.value.code == AppErrorCode.HBK_FEATURE_INVALID
    saved = SavePageDraftUseCase(docs, blobs).execute(
        _draft(
            slug='api-warehouses',
            audience='wms',
            kind='api',
            http_method='GET',
            client_feature_id=api.id,
        ),
        _tech(),
    )
    assert saved.client_feature_id == api.id
    assert saved.kind == 'api'


def test_second_locale_keeps_previous_language_on_new_version():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    first = SavePageDraftUseCase(docs, blobs).execute(_draft(), _tech())
    docs.publish(first.id)
    updated = SavePageDraftUseCase(docs, blobs).execute(
        _draft(versions=[LocaleVersionInput(
            locale='en', version='1.0', title='Orders', description='', markdown='# Orders',
        )]),
        _tech(),
        page_id=first.id,
    )
    locales = {row.locale for row in updated.versions}
    assert locales == {'es', 'en'}


def test_header_change_reuses_the_published_version_without_bump():
    docs = MemoryDocumentStore([FEATURE])
    blobs = MemoryMarkdownStore()
    first = SavePageDraftUseCase(docs, blobs).execute(_draft(), _tech())
    docs.publish(first.id)
    published_id = first.versions[0].id
    uploads = dict(blobs.objects)

    updated = SavePageDraftUseCase(docs, blobs).execute(
        _draft(audience='wms', client_feature_id=FEATURE.id, sort_order=4),
        _tech(),
        page_id=first.id,
    )

    assert updated.audience == 'wms'
    assert updated.sort_order == 4
    assert [(row.id, row.version) for row in updated.versions] == [(published_id, '1.0')]
    assert blobs.objects == uploads


def test_create_keeps_the_configured_menu_slot():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    first = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='alfa', sort_order=0, menu_title='Alfa'), _tech(),
    )
    second = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='beta', sort_order=0, menu_title='Beta'), _tech(),
    )
    child = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='hijo', parent_id=first.id, sort_order=0, menu_title='Hijo'), _tech(),
    )
    created = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='gamma', sort_order=1, menu_title='Gamma'), _tech(),
    )

    assert docs.get_manage(second.id).sort_order == 0
    assert docs.get_manage(created.id).sort_order == 1
    assert docs.get_manage(first.id).sort_order == 2
    assert docs.get_manage(child.id).sort_order == 0

    edited = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='beta', sort_order=4, menu_title='Beta'), _tech(), page_id=second.id,
    )
    assert edited.sort_order == 4
    assert docs.get_manage(created.id).sort_order == 1
    assert docs.get_manage(first.id).sort_order == 2


def test_markdown_lives_in_a_folder_named_after_the_page():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    saved = SavePageDraftUseCase(docs, blobs).execute(_draft(), _tech())
    assert saved.versions[0].object_key == 'handbook/pages/pedidos/es/1.0.md'

    docs.pages[saved.id].slug = 'pedidos-antiguo'
    reused = SavePageDraftUseCase(docs, blobs).execute(
        _draft(versions=[LocaleVersionInput(
            locale='es', version='1.0', title='Nuevo', description='Otro', markdown='# Nuevo',
        )]),
        _tech(),
    )
    folder = str(reused.id).replace('-', '')[:8]
    assert reused.versions[0].object_key == f'handbook/pages/pedidos--{folder}/es/1.0.md'
    assert blobs.objects['handbook/pages/pedidos/es/1.0.md'] == b'# Pedidos'


def test_resaving_a_draft_never_overwrites_markdown_a_row_references():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    first = SavePageDraftUseCase(docs, blobs).execute(_draft(), _tech())
    original_key = first.versions[0].object_key

    class FailingSave(Exception):
        pass

    def fail(*_args, **_kwargs):
        raise FailingSave()

    edited = _draft(versions=[LocaleVersionInput(
        locale='es', version='1.0', title='Pedidos', description='Flujo', markdown='# Editado',
    )])
    save_draft = docs.save_draft
    docs.save_draft = fail
    with pytest.raises(FailingSave):
        SavePageDraftUseCase(docs, blobs).execute(edited, _tech(), page_id=first.id)
    docs.save_draft = save_draft

    assert blobs.objects[original_key] == b'# Pedidos'
    assert set(blobs.objects) == {original_key}

    saved = SavePageDraftUseCase(docs, blobs).execute(edited, _tech(), page_id=first.id)
    new_key = saved.versions[0].object_key
    assert new_key.startswith('handbook/pages/pedidos/es/1.0+') and new_key.endswith('.md')
    assert blobs.objects[new_key] == b'# Editado'
    assert blobs.objects[original_key] == b'# Pedidos'


@pytest.mark.parametrize(('owners', 'expected'), [
    ({}, ('handbook/pages/pedidos/es/1.0.md', True)),
    ({'handbook/pages/pedidos/es/1.0.md': 'other'}, ('handbook/pages/pedidos--{short}/es/1.0.md', True)),
    (
        {'handbook/pages/pedidos/es/1.0.md': 'self'},
        ('handbook/pages/pedidos/es/1.0+abcdef012345.md', True),
    ),
    (
        {
            'handbook/pages/pedidos/es/1.0.md': 'self',
            'handbook/pages/pedidos/es/1.0+abcdef012345.md': 'self',
        },
        ('handbook/pages/pedidos/es/1.0+abcdef012345.md', False),
    ),
    (
        {
            'handbook/pages/pedidos/es/1.0.md': 'other',
            'handbook/pages/pedidos--{short}/es/1.0.md': 'self',
        },
        ('handbook/pages/pedidos--{short}/es/1.0+abcdef012345.md', True),
    ),
])
def test_object_key_never_points_at_live_markdown(owners, expected):
    page_id = uuid4()
    other_id = uuid4()
    short = str(page_id).replace('-', '')[:8]
    resolved = {
        key.format(short=short): page_id if owner == 'self' else other_id
        for key, owner in owners.items()
    }
    docs = MemoryDocumentStore()
    docs.object_key_owner = resolved.get
    key, is_new = SavePageDraftUseCase(docs, MemoryMarkdownStore())._free_object_key(
        'pedidos', page_id, 'es', '1.0', 'abcdef0123456789',
    )
    assert (key, is_new) == (expected[0].format(short=short), expected[1])


def test_api_page_carries_its_http_method_to_the_menu():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    saved = SavePageDraftUseCase(docs, blobs).execute(
        _draft(kind='api', http_method=' post ', icon='bx-package'), _tech(),
    )
    assert saved.http_method == 'POST'
    docs.publish(saved.id)

    [node] = ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous())
    assert (node.kind, node.http_method, node.icon) == ('api', 'POST', 'bx-package')


def test_api_page_requires_a_method_and_other_kinds_drop_it():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(_draft(kind='api', http_method=''), _tech())
    assert exc.value.code == AppErrorCode.HBK_HTTP_METHOD_REQUIRED
    with pytest.raises(ValidationAppException):
        SavePageDraftUseCase(docs, blobs).execute(_draft(kind='api', http_method='TRACE'), _tech())
    assert docs.pages == {}

    manual = SavePageDraftUseCase(docs, blobs).execute(_draft(http_method='GET'), _tech())
    assert manual.http_method == ''


def test_changed_content_on_a_published_version_requires_bump():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    first = SavePageDraftUseCase(docs, blobs).execute(_draft(), _tech())
    docs.publish(first.id)
    for change in ({'markdown': '# Pedidos v2'}, {'title': 'Pedidos de salida'}):
        values = dict(locale='es', version='1.0', title='Pedidos', description='Flujo', markdown='# Pedidos')
        values.update(change)
        with pytest.raises(ConflictException) as exc:
            SavePageDraftUseCase(docs, blobs).execute(
                _draft(versions=[LocaleVersionInput(**values)]), _tech(), page_id=first.id,
            )
        assert exc.value.code == AppErrorCode.HBK_INVALID_VERSION

    bumped = SavePageDraftUseCase(docs, blobs).execute(
        _draft(versions=[LocaleVersionInput(
            locale='es', version='1.1', title='Pedidos', description='Flujo', markdown='# Pedidos v2',
        )]),
        _tech(),
        page_id=first.id,
    )
    assert [row.version for row in bumped.versions] == ['1.1']


def test_menu_page_without_content_groups_its_children():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(_draft(slug='modulos', versions=[]), _tech())
    assert exc.value.code == AppErrorCode.HBK_MENU_TITLE_REQUIRED

    menu = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='modulos', versions=[], menu_title='  Módulos operativos '), _tech(),
    )
    assert menu.versions == []
    assert menu.menu_title == 'Módulos operativos'
    assert blobs.objects == {}
    child = SavePageDraftUseCase(docs, blobs).execute(_draft(parent_id=menu.id), _tech())
    docs.publish(menu.id)
    docs.publish(child.id)

    nodes = {node.slug: node for node in ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous())}
    assert nodes['modulos'].title == 'Módulos operativos'
    assert nodes['modulos'].has_content is False
    assert nodes['pedidos'].parent_id == menu.id
    assert nodes['pedidos'].has_content is True
    with pytest.raises(NotFoundException):
        GetPublishedPageUseCase(docs).execute('modulos', 'es', HandbookViewer.anonymous())


def test_session_without_a_specific_feature_sees_the_matching_audience():
    docs = MemoryDocumentStore([FEATURE])
    blobs = MemoryMarkdownStore()
    operation = SavePageDraftUseCase(docs, blobs).execute(
        _draft(
            slug='operacion', audience='wms', client_feature_id=None,
            versions=[], menu_title='Operación',
        ),
        _tech(),
    )
    private = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='pedidos', parent_id=operation.id, audience='wms', client_feature_id=FEATURE.id),
        _tech(),
    )
    platform = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='plataforma', audience='admin', versions=[], menu_title='Plataforma'),
        _tech(),
    )
    for page in (operation, private, platform):
        docs.publish(page.id)

    client = HandbookViewer.client(user_id='u1', schema_name='acme', features=frozenset())
    assert {node.slug for node in ListCatalogUseCase(docs).execute('es', client)} == {'operacion'}

    granted = HandbookViewer.client(
        user_id='u1', schema_name='acme', features=frozenset({FEATURE.key}),
    )
    assert {node.slug for node in ListCatalogUseCase(docs).execute('es', granted)} == {'operacion', 'pedidos'}

    admin = HandbookViewer.admin(user_id='a1', features=frozenset())
    assert {node.slug for node in ListCatalogUseCase(docs).execute('es', admin)} == {
        'operacion', 'pedidos', 'plataforma',
    }
    assert ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous()) == []


def test_childless_menu_stays_in_the_sidebar():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    menu = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='manuales', versions=[], menu_title='Manuales'), _tech(),
    )
    docs.publish(menu.id)

    nodes = ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous())
    assert [node.slug for node in nodes] == ['manuales']
    assert nodes[0].has_content is False


def test_anonymous_tree_hides_menus_without_public_children():
    docs = MemoryDocumentStore([FEATURE])
    blobs = MemoryMarkdownStore()
    root = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='operacion', versions=[], menu_title='Operación'), _tech(),
    )
    menu = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='almacenes', versions=[], menu_title='Almacenes', parent_id=root.id), _tech(),
    )
    private = SavePageDraftUseCase(docs, blobs).execute(
        _draft(parent_id=menu.id, audience='wms', client_feature_id=FEATURE.id), _tech(),
    )
    for page in (root, menu, private):
        docs.publish(page.id)

    anonymous = ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous())
    assert anonymous == []

    client = HandbookViewer.client(user_id='u1', schema_name='acme', features=frozenset({FEATURE.key}))
    assert {node.slug for node in ListCatalogUseCase(docs).execute('es', client)} == {
        'operacion', 'almacenes', 'pedidos',
    }


def test_manage_page_returns_the_feature_name():
    from handbook.features.docs.content.page.application.use_cases import GetManagePageUseCase
    docs = MemoryDocumentStore([FEATURE])
    blobs = MemoryMarkdownStore()
    saved = SavePageDraftUseCase(docs, blobs).execute(
        _draft(audience='wms', client_feature_id=FEATURE.id), _tech(),
    )
    page = GetManagePageUseCase(docs).execute(saved.id, _tech())
    assert page.feature_label == 'Orders · orders.view'
    public = SavePageDraftUseCase(docs, blobs).execute(_draft(slug='publica'), _tech())
    assert GetManagePageUseCase(docs).execute(public.id, _tech()).feature_label == ''


def test_submit_requires_a_draft():
    docs = MemoryDocumentStore()
    repo = InMemoryChangeRequestRepository()
    with pytest.raises(ConflictException) as exc:
        SubmitPageDraftUseCase(repo, docs).execute(
            page_id=uuid4(),
            reason='Actualizamos el flujo de reserva de pedidos.',
            viewer=_tech(),
        )
    assert exc.value.code == AppErrorCode.HBK_DRAFT_REQUIRED


def test_duplicate_locale_and_parent_clears_icon():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    with pytest.raises(ValidationAppException) as exc:
        SavePageDraftUseCase(docs, blobs).execute(_draft(versions=[
            LocaleVersionInput(locale='es', version='1.0', title='A', description='Uno', markdown='# A'),
            LocaleVersionInput(locale='es', version='1.1', title='B', description='Dos', markdown='# B'),
        ]), _tech())
    assert exc.value.code == AppErrorCode.HBK_INVALID_LOCALE
    saved = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='raiz', icon='bx-book'), _tech(),
    )
    assert saved.icon == 'bx-book'
    child = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='hijo', parent_id=saved.id, icon='bx-book'), _tech(),
    )
    assert child.icon == ''


def test_failed_save_removes_uploaded_markdown():
    class BrokenStore(MemoryDocumentStore):
        def save_draft(self, *args, **kwargs):
            raise ConflictException(AppErrorCode.HBK_SLUG_TAKEN)

    blobs = MemoryMarkdownStore()
    with pytest.raises(ConflictException):
        SavePageDraftUseCase(BrokenStore(), blobs).execute(_draft(), _tech())
    assert blobs.objects == {}


def test_features_are_filtered_and_paged():
    from handbook.features.docs.content.page.application.use_cases import ListFeaturesUseCase
    second = FeatureOptionView(
        id=uuid4(), key='orders.pick', label='Picking', module='Warehouse', audience='wms',
    )
    admin = FeatureOptionView(
        id=uuid4(), key='admin.docs.propose', label='Propose', module='Handbook', audience='admin',
    )
    docs = MemoryDocumentStore([FEATURE, second, admin])
    items, total = ListFeaturesUseCase(docs).execute(_tech(), audience='wms', query='pick', page=0, page_size=1)
    assert total == 1
    assert items[0].key == 'orders.pick'


def test_anonymous_does_not_see_wms_page_after_publish():
    docs = MemoryDocumentStore([FEATURE])
    blobs = MemoryMarkdownStore()
    saved = SavePageDraftUseCase(docs, blobs).execute(
        _draft(audience='wms', client_feature_id=FEATURE.id), _tech(),
    )
    docs.publish(saved.id)
    assert ListCatalogUseCase(docs).execute('es', HandbookViewer.anonymous()) == []
    client = HandbookViewer.client(user_id=str(uuid4()), features=frozenset({FEATURE.key}), schema_name='acme')
    assert len(ListCatalogUseCase(docs).execute('es', client)) == 1
    assert APPROVE_FEATURE_KEY


def test_delete_child_removes_page_and_markdown():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    parent = SavePageDraftUseCase(docs, blobs).execute(_draft(slug='raiz'), _tech())
    child = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='hijo', parent_id=parent.id), _tech(),
    )
    key = child.versions[0].object_key
    assert key in blobs.objects

    slug = DeleteHandbookChildUseCase(docs, blobs).execute(child.id, _tech())

    assert slug == 'hijo'
    assert docs.get_manage(child.id) is None
    assert docs.get_manage(parent.id).slug == 'raiz'
    assert key not in blobs.objects


def test_delete_refuses_published_root_whose_draft_was_nested():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    root = SavePageDraftUseCase(docs, blobs).execute(_draft(slug='raiz'), _tech())
    docs.publish(root.id)
    other = SavePageDraftUseCase(docs, blobs).execute(_draft(slug='otro'), _tech())
    published = docs.pages[root.id].published
    docs.pages[root.id].draft = {**published, 'parent_id': other.id}
    assert docs.get_manage(root.id).parent_id == other.id

    with pytest.raises(ValidationAppException) as error:
        DeleteHandbookChildUseCase(docs, blobs).execute(root.id, _tech())

    assert error.value.code == AppErrorCode.HBK_DELETE_ROOT
    assert docs.get_manage(root.id) is not None
    assert docs.read_published('raiz', 'es') is not None


def test_delete_refuses_root_parent_with_children_and_missing_page():
    docs = MemoryDocumentStore()
    blobs = MemoryMarkdownStore()
    parent = SavePageDraftUseCase(docs, blobs).execute(_draft(slug='raiz'), _tech())
    child = SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='hijo', parent_id=parent.id), _tech(),
    )
    SavePageDraftUseCase(docs, blobs).execute(
        _draft(slug='nieto', parent_id=child.id), _tech(),
    )
    use_case = DeleteHandbookChildUseCase(docs, blobs)

    with pytest.raises(ValidationAppException) as root_error:
        use_case.execute(parent.id, _tech())
    assert root_error.value.code == AppErrorCode.HBK_DELETE_ROOT

    with pytest.raises(ConflictException) as grouped_error:
        use_case.execute(child.id, _tech())
    assert grouped_error.value.code == AppErrorCode.HBK_HAS_CHILDREN
    assert docs.get_manage(child.id) is not None

    with pytest.raises(NotFoundException) as missing:
        use_case.execute(uuid4(), _tech())
    assert missing.value.code == AppErrorCode.HBK_NOT_FOUND

    with pytest.raises(PermissionException):
        use_case.execute(child.id, HandbookViewer.admin(user_id=str(uuid4()), features=frozenset()))
    with pytest.raises(AuthException):
        use_case.execute(child.id, HandbookViewer.anonymous())
    assert docs.delete_page(uuid4()) == []
