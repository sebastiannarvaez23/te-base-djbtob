from abc import ABC, abstractmethod
from typing import Optional, Tuple

from client.features.security.lifecycle.auth.domain.schemas import (
    AuthenticatedClient,
    MenuItemSchema,
    PreferencesSchema,
    SubscriptionInfoSchema,
)


class IAuthRepository(ABC):

    @abstractmethod
    def authenticate(self, username: str, password: str) -> AuthenticatedClient:
        """Authenticate user. Raises AuthException on failure."""
        ...

    @abstractmethod
    def touch_last_login(self, user: object) -> None:
        """Stamp last_login after a completed sign-in that issues a session."""
        ...


class ISessionRepository(ABC):

    @abstractmethod
    def get_company_domain(self, company: object) -> Optional[str]:
        """Returns the domain string for the given company ORM instance."""
        ...

    @abstractmethod
    def get_or_create_preferences(self, user: object) -> PreferencesSchema:
        """Returns user preferences, creating defaults if they don't exist."""
        ...

    @abstractmethod
    def get_active_subscription(self, company: object) -> Optional[SubscriptionInfoSchema]:
        """Returns the active or recently-cancelled (still valid) subscription for the company."""
        ...

    @abstractmethod
    def build_menu(
        self,
        rol: object,
        subscription_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> Tuple[list[MenuItemSchema], list[str]]:
        """Returns (menu_items, feature_keys) based on the role's features
        intersected with the plan plus the company's active complements."""
        ...

    @abstractmethod
    def build_billing_recovery_menu(self, rol: object) -> Tuple[list[MenuItemSchema], list[str]]:
        """Menú y features mínimos para regularizar facturación sin plan activo."""
        ...


class ILoginRetryStore(ABC):
    """Consecutive failed-password counter (schema-scoped)."""

    @abstractmethod
    def incr_failures(self, username: str, ttl_seconds: int) -> int:
        ...

    @abstractmethod
    def get_failures(self, username: str) -> int:
        ...

    @abstractmethod
    def refresh_ttl(self, username: str, count: int, ttl_seconds: int) -> None:
        ...

    @abstractmethod
    def clear_failures(self, username: str) -> None:
        ...

    @abstractmethod
    def ttl_remaining(self, username: str) -> int | None:
        ...


class IClientRefreshStore(ABC):
    """Live client refresh-token sessions."""

    @abstractmethod
    def list_for_user(self, user_id) -> list[dict]:
        ...

    @abstractmethod
    def validate(self, raw_token: str) -> Optional[dict]:
        ...

    @abstractmethod
    def generate_raw_token(self) -> str:
        ...

    @abstractmethod
    def store(
        self,
        raw_token: str,
        user_id,
        schema_name: str,
        ip_address: str,
        user_agent: str,
        *,
        ttl_seconds: int | None = None,
        remember_me: bool = False,
    ) -> Tuple[str, str]:
        """Persist a refresh token. Returns (raw_token, session_id)."""
        ...

    @abstractmethod
    def revoke(self, raw_token: str) -> bool:
        ...

    @abstractmethod
    def revoke_all_for_user(self, user_id) -> int:
        ...

    @abstractmethod
    def revoke_session(self, user_id, session_id: str) -> bool:
        ...
