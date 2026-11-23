"""Unit tests for ReorderSectionsUseCase / ReorderModulesUseCase."""
import uuid
from unittest import TestCase

from platform.features.security.access.modules.application.use_cases import ReorderModulesUseCase
from platform.features.security.access.sections.application.use_cases import ReorderSectionsUseCase


class _FakeSectionRepo:
    def __init__(self):
        self.ids = None

    def reorder(self, ids):
        self.ids = ids
        return len(ids)


class _FakeModuleRepo:
    def __init__(self):
        self.ids = None

    def reorder(self, ids):
        self.ids = ids
        return len(ids)


class ReorderUseCaseTests(TestCase):

    def test_reorder_sections_passes_ids(self):
        repo = _FakeSectionRepo()
        ids = [uuid.uuid4(), uuid.uuid4()]
        count = ReorderSectionsUseCase(repo).execute(ids)
        self.assertEqual(count, 2)
        self.assertEqual(repo.ids, ids)

    def test_reorder_modules_passes_ids(self):
        repo = _FakeModuleRepo()
        ids = [uuid.uuid4()]
        count = ReorderModulesUseCase(repo).execute(ids)
        self.assertEqual(count, 1)
        self.assertEqual(repo.ids, ids)
