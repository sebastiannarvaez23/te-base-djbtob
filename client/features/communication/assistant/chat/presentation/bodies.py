from core.ai.assistant_catalog import ASSISTANT_MAX_MESSAGE_MAX
from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class ChatTurnUiContextBody(RequestBody):
    """Snapshot of the operator's current WMS screen (optional per turn)."""

    route = Field(str, required=False, default='', max_length=200, min_length=0, pattern=PATTERN_CONTENT)
    module_id = Field(str, required=False, default='', max_length=36, min_length=0, is_uuid=True)
    module_code = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CODE)
    module_name = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    feature_key = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CODE)
    page_section = Field(str, required=False, default='', max_length=63, min_length=0, pattern=PATTERN_CODE)
    page_section_label = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    module_purpose = Field(str, required=False, default='', max_length=300, min_length=0, pattern=PATTERN_CONTENT)
    entity_type = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CODE)
    entity_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)


class ChatTurnBody(RequestBody):
    message = Field(str, max_length=ASSISTANT_MAX_MESSAGE_MAX, min_length=1, pattern=PATTERN_CONTENT)
    conversation_id = Field(str, required=False, nullable=True, is_uuid=True)
    ui_context = Field(dict, required=False, nullable=True, schema=ChatTurnUiContextBody)


class RenameConversationBody(RequestBody):
    title = Field(str, max_length=200, min_length=1, pattern=PATTERN_CONTENT)
