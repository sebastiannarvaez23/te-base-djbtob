from core.validators import Field, RequestBody


class UpdateSubscriptionModulesBody(RequestBody):
    module_codes = Field(list, required=True)
