from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_NAME_RE = r'^[A-Za-záéíóúÁÉÍÓÚñÑüÜ ]+$'
_DESC_RE = r'^[A-Za-záéíóúÁÉÍÓÚñÑüÜ ]*$'
_CODE_RE = r'^[A-Z_]+$'


class CreateParameterBody(RequestBody):
    parameter_type = Field(str, is_uuid=True)
    code = Field(str, min_length=3, max_length=20, pattern=_CODE_RE)
    name = Field(str, min_length=3, max_length=30, pattern=_NAME_RE)
    description = Field(str, required=False, min_length=0, max_length=120, pattern=_DESC_RE, default='')
    data_type = Field(str, choices=['STRING', 'INT', 'DECIMAL', 'BOOL', 'JSON'])
    value = Field(str, max_length=5000, pattern=PATTERN_CONTENT)
    is_active = Field(bool, required=False, default=True)


class UpdateParameterBody(RequestBody):
    parameter_type = Field(str, required=False, is_uuid=True)
    code = Field(str, required=False, min_length=3, max_length=20, pattern=_CODE_RE)
    name = Field(str, required=False, min_length=3, max_length=30, pattern=_NAME_RE)
    description = Field(str, required=False, max_length=120, pattern=_DESC_RE)
    data_type = Field(str, required=False, choices=['STRING', 'INT', 'DECIMAL', 'BOOL', 'JSON'])
    value = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False)
    is_active = Field(bool, required=False)
