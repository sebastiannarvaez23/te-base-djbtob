from typing import Optional

from platform.features.configuration.assistant.assistant.domain.interfaces import (
    IAssistantSettingsRepository,
)
from platform.features.configuration.assistant.assistant.domain.mapping import merge_tool_map
from platform.features.configuration.assistant.assistant.domain.schemas import (
    AssistantSettingsPersistSchema,
)
from platform.features.configuration.assistant.assistant.models import AssistantSettings


def _to_persist(obj: AssistantSettings) -> AssistantSettingsPersistSchema:
    return AssistantSettingsPersistSchema(
        enabled=obj.enabled,
        provider=obj.provider,
        max_message_chars=obj.max_message_chars,
        max_agent_steps=obj.max_agent_steps,
        history_turns=obj.history_turns,
        out_of_scope_message=obj.out_of_scope_message or '',
        require_tool_before_facts=obj.require_tool_before_facts,
        enabled_tools=merge_tool_map(obj.enabled_tools),
    )


class DjangoAssistantSettingsRepository(IAssistantSettingsRepository):

    def get(self) -> Optional[AssistantSettingsPersistSchema]:
        obj = AssistantSettings.objects.filter(
            singleton_key=AssistantSettings.SINGLETON_KEY,
        ).first()
        if obj is None:
            return None
        return _to_persist(obj)

    def save(self, data: AssistantSettingsPersistSchema) -> AssistantSettingsPersistSchema:
        obj, _ = AssistantSettings.objects.update_or_create(
            singleton_key=AssistantSettings.SINGLETON_KEY,
            defaults={
                'enabled': data.enabled,
                'provider': data.provider,
                'max_message_chars': data.max_message_chars,
                'max_agent_steps': data.max_agent_steps,
                'history_turns': data.history_turns,
                'out_of_scope_message': data.out_of_scope_message,
                'require_tool_before_facts': data.require_tool_before_facts,
                'enabled_tools': data.enabled_tools,
            },
        )
        return _to_persist(obj)
