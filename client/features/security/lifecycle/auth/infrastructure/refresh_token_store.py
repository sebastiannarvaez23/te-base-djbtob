"""IClientRefreshStore adapter over the shared Redis refresh-token service."""

from __future__ import annotations

from typing import Optional

from core.auth import refresh_service


class RedisClientRefreshStore:
    USER_TYPE = 'client'

    def list_for_user(self, user_id) -> list[dict]:
        return refresh_service.list_for_user(user_id, self.USER_TYPE)

    def validate(self, raw_token: str) -> Optional[dict]:
        return refresh_service.validate(raw_token, expected_type=self.USER_TYPE)

    def generate_raw_token(self) -> str:
        return refresh_service.generate_raw_token()

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
    ) -> tuple[str, str]:
        return refresh_service.store(
            raw_token=raw_token,
            user_id=user_id,
            user_type=self.USER_TYPE,
            schema_name=schema_name,
            ip_address=ip_address,
            user_agent=user_agent,
            ttl_seconds=ttl_seconds,
            remember_me=remember_me,
        )

    def revoke(self, raw_token: str) -> bool:
        return refresh_service.revoke(raw_token, user_type=self.USER_TYPE)

    def revoke_all_for_user(self, user_id) -> int:
        return refresh_service.revoke_all_for_user(user_id, user_type=self.USER_TYPE)

    def revoke_session(self, user_id, session_id: str) -> bool:
        return refresh_service.revoke_by_session_key(
            f'rt:{self.USER_TYPE}:{user_id}:{session_id}',
        )
