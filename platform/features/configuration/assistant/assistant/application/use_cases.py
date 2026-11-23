from pydantic import ValidationError as PydanticValidationError

from core.ai.assistant_catalog import ASSISTANT_TOOL_KEYS
from core.ai.assistant_policy import AssistantRuntimePolicy
from core.cache import invalidate_cache, use_case_cache
from core.errors import ValidationAppException
from core.errors.codes import AppErrorCode

from platform.features.configuration.assistant.assistant.domain.interfaces import (
    IAssistantSettingsRepository,
    IAssistantUsageReader,
    IRuntimeHealthProbe,
)
from platform.features.configuration.assistant.assistant.domain.mapping import (
    defaults_persist,
    merge_tool_map,
    persist_to_policy,
    tools_for_admin,
)
from platform.features.configuration.assistant.assistant.domain.schemas import (
    AssistantAdminSettingsSchema,
    AssistantSettingsPersistSchema,
    AssistantUsageSchema,
)
from core.trace import trace_layer


def _admin_dto(
    persist: AssistantSettingsPersistSchema,
    *,
    health: IRuntimeHealthProbe,
    usage: AssistantUsageSchema,
) -> AssistantAdminSettingsSchema:
    status = health.probe(persist.provider)
    if status not in ('ok', 'down', 'unknown'):
        status = 'unknown'
    return AssistantAdminSettingsSchema(
        enabled=persist.enabled,
        provider=persist.provider,
        max_message_chars=persist.max_message_chars,
        max_agent_steps=persist.max_agent_steps,
        history_turns=persist.history_turns,
        out_of_scope_message=persist.out_of_scope_message,
        require_tool_before_facts=persist.require_tool_before_facts,
        tools=tools_for_admin(persist.enabled_tools),
        runtime_health=status,
        usage=usage,
    )


class LoadAssistantRuntimePolicyUseCase:
    def __init__(self, repository: IAssistantSettingsRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix='assistant_runtime_policy')
    def execute(self) -> AssistantRuntimePolicy:
        return persist_to_policy(self.repository.get())


class GetAssistantAdminSettingsUseCase:
    def __init__(
        self,
        repository: IAssistantSettingsRepository,
        health: IRuntimeHealthProbe,
        usage: IAssistantUsageReader,
    ):
        self.repository = repository
        self.health = health
        self.usage = usage

    @trace_layer('application')
    def execute(self) -> AssistantAdminSettingsSchema:
        persist = self.repository.get() or defaults_persist()
        return _admin_dto(
            persist,
            health=self.health,
            usage=self.usage.collect_24h(),
        )


class UpdateAssistantAdminSettingsUseCase:
    def __init__(
        self,
        repository: IAssistantSettingsRepository,
        health: IRuntimeHealthProbe,
        usage: IAssistantUsageReader,
    ):
        self.repository = repository
        self.health = health
        self.usage = usage

    @trace_layer('application')
    def execute(self, body: dict) -> AssistantAdminSettingsSchema:
        tools = body.get('tools') or []
        seen: set[str] = set()
        tool_map = merge_tool_map(None)
        for item in tools:
            key = (item.get('key') or '').strip()
            if key not in ASSISTANT_TOOL_KEYS:
                raise ValidationAppException(AppErrorCode.AI_UNKNOWN_TOOL)
            if key in seen:
                raise ValidationAppException(
                    AppErrorCode.VALIDATION_ERROR,
                    override_detail=f'Duplicate tool key: {key}',
                )
            seen.add(key)
            tool_map[key] = bool(item.get('enabled'))

        if seen != set(ASSISTANT_TOOL_KEYS):
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='tools must include every catalog key exactly once.',
            )

        payload = {
            'enabled': body['enabled'],
            'provider': body['provider'],
            'max_message_chars': body['max_message_chars'],
            'max_agent_steps': body['max_agent_steps'],
            'history_turns': body['history_turns'],
            'out_of_scope_message': body.get('out_of_scope_message') or '',
            'require_tool_before_facts': body['require_tool_before_facts'],
            'enabled_tools': tool_map,
        }
        try:
            persist = AssistantSettingsPersistSchema(**payload)
        except PydanticValidationError as exc:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=str(exc.errors()[0].get('msg') if exc.errors() else exc),
            ) from exc

        saved = self.repository.save(persist)
        invalidate_cache('assistant_runtime_policy*')
        # Usage no se recalcula en PATCH (costoso). Health sí, es barato salvo local.
        return _admin_dto(
            saved,
            health=self.health,
            usage=self.usage.collect_24h(),
        )
