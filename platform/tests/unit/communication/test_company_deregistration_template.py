"""Unit tests for COMPANY_DEREGISTRATION template construction."""
from unittest import TestCase

import pytest
from django.template import Context, Template

pytestmark = pytest.mark.unit

from platform.features.communication.email.email_template.application.company_deregistration_template import (
    HTML_TEMPLATE,
)
from platform.features.communication.email.email_template.application.template_source import (
    normalize_django_template_source,
)


class TestNormalizeDjangoTemplateSource(TestCase):
    def test_collapses_variable_split_across_newlines(self):
        source = 'Hola <strong>{{ user_name\n                                    }}</strong>,'
        self.assertEqual(
            normalize_django_template_source(source),
            'Hola <strong>{{ user_name }}</strong>,',
        )

    def test_leaves_css_braces_untouched(self):
        source = '<td style="color:#313131;">{{ company_name }}</td>'
        self.assertEqual(normalize_django_template_source(source), source)

    def test_empty_source(self):
        self.assertEqual(normalize_django_template_source(''), '')


class TestCompanyDeregistrationHtml(TestCase):
    def test_is_email_client_safe(self):
        self.assertNotIn('<svg', HTML_TEMPLATE.lower())
        self.assertIn('bgcolor="#313131"', HTML_TEMPLATE)
        self.assertIn('&#127970;', HTML_TEMPLATE)
        self.assertIn('{{ user_name }}', HTML_TEMPLATE)
        self.assertNotRegex(HTML_TEMPLATE, r'\{\{\s+\n')

    def test_renders_all_context_keys(self):
        html = Template(HTML_TEMPLATE).render(Context({
            'user_name': 'Carlos Rodríguez',
            'company_name': 'Prueba Registro Empresa',
            'company_document': '900.123.456-7',
            'deactivation_date': '15 de septiembre de 2026, 10:42 a. m.',
            'deactivation_reason': 'Solicitud del administrador',
            'support_email': 'soporte@base.local',
            'current_year': 2026,
        }))
        self.assertIn('Hola <strong>Carlos Rodríguez</strong>', html)
        self.assertIn('Prueba Registro Empresa', html)
        self.assertIn('900.123.456-7', html)
        self.assertIn('soporte@base.local', html)
        self.assertNotIn('{{', html)
