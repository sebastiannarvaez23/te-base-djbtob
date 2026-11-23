from core.auth.inactivity import inactivity_minutes
from core.trace import trace_layer
from platform.features.security.auth.auth.domain.interfaces import IAdminAuthRepository, IAdminSessionRepository
from platform.features.security.auth.auth.domain.schemas import AdminSessionSchema


class AdminLoginUseCase:
    def __init__(self, repository: IAdminAuthRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, username: str, password: str):
        return self.repository.authenticate(username, password)


class BuildAdminSessionUseCase:
    def __init__(self, session_repository: IAdminSessionRepository):
        self.session_repository = session_repository

    @trace_layer('application')
    def execute(self, user) -> AdminSessionSchema:
        menu, features = self.session_repository.build_menu(
            user.role if user.role_id else None,
            is_superuser=bool(user.is_superuser),
        )
        return AdminSessionSchema(
            menu=menu,
            features=features,
            inactivity_minutes=inactivity_minutes(user_type='admin'),
        )
