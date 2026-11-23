"""Unit tests for the state-projection helpers in
``client.features.security.lifecycle.onboarding.application.use_cases._common``.

Two tightly-coupled helpers under test:

  * ``_safe_subset(payload, allowed_keys)`` — filters a dict to a subset
    of allowed keys. Used to scrub sensitive fields before they leave
    the use-case layer.
  * ``build_state_schema(reg)`` — projects a CompanyRegistration ORM
    instance into ``OnboardingStateSchema``, using ``_safe_subset`` to
    strip ``password_hash`` (admin_user_data) and ``processor_token``
    (payment_data).

These exist so the API never returns hashed credentials or single-use
processor tokens to the client. Test failures here are user-visible
security regressions — guard them aggressively.
"""
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

import django
from django.conf import settings as dj_settings
import pytest

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from client.features.security.lifecycle.onboarding.application.use_cases._common import (
    _ADMIN_USER_PUBLIC_KEYS,
    _PAYMENT_PUBLIC_KEYS,
    _safe_subset,
    build_state_schema,
)
from client.features.security.lifecycle.onboarding.domain.enums import (
    OnboardingStatus,
    OnboardingStep,
)

pytestmark = pytest.mark.unit


def _orm_stub(**overrides):
    """Build an object that quacks like a CompanyRegistration row.

    Defaults reflect a fresh registration that has finished step
    ``admin_user`` but has not yet selected a subscription. Tests
    override the slice they care about.
    """
    base = dict(
        id=uuid4(),
        status=OnboardingStatus.IN_PROGRESS.value,
        email='founder@example.com',
        nit='',
        schema_name='',
        company_data_completed=True,
        admin_user_completed=True,
        subscription_selected=False,
        payment_completed=False,
        requires_payment=False,
        subscription_id=None,
        company_data={
            'name': 'Acme', 'nit': '900123', 'address': '...',
            'country': 'CO', 'state': '...', 'city': '...',
        },
        subscription_data={},
        admin_user_data={
            'email': 'owner@example.com',
            'username': 'owner1',
            'telephone': '3001234567',
            'phone_country_code': 'CO',
            'first_name': 'Jane',
            'second_name': 'Ann',
            'last_name': 'Doe',
            'second_last_name': 'Smith',
            'document_type': 'CC',
            'document_number': '1234567890',
            'password_hash': '$argon2id$v=19$m=65536,t=3,p=4$...',
        },
        payment_data={},
        expires_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
    )
    base.update(overrides)
    reg = MagicMock()
    for k, v in base.items():
        setattr(reg, k, v)
    return reg


class TestSafeSubset(TestCase):

    def test_returns_only_allowed_keys(self):
        out = _safe_subset(
            {'a': 1, 'b': 2, 'secret': 'pwd'},
            allowed=('a', 'b'),
        )
        self.assertEqual(out, {'a': 1, 'b': 2})

    def test_missing_keys_are_skipped(self):
        """The contract is "subset of present keys", not "fill missing
        keys with None" — callers shouldn't conflate "key absent" with
        "key was None"."""
        out = _safe_subset({'a': 1}, allowed=('a', 'b'))
        self.assertEqual(out, {'a': 1})

    def test_none_input_returns_empty_dict(self):
        """JSONField defaults to None on missing values; the schema
        defaults to ``{}``, so we need a deterministic empty fallback."""
        self.assertEqual(_safe_subset(None, allowed=('a', 'b')), {})

    def test_empty_input_returns_empty_dict(self):
        self.assertEqual(_safe_subset({}, allowed=('a', 'b')), {})

    def test_extra_keys_are_dropped_silently(self):
        out = _safe_subset({'a': 1, 'leak': 'x'}, allowed=('a',))
        self.assertNotIn('leak', out)

    def test_does_not_mutate_input(self):
        original = {'a': 1, 'b': 2, 'extra': 3}
        _safe_subset(original, allowed=('a',))
        self.assertEqual(original, {'a': 1, 'b': 2, 'extra': 3})


class TestPublicKeyAllowlists(TestCase):
    """Allowlists are the security boundary — assert their exact shape
    so a refactor that quietly adds ``password_hash`` (or any other
    sensitive field) to one of them gets caught."""

    def test_admin_user_allowlist_excludes_password_hash(self):
        self.assertNotIn('password_hash', _ADMIN_USER_PUBLIC_KEYS)
        self.assertNotIn('password', _ADMIN_USER_PUBLIC_KEYS)

    def test_admin_user_allowlist_includes_only_safe_keys(self):
        self.assertEqual(
            set(_ADMIN_USER_PUBLIC_KEYS),
            {
                'email',
                'username',
                'telephone',
                'phone_country_code',
                'first_name',
                'second_name',
                'last_name',
                'second_last_name',
                'document_type',
                'document_number',
                'birth_date',
            },
        )

    def test_payment_allowlist_excludes_processor_token(self):
        self.assertNotIn('processor_token', _PAYMENT_PUBLIC_KEYS)

    def test_payment_allowlist_includes_only_safe_keys(self):
        self.assertEqual(
            set(_PAYMENT_PUBLIC_KEYS),
            {'holder', 'last4', 'expiry_month', 'expiry_year'},
        )


# StepResolver imports models at first call; patch it to avoid pulling
# the ORM into these unit tests.
_RESOLVER_PATCH = (
    'client.features.security.lifecycle.onboarding.application.use_cases._common.StepResolver.resolve'
)


class TestBuildStateSchemaProjection(TestCase):

    def test_strips_password_hash_from_admin_user_data(self):
        reg = _orm_stub()

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.SUBSCRIPTION):
            state = build_state_schema(reg)

        self.assertNotIn('password_hash', state.admin_user_data)
        self.assertEqual(state.admin_user_data['username'], 'owner1')
        self.assertEqual(state.admin_user_data['email'], 'owner@example.com')

    def test_strips_processor_token_from_payment_data(self):
        reg = _orm_stub(
            payment_completed=True,
            payment_data={
                'processor_token': 'tok_secret_should_never_leak',
                'holder': 'Jane Doe',
                'last4': '4242',
                'expiry_month': 12,
                'expiry_year': 2030,
            },
        )

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.CONFIRMATION):
            state = build_state_schema(reg)

        self.assertNotIn('processor_token', state.payment_data)
        self.assertEqual(state.payment_data['last4'], '4242')

    def test_empty_payment_data_projects_to_empty_dict(self):
        """Free plan: payment_data is ``{}`` in DB. The projection must
        keep it as ``{}`` (not ``{'holder': None, 'last4': None, ...}``)
        so the frontend's truthy-check correctly hides the panel."""
        reg = _orm_stub(payment_data={})

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.SUBSCRIPTION):
            state = build_state_schema(reg)

        self.assertEqual(state.payment_data, {})

    def test_none_payment_data_projects_to_empty_dict(self):
        """Defensive: some legacy rows may have NULL payment_data even
        though the model defaults to ``{}``. We must still project to
        ``{}`` and not raise."""
        reg = _orm_stub(payment_data=None)

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.SUBSCRIPTION):
            state = build_state_schema(reg)

        self.assertEqual(state.payment_data, {})

    def test_company_and_subscription_data_pass_through(self):
        """These two are not subject to the public/private split — they
        are plain copies (no sensitive fields are stored under either)."""
        reg = _orm_stub(
            subscription_selected=True,
            subscription_id=uuid4(),
            requires_payment=True,
            subscription_data={
                'subscription_id': '00000000-0000-0000-0000-000000000001',
                'name': 'Pro',
                'price': 49.0,
            },
        )

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.PAYMENT):
            state = build_state_schema(reg)

        self.assertEqual(state.subscription_data['name'], 'Pro')
        self.assertEqual(state.subscription_data['price'], 49.0)
        self.assertEqual(state.company_data['nit'], '900123')

    def test_completion_flags_are_carried_verbatim(self):
        """Frontend gates hydration on these flags (avoiding the
        truthy-empty-dict trap), so the projection must echo them
        unchanged from the ORM row."""
        reg = _orm_stub(
            company_data_completed=True,
            admin_user_completed=True,
            subscription_selected=True,
            payment_completed=False,
            requires_payment=True,
        )

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.PAYMENT):
            state = build_state_schema(reg)

        self.assertTrue(state.company_data_completed)
        self.assertTrue(state.admin_user_completed)
        self.assertTrue(state.subscription_selected)
        self.assertFalse(state.payment_completed)
        self.assertTrue(state.requires_payment)

    def test_admin_user_password_set_true_when_hash_stored(self):
        """The flag is the public signal for "hash on file" — frontend
        relaxes the password requirement when this is True."""
        reg = _orm_stub()  # default stub has password_hash set

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.SUBSCRIPTION):
            state = build_state_schema(reg)

        self.assertTrue(state.admin_user_password_set)

    def test_admin_user_password_set_false_when_step_not_submitted(self):
        """No admin step yet → the flag is False so the frontend keeps
        password as required."""
        reg = _orm_stub(admin_user_completed=False, admin_user_data={})

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.ADMIN_USER):
            state = build_state_schema(reg)

        self.assertFalse(state.admin_user_password_set)

    def test_admin_user_password_set_false_when_data_is_none(self):
        """Defensive: legacy rows may store NULL instead of {}."""
        reg = _orm_stub(admin_user_data=None)

        with patch(_RESOLVER_PATCH, return_value=OnboardingStep.ADMIN_USER):
            state = build_state_schema(reg)

        self.assertFalse(state.admin_user_password_set)
