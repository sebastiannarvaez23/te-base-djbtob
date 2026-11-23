from typing import Optional
from uuid import UUID

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.identity.sessions.domain.interfaces import ISessionRepository
from core.trace import trace_layer


class ListSessionsPaginatedUseCase:
    def __init__(self, repository: ISessionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_paginated(query)


class KillSessionUseCase:
    def __init__(self, repository: ISessionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, session_id: str) -> bool:
        return self.repository.kill_session(session_id)


class KillSessionsByUserUseCase:
    def __init__(self, repository: ISessionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: UUID) -> int:
        return self.repository.kill_by_user(user_id)


class KillSessionsByCompanyUseCase:
    def __init__(self, repository: ISessionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: UUID) -> int:
        return self.repository.kill_by_company(company_id)


class KillAllSessionsUseCase:
    def __init__(self, repository: ISessionRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self) -> int:
        return self.repository.kill_all()
