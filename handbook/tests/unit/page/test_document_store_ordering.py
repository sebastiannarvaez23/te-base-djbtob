"""Hueco de menú al crear una página y migración de carpetas del markdown (ORM simulado)."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.core.management import call_command

from handbook.features.docs.content.page.infrastructure.repositories import DjangoHandbookDocumentStore

pytestmark = pytest.mark.unit

REPO = 'handbook.features.docs.content.page.infrastructure.repositories'
COMMAND = 'handbook.features.docs.content.page.management.commands.rename_handbook_folders'


def _revision(sort_order, parent_id=None):
    return SimpleNamespace(pk=uuid4(), parent_page_id=parent_id, sort_order=sort_order)


def _page(slug, draft=None, published=None):
    return SimpleNamespace(slug=slug, draft_revision=draft, published_revision=published)


class TestPlaceNewPage:

    def _place(self, pages, requested, parent_id=None):
        with patch(f'{REPO}.HandbookPage') as page_model, \
                patch(f'{REPO}.HandbookRevision') as revision_model, \
                patch(f'{REPO}.advisory_xact_lock') as lock:
            page_model.objects.select_related.return_value.filter.return_value = pages
            index = DjangoHandbookDocumentStore(blobs=MagicMock())._place_new_page(parent_id, requested)
        self.lock = lock
        return index, page_model, revision_model

    @pytest.mark.parametrize('parent_id', [None, uuid4()])
    def test_serializes_creations_under_the_same_parent(self, parent_id):
        self._place([], 0, parent_id)
        self.lock.assert_called_once_with('handbook_menu', parent_id or 'root')

    def test_opens_the_requested_slot_with_one_bulk_update(self):
        alfa, beta, gamma = _revision(0), _revision(1), _revision(2)
        pages = [_page('gamma', gamma), _page('alfa', alfa), _page('beta', beta)]
        index, page_model, revision_model = self._place(pages, 1)
        assert index == 1
        assert (alfa.sort_order, beta.sort_order, gamma.sort_order) == (0, 2, 3)
        page_model.objects.select_related.return_value.filter.assert_called_once()
        updated = list(revision_model.objects.bulk_update.call_args.args[0])
        assert {revision.pk for revision in updated} == {beta.pk, gamma.pk}
        assert revision_model.objects.bulk_update.call_args.args[1] == ['sort_order']

    def test_clamps_the_slot_and_skips_a_noop_write(self):
        alfa = _revision(0)
        index, _page_model, revision_model = self._place([_page('alfa', alfa)], 9)
        assert index == 1
        revision_model.objects.bulk_update.assert_not_called()

    def test_moves_draft_and_published_but_not_a_revision_under_another_parent(self):
        parent = uuid4()
        draft = _revision(0, parent)
        published = _revision(0, uuid4())
        index, _page_model, revision_model = self._place([_page('alfa', draft, published)], 0, parent)
        assert index == 0
        assert (draft.sort_order, published.sort_order) == (1, 0)
        assert list(revision_model.objects.bulk_update.call_args.args[0]) == [draft]


def _version(page_id, slug, key, locale='es', version='1.0'):
    return SimpleNamespace(
        pk=uuid4(), page_id=page_id, page=SimpleNamespace(slug=slug),
        locale=locale, version=version, object_key=key,
    )


def _run(rows, *args, listed=(), put_error=None):
    blobs = MagicMock()
    blobs.get.side_effect = lambda key: f'body:{key}'.encode()
    if put_error is not None:
        blobs.put.side_effect = put_error
    blobs.storage.list_files.return_value = [SimpleNamespace(object_name=key) for key in listed]
    out = StringIO()
    with patch(f'{COMMAND}.MinioMarkdownStore', return_value=blobs), \
            patch(f'{COMMAND}.HandbookLocaleVersion') as model:
        model.objects.select_related.return_value.order_by.return_value = rows
        call_command('rename_handbook_folders', *args, stdout=out, stderr=StringIO())
    return blobs, model, out.getvalue()


class TestRenameHandbookFolders:

    def test_moves_markdown_to_the_slug_folder(self):
        page_id = uuid4()
        old = f'handbook/pages/{page_id}/es/1.0.md'
        blobs, model, out = _run([_version(page_id, 'pedidos', old)])
        blobs.put.assert_called_once_with('handbook/pages/pedidos/es/1.0.md', f'body:{old}'.encode())
        model.objects.filter.return_value.update.assert_called_once_with(
            object_key='handbook/pages/pedidos/es/1.0.md', bucket='base',
        )
        blobs.delete.assert_called_once_with(old)
        assert 'Moved 1 objects; 0 failed; 0 orphans.' in out

    def test_a_folder_owned_by_another_page_falls_back_to_slug_and_id(self):
        owner, renamed = uuid4(), uuid4()
        taken = 'handbook/pages/pedidos/es/1.0.md'
        rows = [
            _version(renamed, 'pedidos', f'handbook/pages/{renamed}/es/1.0.md'),
            _version(owner, 'pedidos-antiguo', taken),
        ]
        blobs, _model, _out = _run(rows)
        short = str(renamed).replace('-', '')[:8]
        targets = [call.args[0] for call in blobs.put.call_args_list]
        assert targets == [
            f'handbook/pages/pedidos--{short}/es/1.0.md',
            'handbook/pages/pedidos-antiguo/es/1.0.md',
        ]

    def test_dry_run_changes_nothing(self):
        page_id = uuid4()
        blobs, model, out = _run(
            [_version(page_id, 'pedidos', f'handbook/pages/{page_id}/es/1.0.md')], '--dry-run',
        )
        blobs.put.assert_not_called()
        blobs.delete.assert_not_called()
        model.objects.filter.assert_not_called()
        assert 'Would move the listed objects' in out

    def test_a_failed_copy_keeps_the_row_on_its_old_key(self):
        page_id = uuid4()
        blobs, model, out = _run(
            [_version(page_id, 'pedidos', f'handbook/pages/{page_id}/es/1.0.md')],
            put_error=RuntimeError('minio down'),
        )
        model.objects.filter.assert_not_called()
        blobs.delete.assert_not_called()
        assert '1 failed' in out

    def test_orphans_are_listed_and_purged_on_request(self):
        page_id = uuid4()
        live = 'handbook/pages/pedidos/es/1.0.md'
        orphan = 'handbook/pages/viejo/es/1.0.md'
        blobs, _model, out = _run(
            [_version(page_id, 'pedidos', live)], '--purge-orphans', listed=[live, orphan],
        )
        blobs.put.assert_not_called()
        blobs.delete.assert_called_once_with(orphan)
        assert f'orphan: {orphan}' in out
        assert '1 orphans deleted.' in out
