from datetime import datetime, timezone
from uuid import UUID

from core.cache import invalidate_cache
from core.errors import AppErrorCode, ValidationAppException

from platform.features.configuration.landing.testimonial.domain.interfaces import (
    ITestimonialPromptReceiptRepository,
    ITestimonialPromptSettingsRepository,
    ITestimonialRepository,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    RepromptTestimonialsResultSchema,
    RepromptTestimonialsSchema,
    TestimonialPromptDecisionSchema,
    TestimonialPromptReceiptSchema,
    TestimonialPromptSettingsSchema,
    UpdateTestimonialPromptSettingsSchema,
)
from core.trace import trace_layer

_CACHE_PREFIX = 'testimonials'


def _defaults() -> TestimonialPromptSettingsSchema:
    return TestimonialPromptSettingsSchema()


def _settings(
    repository: ITestimonialPromptSettingsRepository,
) -> TestimonialPromptSettingsSchema:
    return repository.get() or _defaults()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _days_since(value: datetime) -> int:
    return (datetime.now(timezone.utc) - _aware(value)).days


def _decision(
    should_prompt: bool,
    cfg: TestimonialPromptSettingsSchema,
) -> TestimonialPromptDecisionSchema:
    return TestimonialPromptDecisionSchema(
        should_prompt=should_prompt,
        delay_seconds=cfg.login_delay_seconds if should_prompt else 0,
    )


class GetTestimonialPromptSettingsUseCase:
    def __init__(self, repository: ITestimonialPromptSettingsRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self) -> TestimonialPromptSettingsSchema:
        return _settings(self.repository)


class UpdateTestimonialPromptSettingsUseCase:
    def __init__(self, repository: ITestimonialPromptSettingsRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, data: UpdateTestimonialPromptSettingsSchema,
    ) -> TestimonialPromptSettingsSchema:
        current = self.repository.get() or _defaults()
        fields = data.model_dump(exclude_unset=True)
        if not fields:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        updated = current.model_copy(update=fields)
        result = self.repository.save(updated)
        invalidate_cache(f'{_CACHE_PREFIX}_*')
        return result


class RepromptTestimonialsUseCase:
    """Mark selected rated authors so the prompt appears again on next login."""

    def __init__(
        self,
        testimonials: ITestimonialRepository,
        receipts: ITestimonialPromptReceiptRepository,
    ):
        self.testimonials = testimonials
        self.receipts = receipts

    @trace_layer('application')
    def execute(
        self, data: RepromptTestimonialsSchema,
    ) -> RepromptTestimonialsResultSchema:
        unique = list(dict.fromkeys(data.author_ids))
        if not unique:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        found = self.testimonials.list_by_author_ids(unique)
        found_ids = {row.author_id for row in found}
        if found_ids != set(unique):
            raise ValidationAppException(AppErrorCode.TESTIMONIAL_REPROMPT_NOT_ELIGIBLE)
        requested = self.receipts.mark_pending_reprompt(unique)
        return RepromptTestimonialsResultSchema(requested=requested)


class RecordTestimonialPromptSeenUseCase:
    """Persist first-seen clock. Idempotent. Does not count as a prompt."""

    def __init__(self, receipts: ITestimonialPromptReceiptRepository):
        self.receipts = receipts

    @trace_layer('application')
    def execute(self, user_id: UUID) -> TestimonialPromptReceiptSchema:
        existing = self.receipts.get(user_id)
        if existing and existing.first_seen_at:
            return existing
        now = datetime.now(timezone.utc)
        return self.receipts.upsert(TestimonialPromptReceiptSchema(
            user_id=user_id,
            last_prompted_at=existing.last_prompted_at if existing else None,
            first_seen_at=now,
            pending_reprompt=bool(existing.pending_reprompt) if existing else False,
        ))


class DecideTestimonialPromptUseCase:
    def __init__(
        self,
        settings: ITestimonialPromptSettingsRepository,
        receipts: ITestimonialPromptReceiptRepository,
        testimonials: ITestimonialRepository,
    ):
        self.settings = settings
        self.receipts = receipts
        self.testimonials = testimonials

    @trace_layer('application')
    def execute(self, user_id: UUID) -> TestimonialPromptDecisionSchema:
        cfg = _settings(self.settings)
        if not cfg.prompt_enabled:
            return _decision(False, cfg)

        receipt = self.receipts.get(user_id)
        if receipt and receipt.pending_reprompt:
            return _decision(True, cfg)

        row = self.testimonials.get_by_author(user_id)
        signed = bool(row and row.seal)
        if signed and not cfg.ask_after_submit:
            return _decision(False, cfg)

        never_prompted = receipt is None or receipt.last_prompted_at is None
        if never_prompted:
            if not self._first_appearance_ready(cfg, receipt):
                return _decision(False, cfg)
            return _decision(True, cfg)

        if cfg.frequency_days == 0:
            return _decision(True, cfg)
        return _decision(_days_since(receipt.last_prompted_at) >= cfg.frequency_days, cfg)

    def _first_appearance_ready(
        self,
        cfg: TestimonialPromptSettingsSchema,
        receipt: TestimonialPromptReceiptSchema | None,
    ) -> bool:
        if cfg.first_appearance_days <= 0:
            return True
        seen_at = receipt.first_seen_at if receipt else None
        if seen_at is None:
            return False
        return _days_since(seen_at) >= cfg.first_appearance_days


class AckTestimonialPromptUseCase:
    def __init__(
        self,
        receipts: ITestimonialPromptReceiptRepository,
    ):
        self.receipts = receipts

    @trace_layer('application')
    def execute(self, user_id: UUID) -> TestimonialPromptReceiptSchema:
        existing = self.receipts.get(user_id)
        now = datetime.now(timezone.utc)
        return self.receipts.upsert(TestimonialPromptReceiptSchema(
            user_id=user_id,
            last_prompted_at=now,
            first_seen_at=(
                existing.first_seen_at
                if existing and existing.first_seen_at
                else now
            ),
            pending_reprompt=False,
        ))
