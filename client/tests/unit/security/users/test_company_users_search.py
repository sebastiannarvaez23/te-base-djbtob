"""Share-box search: one query term matches name, username, or email."""
import pytest

from client.features.security.identity.users.infrastructure.repositories import (
    colleague_search_filter,
)
from client.features.security.identity.users.presentation.queries import CompanyUsersQuery

pytestmark = pytest.mark.unit


def test_company_users_query_keeps_free_text():
    query_filter = CompanyUsersQuery({
        'q': 'ana@bodega',
        'status': 'active',
        'page': '0',
        'page_size': '50',
    })
    ok, errors = query_filter.validate()
    assert ok, errors
    assert query_filter.to_query().filters['q'] == 'ana@bodega'


def test_colleague_search_covers_name_username_and_email():
    rendered = str(colleague_search_filter('ana'))
    assert 'first_name' in rendered
    assert 'second_name' in rendered
    assert 'last_name' in rendered
    assert 'second_last_name' in rendered
    assert 'username' in rendered
    assert 'email' in rendered
    assert 'ana' in rendered
