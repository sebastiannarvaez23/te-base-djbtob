"""Unit tests for assistant runtime status catalog."""

import pytest

from core.ai.assistant_status import (
    ASSISTANT_STATUS_CALCULATING,
    ASSISTANT_STATUS_COMPOSING,
    ASSISTANT_STATUS_INTERPRETING,
    ASSISTANT_STATUS_SEARCHING_ORDERS,
    ASSISTANT_STATUS_SEARCHING_REFERENCES,
    status_for_tool,
    status_payload,
)


@pytest.mark.unit
class TestAssistantStatusCatalog:

    def test_tool_mapping(self):
        assert status_for_tool('list_orders') == ASSISTANT_STATUS_SEARCHING_ORDERS
        assert status_for_tool('get_order_by_number') == ASSISTANT_STATUS_SEARCHING_ORDERS
        assert status_for_tool('list_references') == ASSISTANT_STATUS_SEARCHING_REFERENCES
        assert status_for_tool('get_reference') == ASSISTANT_STATUS_SEARCHING_REFERENCES
        assert status_for_tool('get_order_indicators') == ASSISTANT_STATUS_CALCULATING
        assert status_for_tool('unknown_tool') == ASSISTANT_STATUS_INTERPRETING

    def test_payload_has_code_and_english_label(self):
        payload = status_payload(ASSISTANT_STATUS_COMPOSING)
        assert payload['code'] == ASSISTANT_STATUS_COMPOSING
        assert 'Writing' in payload['label']

    def test_reviewing_and_still_working_are_registered(self):
        from core.ai.assistant_status import (
            ASSISTANT_STATUS_REVIEWING_RESULTS,
            ASSISTANT_STATUS_STILL_WORKING,
        )
        assert 'Reviewing' in status_payload(ASSISTANT_STATUS_REVIEWING_RESULTS)['label']
        assert 'Still working' in status_payload(ASSISTANT_STATUS_STILL_WORKING)['label']

    def test_unknown_code_falls_back_to_interpreting(self):
        payload = status_payload('not-a-real-code')
        assert payload['code'] == ASSISTANT_STATUS_INTERPRETING
