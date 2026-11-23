from core.ai.assistant_catalog import (
    ASSISTANT_HISTORY_MAX,
    ASSISTANT_HISTORY_MIN,
    ASSISTANT_MAX_MESSAGE_MAX,
    ASSISTANT_MAX_MESSAGE_MIN,
    ASSISTANT_OUT_OF_SCOPE_MAX,
    ASSISTANT_PROVIDERS,
    ASSISTANT_STEPS_MAX,
    ASSISTANT_STEPS_MIN,
    ASSISTANT_TOOL_KEYS,
)
from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_CATALOG_SIZE = len(ASSISTANT_TOOL_KEYS)


class AssistantToolToggleBody(RequestBody):
    key = Field(str, choices=list(ASSISTANT_TOOL_KEYS), max_length=80, min_length=1)
    enabled = Field(bool, required=True)


class UpdateAssistantSettingsBody(RequestBody):
    enabled = Field(bool, required=True)
    provider = Field(str, required=True, choices=list(ASSISTANT_PROVIDERS))
    max_message_chars = Field(
        int, min_value=ASSISTANT_MAX_MESSAGE_MIN, max_value=ASSISTANT_MAX_MESSAGE_MAX,
    )
    max_agent_steps = Field(
        int, min_value=ASSISTANT_STEPS_MIN, max_value=ASSISTANT_STEPS_MAX,
    )
    history_turns = Field(
        int, min_value=ASSISTANT_HISTORY_MIN, max_value=ASSISTANT_HISTORY_MAX,
    )
    out_of_scope_message = Field(
        str,
        required=False,
        default='',
        max_length=ASSISTANT_OUT_OF_SCOPE_MAX,
        min_length=0,
        pattern=PATTERN_CONTENT,
    )
    require_tool_before_facts = Field(bool, required=True)
    tools = Field(
        list,
        item=AssistantToolToggleBody,
        min_items=_CATALOG_SIZE,
        max_items=_CATALOG_SIZE,
    )
