from core.validators import (
    DATE_FORMAT_CHOICES,
    TIME_FORMAT_CHOICES,
    Field,
    IanaTimezoneBodyMixin,
    RequestBody,
    TimeFormatBodyMixin,
)
from necore.query.patterns import PATTERN_CONTENT, PATTERN_PHONE

class UpdateAdminUserPreferencesBody(IanaTimezoneBodyMixin, TimeFormatBodyMixin, RequestBody):
    language              = Field(str,  required=False, min_length=2,  max_length=5, pattern=PATTERN_CONTENT)
    theme                 = Field(str,  required=False, min_length=2,  max_length=10, pattern=PATTERN_CONTENT)
    timezone              = Field(str,  required=False, min_length=2,  max_length=60, pattern=PATTERN_CONTENT)
    date_format           = Field(str,  required=False, min_length=5,  max_length=12, choices=list(DATE_FORMAT_CHOICES))
    time_format           = Field(str,  required=False, min_length=2,  max_length=2,  choices=list(TIME_FORMAT_CHOICES))
    sidebar_collapsed     = Field(None, required=False)
    items_per_page        = Field(int,  required=False, min_value=5, max_value=200)
    notifications_enabled = Field(None, required=False)

class UpdateAdminUserProfileBody(RequestBody):
    first_name = Field(str, required=False, min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    last_name  = Field(str, required=False, min_length=2,  max_length=30, pattern=PATTERN_CONTENT)
    email      = Field(str, required=False, is_email=True)
    telephone  = Field(str, required=False, min_length=10, max_length=15, pattern=PATTERN_PHONE)
