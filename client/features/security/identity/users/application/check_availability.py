from client.features.security.lifecycle.registration.models import User
from core.trace import trace_layer


class CheckUsernameAvailabilityUseCase:
    """Probe whether a username is still free within the tenant."""

    @trace_layer('application')
    def execute(self, username: str) -> bool:
        normalized = username.strip().lower()
        if not normalized:
            return False
        return not User.objects.filter(username__iexact=normalized).exists()


class CheckEmailAvailabilityUseCase:
    """Probe whether an email is still free within the tenant."""

    @trace_layer('application')
    def execute(self, email: str) -> bool:
        normalized = email.strip().lower()
        if not normalized:
            return False
        return not User.objects.filter(email__iexact=normalized).exists()
