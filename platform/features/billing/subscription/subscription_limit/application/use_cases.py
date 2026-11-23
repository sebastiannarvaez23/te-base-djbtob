import uuid
from typing import List, Optional

from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException, ValidationAppException
from ..domain.interfaces import ISubscriptionLimitRepository
from ..domain.schemas import CreateSubscriptionLimitSchema, SubscriptionLimitSchema, UpdateSubscriptionLimitSchema
from ..domain.window import WindowHoursError, resolved_window_hours
from core.trace import trace_layer


class GetAllSubscriptionLimitsUseCase:
    def __init__(self, repository: ISubscriptionLimitRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[SubscriptionLimitSchema]:
        return self.repository.get_all(filters=filters)


class GetSubscriptionLimitsBySubscriptionUseCase:
    def __init__(self, repository: ISubscriptionLimitRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionLimitSchema]:
        return self.repository.get_by_subscription(subscription_id, filters=filters)


class GetSubscriptionLimitByIdUseCase:
    def __init__(self, repository: ISubscriptionLimitRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> Optional[SubscriptionLimitSchema]:
        return self.repository.get_by_id(id)


class CreateSubscriptionLimitUseCase:
    def __init__(self, repository: ISubscriptionLimitRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateSubscriptionLimitSchema) -> SubscriptionLimitSchema:
        try:
            return self.repository.create(data)
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.SLIMIT_DUPLICATE,
                override_detail=(
                    'A limit for this functionality already exists in the given subscription.'
                ),
            )


class UpdateSubscriptionLimitUseCase:
    def __init__(self, repository: ISubscriptionLimitRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateSubscriptionLimitSchema) -> Optional[SubscriptionLimitSchema]:
        existing = self.repository.get_by_id(id)
        if existing is None:
            return None

        dump = data.model_dump(exclude_unset=True)
        validation_type = dump.get('validation_type', existing.validation_type)
        hours_source = dump['window_hours'] if 'window_hours' in dump else existing.window_hours
        try:
            dump['window_hours'] = resolved_window_hours(
                validation_type,
                hours_source,
                require_if_window=True,
            )
        except WindowHoursError as exc:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=str(exc),
                context={'field': 'window_hours'},
            ) from exc

        return self.repository.update(id, UpdateSubscriptionLimitSchema(**dump))


class DeleteSubscriptionLimitUseCase:
    def __init__(self, repository: ISubscriptionLimitRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        return self.repository.delete(id)
