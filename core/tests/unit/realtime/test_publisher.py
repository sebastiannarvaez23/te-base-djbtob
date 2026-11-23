"""Tests del publisher de tiempo real (sin Channels real)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.realtime.envelope import RealtimeMessage
from core.realtime.publisher import (
    ChannelsRealtimePublisher,
    NullRealtimePublisher,
)

pytestmark = pytest.mark.unit


def _layer_with_async_group_send():
    layer = MagicMock()
    layer.group_send = AsyncMock()
    return layer


def test_to_user_sends_to_namespaced_user_group():
    layer = _layer_with_async_group_send()
    with patch('channels.layers.get_channel_layer', return_value=layer):
        ChannelsRealtimePublisher().to_user(
            'acme', 'user-1', RealtimeMessage(type='notification.new', payload={'a': 1}),
        )

    layer.group_send.assert_awaited_once()
    group, event = layer.group_send.call_args[0]
    assert group == 'rt.acme.user.user-1'
    assert event['type'] == 'realtime.message'
    assert event['payload']['type'] == 'notification.new'
    assert event['payload']['payload'] == {'a': 1}


def test_publish_is_noop_when_layer_not_configured():
    with patch('channels.layers.get_channel_layer', return_value=None):
        # No debe lanzar: emitir en vivo es best-effort.
        ChannelsRealtimePublisher().to_group('any', RealtimeMessage(type='x'))


def test_publish_swallows_layer_errors():
    layer = MagicMock()
    layer.group_send = AsyncMock(side_effect=RuntimeError('redis down'))
    with patch('channels.layers.get_channel_layer', return_value=layer):
        # El error se loguea pero no se propaga.
        ChannelsRealtimePublisher().to_group('g', RealtimeMessage(type='x'))


def test_null_publisher_does_nothing():
    pub = NullRealtimePublisher()
    assert pub.to_user('s', 'u', RealtimeMessage(type='x')) is None
    assert pub.to_group('g', RealtimeMessage(type='x')) is None
