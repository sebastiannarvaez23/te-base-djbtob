from core.validators import Field, RequestBody, ValidationCode, ValidationError
from platform.features.documents.document_template.document_template.domain.template_validation import (
    validate_template_sync,
)
from necore.query.patterns import PATTERN_CONTENT

_CODE = r'^[A-Z0-9_]+$'

class CreateDocumentTemplateBody(RequestBody):
    code = Field(str, max_length=80, pattern=_CODE)
    name = Field(str, max_length=200, pattern=PATTERN_CONTENT)
    kind = Field(str, max_length=50, pattern=_CODE)
    html_template = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    mock_data = Field(dict, required=False, default=dict)
    description = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    is_active = Field(bool, required=False, default=True)
    allowed_formats = Field(list, required=False, default=list)
    default_format = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='PDF')
    format_configs = Field(dict, required=False, default=dict)
    is_storable = Field(bool, required=False, default=False)
    storage_bucket = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')
    storage_path_template = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='')

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        try:
            d = self.validated_data
            validate_template_sync(
                allowed_formats=d.get('allowed_formats', []),
                default_format=d.get('default_format', 'PDF'),
                format_configs=d.get('format_configs', {}),
                is_storable=d.get('is_storable', False),
                storage_path_template=d.get('storage_path_template', ''),
            )
        except Exception as exc:
            return False, [ValidationError(
                'allowed_formats', ValidationCode.INVALID_CHOICE, str(exc),
            )]
        return True, []

class UpdateDocumentTemplateBody(RequestBody):
    code = Field(str, required=False, max_length=80, pattern=_CODE)
    name = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    kind = Field(str, required=False, max_length=50, pattern=_CODE)
    html_template = Field(str, max_length=500_000, pattern=PATTERN_CONTENT, required=False)
    mock_data = Field(dict, required=False)
    description = Field(str, max_length=20_000, pattern=PATTERN_CONTENT, required=False)
    is_active = Field(bool, required=False)
    allowed_formats = Field(list, required=False)
    default_format = Field(str, max_length=10, pattern=PATTERN_CONTENT, required=False)
    format_configs = Field(dict, required=False)
    is_storable = Field(bool, required=False)
    storage_bucket = Field(str, max_length=120, pattern=PATTERN_CONTENT, required=False)
    storage_path_template = Field(str, max_length=500, pattern=PATTERN_CONTENT, required=False)

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        d = self.validated_data
        format_keys = ('allowed_formats', 'default_format', 'format_configs')
        if any(k in d for k in format_keys):
            missing = [k for k in format_keys if k not in d]
            if missing:
                return False, [ValidationError(
                    missing[0],
                    ValidationCode.REQUIRED,
                    'When updating template formats, send allowed_formats, '
                    'default_format and format_configs together.',
                )]
            try:
                validate_template_sync(
                    allowed_formats=d['allowed_formats'],
                    default_format=d['default_format'],
                    format_configs=d['format_configs'],
                    is_storable=d.get('is_storable', False),
                    storage_path_template=d.get('storage_path_template', ''),
                )
            except Exception as exc:
                return False, [ValidationError(
                    'allowed_formats', ValidationCode.INVALID_CHOICE, str(exc),
                )]
        elif d.get('is_storable') is True:
            # Early reject storability without a uniqueness token; full merge
            # validation remains in UpdateDocumentTemplateUseCase.
            try:
                validate_template_sync(
                    allowed_formats=['PDF'],
                    default_format='PDF',
                    format_configs={'PDF': {}},
                    is_storable=True,
                    storage_path_template=d.get('storage_path_template', ''),
                )
            except Exception as exc:
                return False, [ValidationError(
                    'storage_path_template', ValidationCode.INVALID_CHOICE, str(exc),
                )]
        return True, []

class DocumentPreviewBody(RequestBody):
    format = Field(str, max_length=5000, pattern=PATTERN_CONTENT, required=False, default='PDF')
    data = Field(dict, required=False, default=dict)

class DocumentGeneratedDownloadBody(RequestBody):
    object_key = Field(str, max_length=5000, pattern=PATTERN_CONTENT, min_length=1)
