from core.validators import Field, RequestBody


class UpdateLogConfigBody(RequestBody):
    enabled = Field(bool, required=False)
    retention_days = Field(int, required=False, min_value=1)
    archive_enabled = Field(bool, required=False)
    archive_after_days = Field(int, required=False, nullable=True, min_value=1)
    max_records = Field(int, required=False, nullable=True, min_value=100)
    cleanup_frequency = Field(
        str,
        required=False,
        choices=['daily', 'weekly', 'monthly'],
    )
