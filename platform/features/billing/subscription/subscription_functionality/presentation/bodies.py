from core.validators import Field, RequestBody


class UpdateSubscriptionFunctionalitiesBody(RequestBody):
    functionality_keys = Field(list, required=True)
