"""Mueve el markdown del handbook de ``pages/<page-id>/`` a ``pages/<slug>/`` en MinIO."""

from django.core.management.base import BaseCommand

from handbook.core.constants import HANDBOOK_BUCKET, HANDBOOK_OBJECT_PREFIX
from handbook.core.storage import markdown_object_key, page_folder
from handbook.features.docs.content.page.infrastructure.repositories import MinioMarkdownStore
from handbook.features.docs.content.page.models import HandbookLocaleVersion


class Command(BaseCommand):
    help = 'Rename handbook markdown folders in MinIO from the page id to the page slug.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only list the moves; change nothing.')
        parser.add_argument(
            '--purge-orphans',
            action='store_true',
            help='Delete objects under handbook/pages/ that no page version references.',
        )

    def handle(self, *args, dry_run=False, purge_orphans=False, **options):
        blobs = MinioMarkdownStore()
        rows = list(HandbookLocaleVersion.objects.select_related('page').order_by('page__slug', 'locale', 'version'))
        owners = {row.object_key: row.page_id for row in rows}
        moved: list[str] = []
        failed = 0

        for row in rows:
            target = markdown_object_key(row.page.slug, row.locale, row.version)
            if owners.get(target) not in (None, row.page_id):
                target = markdown_object_key(page_folder(row.page.slug, row.page_id), row.locale, row.version)
            if row.object_key == target:
                continue
            self.stdout.write(f'{row.object_key} -> {target}')
            if dry_run:
                continue
            try:
                blobs.put(target, blobs.get(row.object_key))
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.WARNING(f'  skipped: {exc}'))
                continue
            HandbookLocaleVersion.objects.filter(pk=row.pk).update(object_key=target, bucket=HANDBOOK_BUCKET)
            owners.pop(row.object_key, None)
            owners[target] = row.page_id
            moved.append(row.object_key)

        for key in moved:
            if key not in owners:
                blobs.delete(key)

        orphans = [
            item.object_name
            for item in blobs.storage.list_files(HANDBOOK_BUCKET, prefix=f'{HANDBOOK_OBJECT_PREFIX}pages/')
            if item.object_name not in owners
        ]
        for key in orphans:
            self.stdout.write(f'orphan: {key}')
            if purge_orphans and not dry_run:
                blobs.delete(key)

        verb = 'Would move' if dry_run else 'Moved'
        summary = f'{verb} {len(moved) if not dry_run else "the listed"} objects; {failed} failed; {len(orphans)} orphans'
        if purge_orphans and not dry_run:
            summary += ' deleted'
        self.stdout.write(self.style.SUCCESS(summary + '.'))
