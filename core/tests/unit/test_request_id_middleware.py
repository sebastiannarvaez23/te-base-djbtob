"""Unit tests for RequestIDMiddleware uniqueness."""
from unittest import TestCase
from unittest.mock import MagicMock

import pytest
from django.http import HttpResponse

from core.middleware import RequestIDMiddleware

pytestmark = pytest.mark.unit


class RequestIDMiddlewareTests(TestCase):

    def test_always_generates_uuid7_ignoring_client_header(self):
        seen = []

        def get_response(request):
            seen.append(request.request_id)
            return HttpResponse('ok')

        mw = RequestIDMiddleware(get_response)
        req = MagicMock()
        req.META = {'HTTP_X_REQUEST_ID': 'client-fixed-id'}

        resp1 = mw(req)
        resp2 = mw(req)

        self.assertEqual(len(seen), 2)
        self.assertNotEqual(seen[0], seen[1])
        self.assertNotEqual(seen[0], 'client-fixed-id')
        self.assertEqual(resp1['X-Request-ID'], seen[0])
        self.assertEqual(resp2['X-Client-Request-ID'], 'client-fixed-id')
        self.assertTrue(seen[0].startswith('01') or len(seen[0]) >= 32)
