from typing import Optional

from core.ai.assistant_catalog import ASSISTANT_TOOL_KEYS
from core.ai.assistant_policy import AssistantRuntimePolicy, default_assistant_policy
from platform.features.configuration.assistant.assistant.domain.schemas import (
    AssistantSettingsPersistSchema,
    AssistantToolToggleSchema,
)


def default_tool_map() -> dict[str, bool]:
    return {key: True for key in ASSISTANT_TOOL_KEYS}


def merge_tool_map(stored: dict | None) -> dict[str, bool]:
    merged = default_tool_map()
    if isinstance(stored, dict):
        for key, enabled in stored.items():
            if key in merged:
                merged[key] = bool(enabled)
    return merged


def tools_for_admin(stored: dict | None) -> list[AssistantToolToggleSchema]:
    merged = merge_tool_map(stored)
    return [
        AssistantToolToggleSchema(key=key, enabled=merged[key])
        for key in ASSISTANT_TOOL_KEYS
    ]


def persist_to_policy(data: Optional[AssistantSettingsPersistSchema]) -> AssistantRuntimePolicy:
    if data is None:
        return default_assistant_policy()
    merged = merge_tool_map(data.enabled_tools)
    enabled_keys = tuple(key for key in ASSISTANT_TOOL_KEYS if merged.get(key, True))
    return AssistantRuntimePolicy(
        enabled=data.enabled,
        provider=data.provider,
        max_message_chars=data.max_message_chars,
        max_agent_steps=data.max_agent_steps,
        history_turns=data.history_turns,
        out_of_scope_message=data.out_of_scope_message,
        require_tool_before_facts=data.require_tool_before_facts,
        enabled_tool_keys=enabled_keys,
    )


def defaults_persist() -> AssistantSettingsPersistSchema:
    policy = default_assistant_policy()
    return AssistantSettingsPersistSchema(
        enabled=policy.enabled,
        provider=policy.provider,
        max_message_chars=policy.max_message_chars,
        max_agent_steps=policy.max_agent_steps,
        history_turns=policy.history_turns,
        out_of_scope_message=policy.out_of_scope_message,
        require_tool_before_facts=policy.require_tool_before_facts,
        enabled_tools=merge_tool_map(None),
    )
