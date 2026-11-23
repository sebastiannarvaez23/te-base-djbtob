from core.validators import Field, RequestBody


class ToggleLandingSectionBody(RequestBody):
    is_visible = Field(bool, required=True)
