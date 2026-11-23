"""ACL del handbook: audiencia + feature_key + estado, sin base de datos."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.errors import AppErrorCode, AuthException, NotFoundException, PermissionException
from handbook.core.access import (
    HandbookAccessTarget,
    assert_can_approve,
    assert_can_manage,
    assert_can_propose,
    assert_can_view,
    assert_valid_audience,
    assert_valid_kind,
    can_approve,
    can_manage,
    can_propose,
    can_view,
    filter_visible,
)
from handbook.core.constants import (
    APPROVE_FEATURE_KEY,
    AUDIENCE_ADMIN,
    AUDIENCE_PUBLIC,
    AUDIENCE_WMS,
    KIND_MANUAL,
    PROPOSE_FEATURE_KEY,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
)
from handbook.core.session import resolve_viewer, viewer_from_user
from handbook.core.storage import asset_object_key, markdown_object_key
from handbook.core.viewer import HandbookViewer


pytestmark = pytest.mark.unit


def _public(**kwargs) -> HandbookAccessTarget:
    return HandbookAccessTarget(audience=AUDIENCE_PUBLIC, status=STATUS_PUBLISHED, **kwargs)


def _admin_doc(feature_key='admin.tenants.view', **kwargs) -> HandbookAccessTarget:
    return HandbookAccessTarget(
        audience=AUDIENCE_ADMIN,
        feature_key=feature_key,
        status=STATUS_PUBLISHED,
        **kwargs,
    )


def _wms(feature_key='orders.create', **kwargs) -> HandbookAccessTarget:
    return HandbookAccessTarget(
        audience=AUDIENCE_WMS,
        feature_key=feature_key,
        status=STATUS_PUBLISHED,
        **kwargs,
    )


class TestPublicAudience:

    def test_anonymous_sees_published_public(self):
        assert can_view(_public(), HandbookViewer.anonymous())

    def test_client_and_admin_see_public(self):
        client = HandbookViewer.client(
            user_id='u', features=frozenset(), schema_name='acme',
        )
        admin = HandbookViewer.admin(user_id='a', features=frozenset())
        assert can_view(_public(), client)
        assert can_view(_public(), admin)


class TestAdminAudience:

    def test_anonymous_and_client_blocked(self):
        target = _admin_doc()
        assert not can_view(target, HandbookViewer.anonymous())
        client = HandbookViewer.client(
            user_id='u', features=frozenset({'admin.tenants.view'}), schema_name='acme',
        )
        assert not can_view(target, client)

    def test_admin_needs_matching_feature(self):
        target = _admin_doc('admin.tenants.view')
        allowed = HandbookViewer.admin(
            user_id='a', features=frozenset({'admin.tenants.view'}),
        )
        denied = HandbookViewer.admin(
            user_id='a', features=frozenset({'admin.users.view'}),
        )
        assert can_view(target, allowed)
        assert not can_view(target, denied)

    def test_superuser_bypasses_admin_feature_key(self):
        target = _admin_doc('admin.tenants.view')
        superuser = HandbookViewer.admin(
            user_id='a', features=frozenset(), is_superuser=True,
        )
        assert can_view(target, superuser)

    def test_admin_doc_without_feature_key_visible_to_all_admins(self):
        target = HandbookAccessTarget(audience=AUDIENCE_ADMIN, feature_key=None)
        admin = HandbookViewer.admin(user_id='a', features=frozenset())
        assert can_view(target, admin)


class TestWmsAudience:

    def test_admin_sees_all_client_pages(self):
        admin = HandbookViewer.admin(user_id='a', features=frozenset())
        assert can_view(_wms('orders.create'), admin)
        assert can_view(HandbookAccessTarget(audience=AUDIENCE_WMS, feature_key=None), admin)

    def test_client_needs_feature_from_session(self):
        target = _wms('orders.create')
        allowed = HandbookViewer.client(
            user_id='u',
            features=frozenset({'orders.create', 'orders.view'}),
            schema_name='acme',
        )
        denied = HandbookViewer.client(
            user_id='u',
            features=frozenset({'orders.view'}),
            schema_name='acme',
        )
        assert can_view(target, allowed)
        assert not can_view(target, denied)

    def test_anonymous_blocked_from_wms(self):
        assert not can_view(_wms(), HandbookViewer.anonymous())

    def test_wms_without_feature_key_visible_to_any_client(self):
        target = HandbookAccessTarget(audience=AUDIENCE_WMS, feature_key=None)
        client = HandbookViewer.client(
            user_id='u', features=frozenset(), schema_name='acme',
        )
        assert can_view(target, client)


class TestDrafts:

    def test_draft_hidden_from_readers(self):
        draft = HandbookAccessTarget(
            audience=AUDIENCE_PUBLIC, status=STATUS_DRAFT,
        )
        assert not can_view(draft, HandbookViewer.anonymous())
        client = HandbookViewer.client(
            user_id='u', features=frozenset(), schema_name='acme',
        )
        admin = HandbookViewer.admin(user_id='a', features=frozenset())
        assert not can_view(draft, client)
        assert not can_view(draft, admin)

    def test_editor_sees_drafts(self):
        draft = HandbookAccessTarget(
            audience=AUDIENCE_WMS,
            feature_key='orders.create',
            status=STATUS_DRAFT,
        )
        editor = HandbookViewer.admin(
            user_id='a',
            features=frozenset({PROPOSE_FEATURE_KEY}),
        )
        assert can_view(draft, editor)
        assert can_manage(editor)
        assert can_propose(editor)
        assert not can_approve(editor)


class TestManage:

    def test_only_platform_staff(self):
        assert not can_manage(HandbookViewer.anonymous())
        client = HandbookViewer.client(
            user_id='u',
            features=frozenset({PROPOSE_FEATURE_KEY, APPROVE_FEATURE_KEY}),
            schema_name='acme',
        )
        assert not can_manage(client)
        assert not can_propose(client)
        assert not can_approve(client)
        admin = HandbookViewer.admin(
            user_id='a', features=frozenset({'admin.tenants.view'}),
        )
        assert not can_manage(admin)

    def test_tech_admin_proposes_but_does_not_approve(self):
        tech = HandbookViewer.admin(
            user_id='a', features=frozenset({PROPOSE_FEATURE_KEY}),
        )
        assert can_propose(tech)
        assert not can_approve(tech)

    def test_platform_administrator_approves(self):
        platform_admin = HandbookViewer.admin(
            user_id='a', features=frozenset({APPROVE_FEATURE_KEY}),
        )
        assert can_approve(platform_admin)
        superuser = HandbookViewer.admin(
            user_id='a', features=frozenset(), is_superuser=True,
        )
        assert can_approve(superuser)
        assert can_propose(superuser)

    def test_superuser_can_manage(self):
        superuser = HandbookViewer.admin(
            user_id='a', features=frozenset(), is_superuser=True,
        )
        assert can_manage(superuser)

    def test_assert_can_manage_anonymous_is_401(self):
        with pytest.raises(AuthException) as exc:
            assert_can_manage(HandbookViewer.anonymous())
        assert exc.value.code == AppErrorCode.AUTH_TOKEN_REQUIRED

    def test_assert_can_manage_client_is_403(self):
        client = HandbookViewer.client(
            user_id='u', features=frozenset(), schema_name='acme',
        )
        with pytest.raises(PermissionException) as exc:
            assert_can_manage(client)
        assert exc.value.code == AppErrorCode.HBK_MANAGE_FORBIDDEN

    def test_assert_can_propose_and_approve(self):
        tech = HandbookViewer.admin(
            user_id='a', features=frozenset({PROPOSE_FEATURE_KEY}),
        )
        assert_can_propose(tech)
        with pytest.raises(PermissionException) as exc:
            assert_can_approve(tech)
        assert exc.value.code == AppErrorCode.HBK_APPROVE_FORBIDDEN


class TestAssertCanView:

    def test_denied_is_not_found(self):
        with pytest.raises(NotFoundException) as exc:
            assert_can_view(_wms(), HandbookViewer.anonymous())
        assert exc.value.code == AppErrorCode.HBK_NOT_FOUND


class TestFilterAndValidation:

    def test_filter_visible_drops_hidden(self):
        items = [
            _public(),
            _wms('orders.create'),
            _admin_doc(),
        ]
        client = HandbookViewer.client(
            user_id='u',
            features=frozenset({'orders.create'}),
            schema_name='acme',
        )
        visible = filter_visible(items, client)
        assert visible == [items[0], items[1]]

    def test_invalid_audience_and_kind(self):
        with pytest.raises(Exception) as exc:
            assert_valid_audience('everyone')
        assert exc.value.code == AppErrorCode.HBK_INVALID_AUDIENCE
        with pytest.raises(Exception) as exc:
            assert_valid_kind('blog')
        assert exc.value.code == AppErrorCode.HBK_INVALID_KIND
        assert_valid_audience(AUDIENCE_WMS)
        assert_valid_kind(KIND_MANUAL)


class TestStorageKeys:

    def test_markdown_and_asset_keys(self):
        assert markdown_object_key('pedidos', 'es', '1.0') == 'handbook/pages/pedidos/es/1.0.md'
        assert asset_object_key('p1', 'img.png') == 'handbook/assets/p1/img.png'
        assert asset_object_key('p1', '../x.png') == 'handbook/assets/p1/x.png'


class TestViewerFromUser:

    def test_anonymous_when_unauthenticated(self):
        user = SimpleNamespace(is_authenticated=False, pk='1')
        assert viewer_from_user(user).kind == 'anonymous'

    def test_admin_uses_loader(self):
        user = SimpleNamespace(
            is_authenticated=True, pk='adm', is_superuser=False, company_id=None,
        )

        class Loader:
            def load_admin_features(self, _user):
                return frozenset({'admin.tenants.view'})

            def load_client_features(self, _user):
                return frozenset()

        viewer = viewer_from_user(
            user, payload={'user_type': 'admin'}, loader=Loader(),
        )
        assert viewer.kind == 'admin'
        assert viewer.has('admin.tenants.view')

    def test_client_uses_loader(self):
        user = SimpleNamespace(
            is_authenticated=True, pk='u1', company_id='co',
        )

        class Loader:
            def load_admin_features(self, _user):
                return frozenset()

            def load_client_features(self, _user):
                return frozenset({'orders.create'})

        viewer = viewer_from_user(
            user,
            payload={'user_type': 'client', 'schema_name': 'public'},
            loader=Loader(),
        )
        assert viewer.kind == 'client'
        assert viewer.has('orders.create')

    def test_resolve_viewer_caches_on_request(self):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False), auth=None)
        first = resolve_viewer(request)
        request.user = SimpleNamespace(is_authenticated=True, pk='x', company_id=None)
        second = resolve_viewer(request)
        assert first is second
        assert first.kind == 'anonymous'
