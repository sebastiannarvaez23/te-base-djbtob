"""
Adaptador IChatModel → API OpenAI (ChatGPT) vía HTTP OpenAI-compatible.

Configuración:
    AI_PROVIDER='openai'
    AI_API_KEY / OPENAI_API_KEY
    AI_CHAT_MODEL (default gpt-4o-mini)
    AI_OPENAI_BASE_URL (default https://api.openai.com)
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Tuple
from urllib.parse import urljoin

from django.conf import settings

from core.errors import AppErrorCode, ServerException

from ...domain.genai.schemas import FinishReason, MessageRole, Prompt, TokenUsage
from .base import BaseChatModel

logger = logging.getLogger('app.ai')

_DEFAULT_MODEL = 'gpt-4o-mini'
_FINISH_MAP = {
    'stop': FinishReason.STOP,
    'length': FinishReason.LENGTH,
    'content_filter': FinishReason.STOP,
}


class OpenAIChatModel(BaseChatModel):
    """Chat over OpenAI (or compatible) HTTP API."""

    provider_name = 'openai'

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
    ):
        configured = (model or getattr(settings, 'AI_CHAT_MODEL', '') or '').strip()
        if not configured or configured.startswith(('qwen', 'llama', 'phi', 'claude')):
            configured = _DEFAULT_MODEL
        self.model_name = configured
        self._api_key = (
            api_key
            or getattr(settings, 'AI_API_KEY', '')
            or getattr(settings, 'OPENAI_API_KEY', '')
            or ''
        )
        if not self._api_key:
            raise ServerException(
                AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                override_detail='AI_API_KEY (or OPENAI_API_KEY) is not configured for OpenAI.',
            )
        self._base_url = (
            (base_url or getattr(settings, 'AI_OPENAI_BASE_URL', 'https://api.openai.com'))
            .rstrip('/')
            + '/'
        )
        self._max_tokens = int(max_tokens or getattr(settings, 'AI_MAX_TOKENS', 1024) or 1024)
        self._timeout = float(timeout_s or getattr(settings, 'AI_TIMEOUT_SECONDS', 60.0) or 60.0)

    def _chat_url(self) -> str:
        return urljoin(self._base_url, 'v1/chat/completions')

    def _to_api_messages(self, prompt: Prompt) -> list[dict]:
        messages: list[dict] = []
        if prompt.system:
            messages.append({'role': 'system', 'content': prompt.system})
        for m in prompt.messages:
            if m.role == MessageRole.SYSTEM:
                if not prompt.system:
                    messages.append({'role': 'system', 'content': m.content})
                continue
            messages.append({'role': m.role.value, 'content': m.content})
        return messages

    def _post_json(self, body: dict, timeout: float) -> dict:
        payload = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(
            self._chat_url(),
            data=payload,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Bearer {self._api_key}',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace') if exc.fp else str(exc)
            if exc.code in (401, 403):
                raise ServerException(
                    AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                    override_detail=f'OpenAI auth failed: {detail[:400]}',
                ) from exc
            raise ServerException(
                AppErrorCode.AI_PROVIDER_ERROR,
                override_detail=f'OpenAI HTTP {exc.code}: {detail[:400]}',
            ) from exc
        except urllib.error.URLError as exc:
            raise ServerException(
                AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                override_detail=f'OpenAI unreachable: {getattr(exc, "reason", exc)}',
            ) from exc
        except TimeoutError as exc:
            raise ServerException(AppErrorCode.AI_TIMEOUT, override_detail=str(exc)) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ServerException(
                AppErrorCode.AI_INVALID_RESPONSE,
                override_detail=f'OpenAI returned non-JSON: {raw[:200]}',
            ) from exc

    def _parse(self, data: dict) -> Tuple[str, TokenUsage, FinishReason]:
        choices = data.get('choices') or []
        if not choices:
            raise ServerException(
                AppErrorCode.AI_INVALID_RESPONSE,
                override_detail='OpenAI returned no choices.',
            )
        choice = choices[0]
        message = choice.get('message') or {}
        text = (message.get('content') or '').strip()
        if not text:
            raise ServerException(
                AppErrorCode.AI_INVALID_RESPONSE,
                override_detail='OpenAI returned an empty message.',
            )
        usage_raw = data.get('usage') or {}
        usage = TokenUsage(
            input_tokens=int(usage_raw.get('prompt_tokens') or 0),
            output_tokens=int(usage_raw.get('completion_tokens') or 0),
        )
        finish = _FINISH_MAP.get(
            (choice.get('finish_reason') or '').lower(),
            FinishReason.UNKNOWN,
        )
        return text, usage, finish

    def _generate(self, prompt: Prompt) -> Tuple[str, TokenUsage, FinishReason]:
        model = prompt.options.model or self.model_name
        max_tokens = prompt.options.max_tokens or self._max_tokens
        timeout = float(prompt.options.timeout_seconds or self._timeout)
        body = {
            'model': model,
            'messages': self._to_api_messages(prompt),
            'max_tokens': max_tokens,
        }
        data = self._post_json(body, timeout)
        return self._parse(data)
