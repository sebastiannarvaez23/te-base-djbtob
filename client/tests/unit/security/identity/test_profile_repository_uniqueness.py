"""Identity profile repository maps document uniqueness IntegrityError."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.db import IntegrityError

from client.features.security.identity.identity.domain.schemas import UpdateUserProfileSchema
from client.features.security.identity.identity.infrastructure.repositories import (
    DjangoUserProfileRepository,
)
from core.errors import AppErrorCode, ConflictException

pytestmark = pytest.mark.unit


@patch('client.features.security.identity.identity.infrastructure.repositories.transaction.atomic')
@patch.object(DjangoUserProfileRepository, '_load')
@patch.object(DjangoUserProfileRepository, '_to_profile')
def test_update_maps_document_unique_integrity_error(_to_profile, _load, atomic):
    atomic.return_value.__enter__.return_value = None
    atomic.return_value.__exit__.return_value = False
    user = MagicMock()
    user.id = uuid4()
    user.save.side_effect = IntegrityError(
        'duplicate key value violates unique constraint "uniq_user_company_document"'
    )
    _load.return_value = user
    repo = DjangoUserProfileRepository(storage=MagicMock())

    with pytest.raises(ConflictException) as exc:
        repo.update(user.id, UpdateUserProfileSchema(document_number='1144205897'))

    assert exc.value.code == AppErrorCode.USER_DUPLICATE_DOCUMENT
