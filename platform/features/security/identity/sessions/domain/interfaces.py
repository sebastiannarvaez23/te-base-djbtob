from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from core.query.core import PaginatedQuery, PaginatedResult


class ISessionRepository(ABC):

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def kill_session(self, session_id: str) -> bool:
        """Delete a single session by its token key. Returns True if found and deleted."""
        ...

    @abstractmethod
    def kill_by_user(self, user_id: UUID) -> int:
        """Delete all sessions for a given user. Returns the number of sessions deleted."""
        ...

    @abstractmethod
    def kill_by_company(self, company_id: UUID) -> int:
        """Delete all sessions for all users of a given company. Returns count."""
        ...

    @abstractmethod
    def kill_all(self) -> int:
        """Delete all sessions (admin + client). Returns count."""
        ...
