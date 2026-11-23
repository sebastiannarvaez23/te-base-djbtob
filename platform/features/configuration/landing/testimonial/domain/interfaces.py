from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from uuid import UUID

from .schemas import (
    AuthorSnapshot,
    CreateTestimonialSchema,
    SignedTestimonialDraft,
    TestimonialListFilters,
    TestimonialPromptReceiptSchema,
    TestimonialPromptSettingsSchema,
    TestimonialSchema,
    UpdateTestimonialSchema,
)


class ITestimonialRepository(ABC):

    @abstractmethod
    def list_page(
        self,
        filters: TestimonialListFilters,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Tuple[List[TestimonialSchema], int]:
        ...

    @abstractmethod
    def get_by_id(self, testimonial_id: UUID) -> Optional[TestimonialSchema]:
        ...

    @abstractmethod
    def get_by_author(self, author_id: UUID) -> Optional[TestimonialSchema]:
        ...

    @abstractmethod
    def list_by_author_ids(self, author_ids: List[UUID]) -> List[TestimonialSchema]:
        ...

    @abstractmethod
    def get_author(self, author_id: UUID) -> Optional[AuthorSnapshot]:
        ...

    @abstractmethod
    def create(self, data: CreateTestimonialSchema) -> TestimonialSchema:
        ...

    @abstractmethod
    def replace_live(
        self, author_id: UUID, data: SignedTestimonialDraft,
    ) -> TestimonialSchema:
        ...

    @abstractmethod
    def update(
        self, testimonial_id: UUID, data: UpdateTestimonialSchema,
    ) -> Optional[TestimonialSchema]:
        ...


class ITestimonialPromptSettingsRepository(ABC):

    @abstractmethod
    def get(self) -> Optional[TestimonialPromptSettingsSchema]:
        ...

    @abstractmethod
    def save(
        self, data: TestimonialPromptSettingsSchema,
    ) -> TestimonialPromptSettingsSchema:
        ...


class ITestimonialPromptReceiptRepository(ABC):

    @abstractmethod
    def get(self, user_id: UUID) -> Optional[TestimonialPromptReceiptSchema]:
        ...

    @abstractmethod
    def upsert(
        self, data: TestimonialPromptReceiptSchema,
    ) -> TestimonialPromptReceiptSchema:
        ...

    @abstractmethod
    def mark_pending_reprompt(self, user_ids: List[UUID]) -> int:
        ...
