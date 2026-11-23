"""Operational directories hide purged (GONE) companies and tombstone users."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from client.features.security.lifecycle.registration.models import User
from core.query.core import PaginatedQuery
from platform.features.company.tenant.company.domain.lifecycle import (
    DIRECTORY_HIDDEN_LIFECYCLES,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CLOSED,
    LIFECYCLE_GONE,
    TOMBSTONE_EMAIL_DOMAIN,
    is_directory_visible,
)
from platform.features.company.tenant.company.infrastructure.repositories import (
    DjangoCompanyRepository,
)
from platform.features.company.tenant.users.infrastructure.repositories import (
    DjangoTenantUserRepository,
)


pytestmark = pytest.mark.unit

COMPANY_REPO = 'platform.features.company.tenant.company.infrastructure.repositories'
USER_REPO = 'platform.features.company.tenant.users.infrastructure.repositories'


def test_directory_hides_gone_keeps_closed():
    assert is_directory_visible(LIFECYCLE_ACTIVE)
    assert is_directory_visible(LIFECYCLE_CLOSED)
    assert not is_directory_visible(LIFECYCLE_GONE)
    assert DIRECTORY_HIDDEN_LIFECYCLES == frozenset({LIFECYCLE_GONE})


@patch(f'{COMPANY_REPO}.Company.objects')
def test_company_list_excludes_gone(objects):
    qs = MagicMock()
    objects.select_related.return_value.exclude.return_value.order_by.return_value = qs
    qs.count.return_value = 0
    qs.__getitem__.return_value = []

    DjangoCompanyRepository().get_paginated(
        PaginatedQuery(page=0, page_size=10, filters={}),
    )

    objects.select_related.return_value.exclude.assert_called_once_with(
        lifecycle__in=DIRECTORY_HIDDEN_LIFECYCLES,
    )


@patch(f'{COMPANY_REPO}.Company.objects')
def test_company_get_all_excludes_gone(objects):
    objects.select_related.return_value.exclude.return_value = []

    DjangoCompanyRepository().get_all()

    objects.select_related.return_value.exclude.assert_called_once_with(
        lifecycle__in=DIRECTORY_HIDDEN_LIFECYCLES,
    )


@patch(f'{USER_REPO}.User.objects')
def test_tenant_user_list_excludes_gone_and_tombstones(objects):
    qs = MagicMock()
    chained = objects.select_related.return_value.exclude.return_value.exclude.return_value
    chained.order_by.return_value = qs
    qs.count.return_value = 0
    qs.__getitem__.return_value = []

    DjangoTenantUserRepository().get_paginated(
        PaginatedQuery(page=0, page_size=10, filters={}),
    )

    first_exclude = objects.select_related.return_value.exclude
    first_exclude.assert_called_once_with(
        company__lifecycle__in=DIRECTORY_HIDDEN_LIFECYCLES,
    )
    first_exclude.return_value.exclude.assert_called_once_with(
        email__iendswith=f'@{TOMBSTONE_EMAIL_DOMAIN}',
    )


@patch(f'{USER_REPO}.User.objects')
def test_toggle_active_ignores_tombstone_users(objects):
    objects.select_related.return_value.exclude.return_value.exclude.return_value.get.side_effect = (
        User.DoesNotExist
    )

    result = DjangoTenantUserRepository().toggle_active(uuid4())
    assert result is None
