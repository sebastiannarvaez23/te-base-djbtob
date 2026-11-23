"""RequestBody schemas for ``frontend_context`` on incident reports."""
from __future__ import annotations

import json

from core.validators import Field, RequestBody, ValidationError
from necore.query.patterns import PATTERN_CONTENT
from core.validators.codes import ValidationCode

from platform.features.support.incidents.incident.application.frontend_context import (
    FRONTEND_CONTEXT_MAX_BYTES,
)

FRONTEND_CONTEXT_REQUEST_MAX_BYTES = int(FRONTEND_CONTEXT_MAX_BYTES * 1.25)


class FrontendLogEntryBody(RequestBody):
    ts = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    level = Field(
        str,
        required=False,
        default='log',
        max_length=10,
        choices=['log', 'info', 'warn', 'error', 'debug'],
    )
    message = Field(str, required=True, min_length=1, max_length=2000, pattern=PATTERN_CONTENT)


class BrowserConsoleEntryBody(RequestBody):
    ts = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    level = Field(
        str,
        required=False,
        default='log',
        max_length=10,
        choices=['log', 'info', 'warn', 'error', 'debug'],
    )
    message = Field(str, required=True, min_length=1, max_length=2000, pattern=PATTERN_CONTENT)


class FrontendEventBody(RequestBody):
    ts = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    type = Field(str, required=False, default='', max_length=32, min_length=0, pattern=PATTERN_CONTENT)
    summary = Field(str, required=True, min_length=1, max_length=500, pattern=PATTERN_CONTENT)
    request_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    correlation_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)


class FrontendApiActivityBody(RequestBody):
    ts = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    method = Field(str, required=False, default='', max_length=16, min_length=0, pattern=PATTERN_CONTENT)
    endpoint = Field(str, required=False, default='', max_length=500, min_length=0, pattern=PATTERN_CONTENT)
    status = Field(int, required=False, nullable=True, default=None)
    duration_ms = Field(int, required=False, nullable=True, default=None)
    request_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    correlation_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    result = Field(str, required=False, default='', max_length=16, min_length=0, pattern=PATTERN_CONTENT)
    error_summary = Field(str, required=False, default='', max_length=500, min_length=0, pattern=PATTERN_CONTENT)


class FrontendNavigationRouteBody(RequestBody):
    ts = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    route = Field(str, required=False, default='', max_length=200, min_length=0, pattern=PATTERN_CONTENT)
    module_code = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    module_name = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    page_section = Field(str, required=False, default='', max_length=63, min_length=0, pattern=PATTERN_CONTENT)
    feature_key = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)


class FrontendNavigationBody(RequestBody):
    current_route = Field(str, required=False, default='', max_length=200, min_length=0, pattern=PATTERN_CONTENT)
    previous_route = Field(str, required=False, default='', max_length=200, min_length=0, pattern=PATTERN_CONTENT)
    module_code = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    module_name = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    page_section = Field(str, required=False, default='', max_length=63, min_length=0, pattern=PATTERN_CONTENT)
    page_section_label = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    feature_key = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    recent_routes = Field(
        list,
        required=False,
        default=list,
        item=FrontendNavigationRouteBody,
        min_items=0,
        max_items=10,
    )


class FrontendRuntimeErrorBody(RequestBody):
    ts = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    message = Field(str, required=True, min_length=1, max_length=500, pattern=PATTERN_CONTENT)
    type = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)


class FrontendRuntimeBody(RequestBody):
    recent_errors = Field(
        list,
        required=False,
        default=list,
        item=FrontendRuntimeErrorBody,
        min_items=0,
        max_items=10,
    )
    recent_error_count = Field(int, required=False, default=0, min_value=0)
    app_uptime_ms = Field(int, required=False, default=0, min_value=0)
    pending_requests = Field(int, required=False, default=0, min_value=0)
    angular_production_mode = Field(bool, required=False, default=False)


class FrontendApplicationBody(RequestBody):
    name = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    version = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    environment = Field(str, required=False, default='', max_length=32, min_length=0, pattern=PATTERN_CONTENT)
    build = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)


class FrontendBrowserBody(RequestBody):
    browser = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    browser_version = Field(str, required=False, default='', max_length=32, min_length=0, pattern=PATTERN_CONTENT)
    language = Field(str, required=False, default='', max_length=16, min_length=0, pattern=PATTERN_CONTENT)
    locale = Field(str, required=False, default='', max_length=16, min_length=0, pattern=PATTERN_CONTENT)
    timezone = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    user_agent = Field(str, required=False, default='', max_length=500, min_length=0, pattern=PATTERN_CONTENT)


class FrontendDeviceBody(RequestBody):
    device_type = Field(
        str,
        required=False,
        default='',
        max_length=16,
        choices=['', 'desktop', 'tablet', 'mobile', 'unknown'],
    )
    os = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    os_version = Field(str, required=False, default='', max_length=32, min_length=0, pattern=PATTERN_CONTENT)
    screen_width = Field(int, required=False, default=0, min_value=0)
    screen_height = Field(int, required=False, default=0, min_value=0)
    device_pixel_ratio = Field(int, required=False, default=0, min_value=0)


class FrontendNetworkBody(RequestBody):
    online = Field(bool, required=False, default=True)
    connection_type = Field(str, required=False, default='', max_length=32, min_length=0, pattern=PATTERN_CONTENT)
    effective_type = Field(str, required=False, default='', max_length=16, min_length=0, pattern=PATTERN_CONTENT)
    recent_failed_requests = Field(int, required=False, default=0, min_value=0)
    last_disconnected_at = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    last_reconnected_at = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)


class FrontendUiBody(RequestBody):
    active_tab = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    modal_open = Field(bool, required=False, default=False)
    view = Field(str, required=False, default='', max_length=100, min_length=0, pattern=PATTERN_CONTENT)
    entity_type = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    entity_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)


class FrontendAuthEventBody(RequestBody):
    ts = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    event = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)


class FrontendSessionBody(RequestBody):
    session_started_at = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    session_duration_ms = Field(int, required=False, default=0, min_value=0)
    last_activity_at = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    session_state = Field(
        str,
        required=False,
        default='',
        max_length=16,
        choices=['', 'authenticated', 'anonymous'],
    )
    recent_auth_events = Field(
        list,
        required=False,
        default=list,
        item=FrontendAuthEventBody,
        min_items=0,
        max_items=10,
    )


class FrontendContextBody(RequestBody):
    captured_at = Field(str, required=False, default='', max_length=40, min_length=0, pattern=PATTERN_CONTENT)
    application = Field(dict, required=False, nullable=True, schema=FrontendApplicationBody)
    navigation = Field(dict, required=False, nullable=True, schema=FrontendNavigationBody)
    browser = Field(dict, required=False, nullable=True, schema=FrontendBrowserBody)
    device = Field(dict, required=False, nullable=True, schema=FrontendDeviceBody)
    network = Field(dict, required=False, nullable=True, schema=FrontendNetworkBody)
    recent_events = Field(
        list,
        required=False,
        default=list,
        item=FrontendEventBody,
        min_items=0,
        max_items=50,
    )
    recent_api_activity = Field(
        list,
        required=False,
        default=list,
        item=FrontendApiActivityBody,
        min_items=0,
        max_items=20,
    )
    runtime = Field(dict, required=False, nullable=True, schema=FrontendRuntimeBody)
    ui = Field(dict, required=False, nullable=True, schema=FrontendUiBody)
    session = Field(dict, required=False, nullable=True, schema=FrontendSessionBody)
    browser_console = Field(
        list,
        required=False,
        default=list,
        item=BrowserConsoleEntryBody,
        min_items=0,
        max_items=50,
    )
    correlation_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)
    trace_id = Field(str, required=False, default='', max_length=64, min_length=0, pattern=PATTERN_CONTENT)


def frontend_context_size_errors(field_name: str, value) -> list[ValidationError]:
    if value is None:
        return []
    try:
        size = len(json.dumps(value, ensure_ascii=False).encode('utf-8'))
    except (TypeError, ValueError):
        return [ValidationError(
            field=field_name,
            code=ValidationCode.INVALID_TYPE,
            detail=f"Field '{field_name}' must be JSON-serializable.",
        )]
    if size > FRONTEND_CONTEXT_REQUEST_MAX_BYTES:
        return [ValidationError(
            field=field_name,
            code=ValidationCode.MAX_VALUE,
            detail=(
                f"Field '{field_name}' exceeds maximum serialized size "
                f"({FRONTEND_CONTEXT_REQUEST_MAX_BYTES} bytes)."
            ),
        )]
    return []
