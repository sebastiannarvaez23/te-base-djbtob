"""Identity profile update: extra name, document, and phone country rules."""
from unittest import TestCase

import pytest
from pydantic import ValidationError

from client.features.security.identity.identity.domain.schemas import UpdateUserProfileSchema
from client.features.security.identity.identity.presentation.bodies import UpdateUserProfileBody
from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType

pytestmark = pytest.mark.unit


class TestUpdateUserProfileSchema(TestCase):

    def test_strips_grouping_dots_from_document_number(self):
        schema = UpdateUserProfileSchema(document_type='CC', document_number='1.144.205.897')
        self.assertEqual(schema.document_number, '1144205897')
        self.assertEqual(schema.document_type, IdentityDocumentType.CEDULA_CIUDADANIA)

    def test_rejects_letters_on_citizenship_id(self):
        with self.assertRaises(ValidationError):
            UpdateUserProfileSchema(document_type='CC', document_number='AB1234')

    def test_passport_allows_alphanumeric(self):
        schema = UpdateUserProfileSchema(document_type='PA', document_number='ab-123456')
        self.assertEqual(schema.document_number, 'AB-123456')

    def test_colombian_phone_must_be_ten_digits(self):
        with self.assertRaises(ValidationError):
            UpdateUserProfileSchema(phone_country_code='CO', telephone='300123456')

        schema = UpdateUserProfileSchema(phone_country_code='co', telephone='300-123-4567')
        self.assertEqual(schema.telephone, '3001234567')
        self.assertEqual(schema.phone_country_code, 'CO')

    def test_foreign_phone_may_be_shorter_than_ten(self):
        schema = UpdateUserProfileSchema(phone_country_code='US', telephone='5551234')
        self.assertEqual(schema.telephone, '5551234')

    def test_optional_second_name_must_be_at_least_two_when_set(self):
        with self.assertRaises(ValidationError):
            UpdateUserProfileSchema(second_name='A')

        schema = UpdateUserProfileSchema(second_name='Ann')
        self.assertEqual(schema.second_name, 'Ann')

    def test_second_last_name_may_be_cleared(self):
        schema = UpdateUserProfileSchema(second_last_name='')
        self.assertEqual(schema.second_last_name, '')


class TestUpdateUserProfileBody(TestCase):

    def test_strips_document_grouping_and_normalizes_country(self):
        data, err = UpdateUserProfileBody({
            'document_type': 'CC',
            'document_number': '1.144.205.897',
            'phone_country_code': 'co',
            'telephone': '3001234567',
        }).parse()
        self.assertIsNone(err)
        self.assertEqual(data['document_number'], '1144205897')
        self.assertEqual(data['phone_country_code'], 'CO')

    def test_rejects_short_colombian_phone(self):
        data, err = UpdateUserProfileBody({
            'phone_country_code': 'CO',
            'telephone': '300123456',
        }).parse()
        self.assertIsNone(data)
        self.assertIsNotNone(err)

    def test_document_number_max_length_matches_database(self):
        data, err = UpdateUserProfileBody({
            'document_number': 'A' * 21,
        }).parse()
        self.assertIsNone(data)
        self.assertIsNotNone(err)
