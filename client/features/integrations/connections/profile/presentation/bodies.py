from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CODE, PATTERN_CONTENT


class CreateConnectionBody(RequestBody):
    connector_key = Field(str, max_length=50, pattern=PATTERN_CODE)
    name = Field(str, max_length=120, pattern=PATTERN_CONTENT)
    environment = Field(str, choices=['PROSANDBOX', 'CLIENT_TEST', 'CLIENT_PROD'])
    config = Field(dict, required=False, default=dict)
    schedule_cron = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    secrets = Field(dict, required=False, default=dict)


class UpdateConnectionBody(RequestBody):
    name = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    environment = Field(
        str, required=False, choices=['PROSANDBOX', 'CLIENT_TEST', 'CLIENT_PROD'],
    )
    config = Field(dict, required=False)
    status = Field(str, required=False, choices=['ACTIVE', 'PAUSED', 'DEGRADED', 'ERROR'])
    schedule_cron = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    secrets = Field(dict, required=False)


class CreateFieldMappingBody(RequestBody):
    connection_id = Field(str, is_uuid=True)
    entity = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='order')
    direction = Field(str, choices=['INBOUND', 'OUTBOUND'])
    rules = Field(list, required=True)
    is_active = Field(bool, required=False, default=True)


class UpdateFieldMappingBody(RequestBody):
    rules = Field(list, required=False)
    is_active = Field(bool, required=False)
