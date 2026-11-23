"""Company registration in Neurana must not block the company save."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform.features.company.tenant.company.application.neurana_customer import (
    register_company_customer,
)


@pytest.mark.unit
def test_company_with_nit_registers_and_http_failure_does_not_raise():
    company_id = uuid4()
    company = SimpleNamespace(id=company_id, nit='900123456', name='Acme', address='Calle 1')
    calls = []

    class _Down:
        def register_customer(self, payload):
            calls.append(payload)
            raise RuntimeError('neurana down')

    register_company_customer(
        company_id,
        loader=lambda _id: company,
        client_factory=_Down,
    )
    assert len(calls) == 1
    assert calls[0].tax_id == '900123456'
    assert calls[0].external_id == str(company_id)
    assert calls[0].tax_regime == ''
    assert calls[0].fiscal_responsibilities == []


@pytest.mark.unit
def test_company_without_nit_does_not_call_neurana():
    company = SimpleNamespace(id=uuid4(), nit='', name='Acme', address='')

    class _Client:
        def register_customer(self, payload):
            raise AssertionError('should not register')

    register_company_customer(
        company.id,
        loader=lambda _id: company,
        client_factory=_Client,
    )
