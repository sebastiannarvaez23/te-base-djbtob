"""Unit tests del adaptador local (Fase 0b) — HTTP mock, sin runtime real."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from core.ai import get_chat_model
from core.ai.domain.schemas import FinishReason, Message, Prompt
from core.ai.infrastructure.genai.local_provider import LocalChatModel
from core.errors import AppErrorCode, ServerException


def _openai_response(text: str = 'hola desde slm', prompt_tokens: int = 3, completion_tokens: int = 4) -> bytes:
    body = {
        'choices': [
            {
                'message': {'role': 'assistant', 'content': text},
                'finish_reason': 'stop',
            }
        ],
        'usage': {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
        },
    }
    return json.dumps(body).encode('utf-8')


def _mock_urlopen(payload: bytes, status: int = 200):
    resp = MagicMock()
    resp.read.return_value = payload
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    if status != 200:
        import urllib.error
        raise urllib.error.HTTPError(
            url='http://127.0.0.1:11434/v1/chat/completions',
            code=status,
            msg='error',
            hdrs=None,
            fp=io.BytesIO(payload),
        )
    return resp


@pytest.mark.unit
class TestLocalChatModel:

    @override_settings(
        AI_ENABLED=True,
        AI_CHAT_MODEL='qwen2.5:1.5b',
        AI_RUNTIME_URL='http://127.0.0.1:11434',
        AI_MAX_TOKENS=256,
        AI_TIMEOUT_SECONDS=5,
        AI_MAX_CONCURRENT=2,
        AI_REDACT_PROMPTS=False,
        AI_CACHE_ENABLED=False,
    )
    def test_complete_parses_openai_compatible_response(self):
        model = LocalChatModel()
        with patch(
            'core.ai.infrastructure.genai.local_provider.urllib.request.urlopen',
            return_value=_mock_urlopen(_openai_response('respuesta local')),
        ) as urlopen:
            completion = model.complete(Prompt(messages=[Message.user('ping')]))

        assert completion.text == 'respuesta local'
        assert completion.provider == 'local'
        assert completion.model == 'qwen2.5:1.5b'
        assert completion.finish_reason == FinishReason.STOP
        assert completion.usage.input_tokens == 3
        assert completion.usage.output_tokens == 4
        assert urlopen.called
        req = urlopen.call_args[0][0]
        assert req.full_url.endswith('/v1/chat/completions')
        body = json.loads(req.data.decode('utf-8'))
        assert body['model'] == 'qwen2.5:1.5b'
        assert body['stream'] is False
        assert body['messages'][-1]['content'] == 'ping'

    @override_settings(
        AI_ENABLED=True,
        AI_CHAT_MODEL='claude-opus-4-8',
        AI_RUNTIME_URL='http://127.0.0.1:11434',
        AI_REDACT_PROMPTS=False,
        AI_CACHE_ENABLED=False,
    )
    def test_ignores_cloud_model_id_and_uses_slm_default(self):
        model = LocalChatModel()
        assert model.model_name == 'qwen2.5:1.5b'

    @override_settings(
        AI_ENABLED=True,
        AI_RUNTIME_URL='http://127.0.0.1:11434',
        AI_REDACT_PROMPTS=False,
        AI_CACHE_ENABLED=False,
    )
    def test_unreachable_runtime_maps_to_ai_001(self):
        import urllib.error

        model = LocalChatModel(model='qwen2.5:1.5b')
        with patch(
            'core.ai.infrastructure.genai.local_provider.urllib.request.urlopen',
            side_effect=urllib.error.URLError('connection refused'),
        ):
            with pytest.raises(ServerException) as exc_info:
                model.complete(Prompt(messages=[Message.user('x')]))
        assert exc_info.value.code == AppErrorCode.AI_PROVIDER_UNAVAILABLE

    @override_settings(
        AI_ENABLED=True,
        AI_RUNTIME_URL='http://127.0.0.1:11434',
        AI_REDACT_PROMPTS=False,
        AI_CACHE_ENABLED=False,
    )
    def test_empty_message_maps_to_ai_004(self):
        model = LocalChatModel(model='qwen2.5:1.5b')
        empty = json.dumps({
            'choices': [{'message': {'content': ''}, 'finish_reason': 'stop'}],
            'usage': {},
        }).encode()
        with patch(
            'core.ai.infrastructure.genai.local_provider.urllib.request.urlopen',
            return_value=_mock_urlopen(empty),
        ):
            with pytest.raises(ServerException) as exc_info:
                model.complete(Prompt(messages=[Message.user('x')]))
        assert exc_info.value.code == AppErrorCode.AI_INVALID_RESPONSE

    @override_settings(
        AI_ENABLED=True,
        AI_RUNTIME_URL='http://127.0.0.1:11434',
        AI_REDACT_PROMPTS=False,
        AI_CACHE_ENABLED=False,
        AI_MAX_CONCURRENT=1,
    )
    def test_stream_yields_delta_chunks(self):
        lines = [
            b'data: {"choices":[{"delta":{"content":"ho"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"la"}}]}\n',
            b'data: [DONE]\n',
        ]
        resp = MagicMock()
        resp.__enter__.return_value = iter(lines)
        resp.__exit__.return_value = False

        model = LocalChatModel(model='qwen2.5:1.5b')
        with patch(
            'core.ai.infrastructure.genai.local_provider.urllib.request.urlopen',
            return_value=resp,
        ):
            chunks = list(model.stream(Prompt(messages=[Message.user('x')])))
        assert ''.join(chunks) == 'hola'


@pytest.mark.unit
class TestLocalFactoryGates:

    @override_settings(AI_ENABLED=True, AI_PROVIDER='local')
    def test_factory_returns_local(self):
        assert isinstance(get_chat_model(), LocalChatModel)

    @override_settings(AI_ENABLED=False, AI_PROVIDER='local')
    def test_factory_blocks_local_when_ai_disabled(self):
        with pytest.raises(ServerException) as exc_info:
            get_chat_model()
        assert exc_info.value.code == AppErrorCode.AI_DISABLED

    @override_settings(AI_ENABLED=False, AI_PROVIDER='fake')
    def test_fake_still_works_when_ai_disabled(self):
        # fake no consume runtime; útil en tests con flag off
        model = get_chat_model()
        assert model.complete(Prompt(messages=[Message.user('ok')])).text
