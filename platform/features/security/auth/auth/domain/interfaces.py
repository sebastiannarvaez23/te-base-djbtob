from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class IAdminAuthRepository(ABC):

    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[object]:
        """Returns the AdminUser ORM instance if credentials are valid, else None."""
        ...

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[object]:
        """Active admin user by username, or None."""
        ...

    @abstractmethod
    def touch_last_login(self, user: object) -> None:
        """Stamp last_login after a completed sign-in that issues a session."""
        ...


class IAdminSessionRepository(ABC):

    @abstractmethod
    def build_menu(
        self,
        role: object,
        *,
        is_superuser: bool = False,
    ) -> Tuple[list, List[str]]:
        """Return (menu_items, feature_keys) for the admin role.

        Superusers receive every active module and feature (no subscription layer).
        """
        ...


class IAdminLoginRetryStore(ABC):

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


class IAdminTrustedDeviceRepository(ABC):

    @abstractmethod
    def find_active(self, user, device_hash: str, *, cutoff):
        """Return a non-revoked trusted device used after *cutoff*, or None."""
        ...

    @abstractmethod
    def touch(self, device, *, ip: str = '', user_agent: str = '') -> None:
        ...

    @abstractmethod
    def register(
        self, user, device_hash: str, *, ip: str = '', user_agent: str = '',
        max_devices: int = 10,
    ) -> None:
        ...


class IAdminUserLookup(ABC):

    @abstractmethod
    def get_active_by_id(self, user_id, *, with_role: bool = False):
        """Active admin user by id, or None."""
        ...
