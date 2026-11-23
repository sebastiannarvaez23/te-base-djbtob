from core.validators import Field, RequestBody

from platform.features.support.incidents.incident.presentation.frontend_context_bodies import (
    FrontendContextBody,
    FrontendLogEntryBody,
    frontend_context_size_errors,
)
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT

class ReportIncidentBody(RequestBody):
    token = Field(str, required=True, min_length=20, max_length=128, pattern=PATTERN_CONTENT)
    comment = Field(str, required=False, max_length=2000, pattern=PATTERN_CONTENT)
    frontend_logs = Field(
        list,
        required=False,
        default=list,
        item=FrontendLogEntryBody,
        min_items=0,
        max_items=50,
    )
    frontend_context = Field(dict, required=False, nullable=True, default=None, schema=FrontendContextBody)

    def validate(self):
        ok, errors = super().validate()
        if ok:
            errors.extend(frontend_context_size_errors(
                'frontend_context',
                self._validated_data.get('frontend_context'),
            ))
            ok = len(errors) == 0
        return ok, errors

class ManualIncidentMessageBody(RequestBody):
    id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    role = Field(
        str,
        required=True,
        max_length=20,
        min_length=1,
        choices=['user', 'assistant', 'system'],
    )
    text = Field(str, required=True, max_length=8000, min_length=0, pattern=PATTERN_CONTENT)

class ManualIncidentUiContextBody(RequestBody):
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

class ManualIncidentConversationBody(RequestBody):
    exported_at = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    conversation_id = Field(str, required=False, nullable=True, max_length=36, min_length=0, is_uuid=True)
    ui_context = Field(dict, required=False, nullable=True, schema=ManualIncidentUiContextBody)
    messages = Field(list, required=True, item=ManualIncidentMessageBody, min_items=0, max_items=200)

class ReportManualIncidentBody(RequestBody):
    comment = Field(str, required=True, min_length=1, max_length=2000, pattern=PATTERN_CONTENT)
    conversation = Field(dict, required=True, schema=ManualIncidentConversationBody)
    ui_context = Field(dict, required=False, nullable=True, schema=ManualIncidentUiContextBody)
    source = Field(
        str,
        required=False,
        default='assistant',
        choices=['assistant', 'toolbar'],
        max_length=32,
    )
    kind = Field(
        str,
        required=False,
        default='incident',
        choices=['incident', 'suggestion'],
        max_length=20,
    )
    frontend_logs = Field(
        list,
        required=False,
        default=list,
        item=FrontendLogEntryBody,
        min_items=0,
        max_items=50,
    )
    frontend_context = Field(dict, required=False, nullable=True, default=None, schema=FrontendContextBody)

    def validate(self):
        ok, errors = super().validate()
        if ok:
            errors.extend(frontend_context_size_errors(
                'frontend_context',
                self._validated_data.get('frontend_context'),
            ))
            ok = len(errors) == 0
        return ok, errors

class UpdateIncidentStatusBody(RequestBody):
    status = Field(
        str,
        choices=['open', 'in_progress', 'resolved', 'closed', 'discarded'],
    )
    assigned_admin_id = Field(
        str, required=False, nullable=True, default=None, max_length=64, is_uuid=True,
    )
    resolution_notes = Field(str, required=False, max_length=5000, default='', pattern=PATTERN_CONTENT)

    def validate(self):
        if self._data.get('assigned_admin_id') == '':
            self._data['assigned_admin_id'] = None
        notes = self._data.get('resolution_notes')
        if isinstance(notes, str):
            self._data['resolution_notes'] = notes.strip()
        return super().validate()
