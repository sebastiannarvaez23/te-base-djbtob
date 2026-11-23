from typing import Literal, NamedTuple, Optional
from pydantic import BaseModel

from core.access.billing_recovery import AccessMode, LoginAccessResult
from core.validators import DateFormatValue, TimeFormatValue

__all__ = ['AccessMode', 'AuthenticatedClient', 'LoginAccessResult']


class AuthenticatedClient(NamedTuple):
    """Resultado de credenciales válidas antes de emitir sesión."""

    user: object
    access: LoginAccessResult


class LoginInputSchema(BaseModel):
    username: str
    password: str


class PreferencesSchema(BaseModel):
    language: str
    theme: str
    timezone: str
    date_format: DateFormatValue
    time_format: TimeFormatValue
    sidebar_collapsed: bool
    items_per_page: int
    notifications_enabled: bool

    model_config = {'from_attributes': True}


class SubscriptionInfoSchema(BaseModel):
    id: str
    name: str
    end_date: str
    status: str
    billing_interval: str = 'monthly'


class MenuItemSchema(BaseModel):
    id: str
    code: str
    name: str
    icon: str
    route: str
    section: str
    section_name: str = ''


class UserInfoSchema(BaseModel):
    id: str
    username: str
    first_name: str = ''
    second_name: str = ''
    rol: Optional[str]
    picture: str
    preferences: PreferencesSchema


class CompanyInfoSchema(BaseModel):
    id: str
    name: str
    nit: str
    address: str
    country: str
    state: str
    city: str
    domain: Optional[str]
    subscription: Optional[SubscriptionInfoSchema]


class SessionSchema(BaseModel):
    user: UserInfoSchema
    company: CompanyInfoSchema
    # Evaluated before menu serialization so clients/logs see the gate early.
    requires_policy_acceptance: bool = False
    policy_country: Optional[str] = None
    menu: list[MenuItemSchema]
    features: list[str]
    access_mode: AccessMode = 'full'
    subscription_status: Optional[str] = None
    # TIME_INACTIVITY in minutes. 0 means the client must not arm an idle timer.
    inactivity_minutes: int = 0


class IssuedClientSession(NamedTuple):
    """Tokens minted for a completed client sign-in (JWT is issued in presentation)."""

    session: SessionSchema
    refresh_token: str
    session_id: str
    remember_me: bool = False


class VerifiedTwoFactor(NamedTuple):
    """OTP consumed successfully; ``remember_me`` was bound at login."""

    user: object
    remember_me: bool


class TwoFactorChallengeSchema(BaseModel):
    two_factor_required: bool = True
    challenge_id: str
    expires_in: int
    email_hint: str


class TrustedDeviceSchema(BaseModel):
    id: str
    label: str
    last_ip: Optional[str] = None
    last_used_at: str
    created_at: str
    is_current: bool = False
