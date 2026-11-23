"""Unit tests para el módulo transversal core/ai (FASE 0).

Fijan el contrato de los cimientos de IA:
- El puerto IChatModel funciona con un adaptador fake (sin red ni API key).
- El factory selecciona el proveedor por settings y default seguro 'fake'.
- La degradación (complete_or) nunca relanza: devuelve una Completion degradada.
- La redacción enmascara secretos antes de que el prompt salga.
- Los códigos de error AI_* están registrados.
"""

import pytest
from django.test import override_settings

from core.ai import get_chat_model, get_embedder
from core.ai.config import is_ai_enabled
from core.ai.domain.schemas import (
    Completion,
    FinishReason,
    Message,
    Prompt,
    TokenUsage,
)
from core.ai.infrastructure.fake_provider import FakeChatModel, FakeEmbedder
from core.ai.resilience import complete_or
from core.ai.safety import redact_prompt
from core.errors import AppErrorCode
from core.errors.codes import ERROR_REGISTRY


@pytest.mark.unit
class TestFakeChatModel:

    def test_echoes_last_user_message(self):
        model = FakeChatModel()
        prompt = Prompt(messages=[Message.user('Resume el día')])
        completion = model.complete(prompt)
        assert 'Resume el día' in completion.text
        assert completion.provider == 'fake'
        assert completion.finish_reason == FinishReason.STOP
        assert not completion.degraded

    def test_agent_protocol_returns_json_not_raw_echo(self):
        model = FakeChatModel()
        prompt = Prompt(
            system='Available tools\n{"action":"final","text":"..."}',
            messages=[Message.user('Que tal estan las bodegas?')],
        )
        completion = model.complete(prompt)
        assert '"action"' in completion.text
        assert '[fake:' not in completion.text
        assert (
            'list_orders' in completion.text
            or 'list_warehouses' in completion.text
            or 'final' in completion.text
        )

    def test_reports_token_usage_and_latency(self):
        model = FakeChatModel()
        completion = model.complete(Prompt(messages=[Message.user('hola')]))
        assert completion.usage.input_tokens >= 1
        assert completion.usage.output_tokens >= 1
        assert completion.latency_ms >= 0

    def test_canned_response_overrides_echo(self):
        model = FakeChatModel(canned_response='RESPUESTA FIJA')
        completion = model.complete(Prompt(messages=[Message.user('x')]))
        assert completion.text == 'RESPUESTA FIJA'

    def test_stream_yields_text(self):
        model = FakeChatModel(canned_response='abc')
        chunks = list(model.stream(Prompt(messages=[Message.user('x')])))
        assert ''.join(chunks) == 'abc'


@pytest.mark.unit
class TestFakeEmbedder:

    def test_embed_is_deterministic(self):
        embedder = FakeEmbedder(dim=8)
        a = embedder.embed('mismo texto')
        b = embedder.embed('mismo texto')
        assert a.vector == b.vector
        assert len(a.vector) == 8

    def test_embed_batch(self):
        embedder = FakeEmbedder()
        results = embedder.embed_batch(['a', 'b', 'c'])
        assert len(results) == 3


@pytest.mark.unit
class TestConfigFactory:

    @override_settings(AI_PROVIDER='fake', AI_ENABLED=True)
    def test_default_provider_is_fake(self):
        assert isinstance(get_chat_model(), FakeChatModel)

    def test_explicit_fake_override(self):
        assert isinstance(get_chat_model('fake'), FakeChatModel)

    def test_unknown_provider_falls_back_to_fake(self):
        assert isinstance(get_chat_model('does-not-exist'), FakeChatModel)

    def test_embedder_default_is_fake(self):
        assert isinstance(get_embedder(), FakeEmbedder)

    def test_ai_enabled_flag(self):
        assert is_ai_enabled() in (True, False)

    def test_explicit_local_override(self, settings):
        settings.AI_ENABLED = True
        from core.ai.infrastructure.local_provider import LocalChatModel
        assert isinstance(get_chat_model('local'), LocalChatModel)


@pytest.mark.unit
class TestResilienceFallback:

    def test_complete_or_returns_completion_on_success(self):
        model = FakeChatModel(canned_response='ok')
        completion = complete_or(model, Prompt(messages=[Message.user('x')]),
                                 fallback='no disponible', feature='test')
        assert completion.text == 'ok'
        assert not completion.degraded

    def test_complete_or_degrades_on_failure(self):
        class BoomModel:
            provider_name = 'boom'
            model_name = 'boom-1'

            def complete(self, prompt):
                raise RuntimeError('proveedor caído')

        completion = complete_or(BoomModel(), Prompt(messages=[Message.user('x')]),
                                 fallback='resumen no disponible', feature='test')
        assert completion.degraded
        assert completion.text == 'resumen no disponible'
        assert completion.finish_reason == FinishReason.ERROR


@pytest.mark.unit
class TestSafetyRedaction:

    def test_redacts_secrets_in_json_content(self):
        prompt = Prompt(messages=[
            Message.user('{"user": "ana", "password": "s3cr3t", "token": "abc"}'),
        ])
        redacted = redact_prompt(prompt)
        body = redacted.messages[0].content
        assert 's3cr3t' not in body
        assert 'abc' not in body
        assert 'ana' in body

    def test_does_not_mutate_original_prompt(self):
        prompt = Prompt(messages=[Message.user('{"password": "s3cr3t"}')])
        redact_prompt(prompt)
        assert 's3cr3t' in prompt.messages[0].content

    def test_plain_text_passes_through(self):
        prompt = Prompt(messages=[Message.user('texto plano sin json')])
        redacted = redact_prompt(prompt)
        assert redacted.messages[0].content == 'texto plano sin json'

    def test_redacts_secrets_in_system_prompt(self):
        prompt = Prompt(
            system='{"password": "s3cr3t"}',
            messages=[Message.user('hola')],
        )
        redacted = redact_prompt(prompt)
        assert 's3cr3t' not in (redacted.system or '')
        assert 's3cr3t' in (prompt.system or '')


@pytest.mark.unit
class TestErrorCodes:

    @pytest.mark.parametrize('code', [
        AppErrorCode.AI_PROVIDER_UNAVAILABLE,
        AppErrorCode.AI_TIMEOUT,
        AppErrorCode.AI_QUOTA_EXCEEDED,
        AppErrorCode.AI_INVALID_RESPONSE,
        AppErrorCode.AI_PROVIDER_ERROR,
        AppErrorCode.AI_DISABLED,
        AppErrorCode.AI_CONVERSATION_NOT_FOUND,
        AppErrorCode.AI_UNKNOWN_TOOL,
        AppErrorCode.AI_BUSY,
        AppErrorCode.AI_OR_DISABLED,
        AppErrorCode.AI_ML_DISABLED,
    ])
    def test_ai_codes_are_registered(self, code):
        entry = ERROR_REGISTRY[code]
        assert 'http_status' in entry
        assert 'message' in entry
        assert 'detail' in entry


@pytest.mark.unit
class TestSchemas:

    def test_token_usage_total(self):
        usage = TokenUsage(input_tokens=10, output_tokens=5)
        assert usage.total_tokens == 15

    def test_message_factories(self):
        assert Message.user('a').role.value == 'user'
        assert Message.system('b').role.value == 'system'
        assert Message.assistant('c').role.value == 'assistant'

    def test_completion_defaults(self):
        c = Completion(text='hola')
        assert c.finish_reason == FinishReason.STOP
        assert c.usage.total_tokens == 0
        assert not c.degraded
