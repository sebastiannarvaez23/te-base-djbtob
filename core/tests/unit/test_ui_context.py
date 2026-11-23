"""Unit tests de core/ui_context.py."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from types import SimpleNamespace
from unittest import TestCase

from core.ui_context import (
    UiContext,
    get_ui_context,
    parse_ui_context_header,
    reset_ui_context,
    set_ui_context,
    ui_context_dict,
    ui_context_from_request,
)

_MID = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'


class UiContextTests(TestCase):

    def tearDown(self):
        reset_ui_context()

    def test_contextvar_roundtrip(self):
        set_ui_context(UiContext(
            module_id=_MID,
            functionality_id='b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
            page_section='profile',
            feature_key='settings.profile.edit',
        ))
        self.assertEqual(ui_context_dict(), {
            'module_id': _MID,
            'module_code': '',
            'functionality_id': 'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
            'page_section': 'profile',
            'feature_key': 'settings.profile.edit',
        })
        self.assertEqual(get_ui_context().page_section, 'profile')

    def test_parse_header_happy_path(self):
        ctx = parse_ui_context_header(f'fk=orders.view;ps=list;mid={_MID}')
        self.assertEqual(ctx.feature_key, 'orders.view')
        self.assertEqual(ctx.page_section, 'list')
        self.assertEqual(ctx.module_id, _MID)
        self.assertEqual(ctx.functionality_id, '')

    def test_parse_header_ignores_invalid_parts(self):
        ctx = parse_ui_context_header(
            f'fk=BAD KEY;ps=profile;mid=not-a-uuid;hack=1;fk=inventories.references-view;mid={_MID.upper()}'
        )
        self.assertEqual(ctx.feature_key, 'inventories.references-view')
        self.assertEqual(ctx.page_section, 'profile')
        self.assertEqual(ctx.module_id, _MID)

    def test_parse_header_empty_or_garbage(self):
        self.assertEqual(parse_ui_context_header(''), UiContext())
        self.assertEqual(parse_ui_context_header(';;;'), UiContext())
        self.assertEqual(parse_ui_context_header('<script>'), UiContext())

    def test_parse_header_does_not_include_assistant_fields(self):
        ctx = parse_ui_context_header(
            'fk=orders.view;ps=list;module_purpose=despacho;entity_id=abc'
        )
        self.assertEqual(ctx.feature_key, 'orders.view')
        self.assertEqual(ctx.page_section, 'list')
        self.assertEqual(ctx.module_id, '')

    def test_from_request_reads_django_meta(self):
        request = SimpleNamespace(META={'HTTP_X_UI_CONTEXT': f'fk=orders.view;ps=board;mid={_MID}'})
        ctx = ui_context_from_request(request)
        self.assertEqual(ctx.feature_key, 'orders.view')
        self.assertEqual(ctx.page_section, 'board')
        self.assertEqual(ctx.module_id, _MID)

    def test_from_request_missing_header_is_empty(self):
        self.assertEqual(ui_context_from_request(SimpleNamespace(META={})), UiContext())
