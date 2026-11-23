from typing import List, NamedTuple, Optional

from pydantic import BaseModel, Field


class AdminLoginInputSchema(BaseModel):
    username: str
    password: str


class AdminLoginOutputSchema(BaseModel):
    access_token: str


class AdminMenuItemSchema(BaseModel):
    id: str
    code: str
    name: str
    icon: str
    route: str
    section: str
    section_name: str = ''


class AdminSessionSchema(BaseModel):
    menu: List[AdminMenuItemSchema] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    # TIME_INACTIVITY (admin catalog) in minutes. 0 = SPA must not arm idle timer.
    inactivity_minutes: int = 0


class AdminTwoFactorChallengeSchema(BaseModel):
    two_factor_required: bool = True
    challenge_id: str
    expires_in: int
    email_hint: str


class AdminVerifiedTwoFactor(NamedTuple):
    user: object


class IssuedAdminSession(NamedTuple):
    """Tokens minted after a completed admin sign-in (password or 2FA)."""

    user: object
    access_token: str
    refresh_token: str
    session_id: str
