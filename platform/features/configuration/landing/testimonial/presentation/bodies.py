from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT

_LOCALES = ['es', 'en']
_AUTHOR_ID = Field(str, is_uuid=True)


class CreateTestimonialBody(RequestBody):
    author_id = Field(str, is_uuid=True)
    score = Field(int, min_value=1, max_value=5)
    message = Field(str, min_length=1, max_length=2000, pattern=PATTERN_CONTENT)
    author_name = Field(str, required=False, nullable=True, max_length=200, default=None, pattern=PATTERN_CONTENT)
    author_role = Field(str, required=False, max_length=200, default='', pattern=PATTERN_CONTENT)
    company_name = Field(str, required=False, nullable=True, max_length=200, default=None, pattern=PATTERN_CONTENT)
    locale = Field(str, required=False, choices=_LOCALES, default='es')
    is_published = Field(bool, required=False, default=False)
    sort_order = Field(int, required=False, min_value=0, max_value=32767, default=0)


class SubmitMyTestimonialBody(RequestBody):
    score = Field(int, min_value=1, max_value=5)
    message = Field(str, min_length=10, max_length=2000, pattern=PATTERN_CONTENT)
    locale = Field(str, required=False, choices=_LOCALES, default='es')
    accepted = Field(bool, choices=[True])


class UpdateTestimonialPromptSettingsBody(RequestBody):
    prompt_enabled = Field(bool, required=False)
    frequency_days = Field(int, required=False, min_value=0, max_value=365)
    first_appearance_days = Field(int, required=False, min_value=0, max_value=365)
    login_delay_seconds = Field(int, required=False, min_value=0, max_value=300)
    ask_after_submit = Field(bool, required=False)


class RepromptTestimonialsBody(RequestBody):
    author_ids = Field(list, min_items=1, max_items=500)

    def validate(self):
        ok, errors = super().validate()
        if not ok:
            return ok, errors
        values = self.validated_data.get('author_ids') or []
        extra = []
        unique = []
        seen = set()
        for index, value in enumerate(values):
            _AUTHOR_ID.name = f'author_ids[{index}]'
            item_errors, item = _AUTHOR_ID.validate_and_coerce(value)
            if item_errors:
                extra.extend(item_errors)
                continue
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        if extra:
            return False, extra
        self.validated_data['author_ids'] = unique
        return True, []


class UpdateTestimonialBody(RequestBody):
    author_id = Field(str, required=False, is_uuid=True)
    score = Field(int, required=False, min_value=1, max_value=5)
    message = Field(str, required=False, min_length=1, max_length=2000, pattern=PATTERN_CONTENT)
    author_name = Field(str, required=False, nullable=True, max_length=200, pattern=PATTERN_CONTENT)
    author_role = Field(str, required=False, max_length=200, pattern=PATTERN_CONTENT)
    company_name = Field(str, required=False, nullable=True, max_length=200, pattern=PATTERN_CONTENT)
    locale = Field(str, required=False, choices=_LOCALES)
    is_published = Field(bool, required=False)
    sort_order = Field(int, required=False, min_value=0, max_value=32767)
