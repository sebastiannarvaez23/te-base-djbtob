from core.validators import Field, RequestBody

_NAME_RE = r'^[A-Za-záéíóúÁÉÍÓÚñÑüÜ ]+$'
_DESC_RE = r'^[A-Za-záéíóúÁÉÍÓÚñÑüÜ ]*$'
_CODE_RE = r'^[A-Z_]+$'


class CreateParameterTypeBody(RequestBody):
    code = Field(str, min_length=3, max_length=20, pattern=_CODE_RE)
    name = Field(str, min_length=3, max_length=30, pattern=_NAME_RE)
    description = Field(str, required=False, max_length=120, pattern=_DESC_RE, default='')
    is_active = Field(bool, required=False, default=True)


class UpdateParameterTypeBody(RequestBody):
    code = Field(str, required=False, min_length=3, max_length=20, pattern=_CODE_RE)
    name = Field(str, required=False, min_length=3, max_length=30, pattern=_NAME_RE)
    description = Field(str, required=False, max_length=120, pattern=_DESC_RE)
    is_active = Field(bool, required=False)
