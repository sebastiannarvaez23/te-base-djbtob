"""
Typed context schemas for each email template.

Each schema maps 1-to-1 with a template code and defines exactly
which variables that template expects. This ensures type safety at
the caller site and makes it trivial to discover what data a
template needs.

Adding a new template?
  1. Create a new BaseModel here with the template's variables.
  2. Create a dispatcher function in dispatchers.py.
"""

from pydantic import BaseModel


class WelcomeAdminContext(BaseModel):
    """Context for WELCOME_ADMIN template."""
    user_name: str
    user_email: str
    username: str
    company_name: str
    subscription_name: str
    subscription_code: str
    price: float
    start_date: str
    end_date: str
    modules_list: str
    platform_url: str
    support_email: str
    current_year: int


class WelcomeUserContext(BaseModel):
    """Context for WELCOME_USER template — invited company collaborator."""
    user_name: str
    user_email: str
    company_name: str
    current_year: int
    support_email: str
    activation_url: str
    expiration_time: int  # minutes


class EmailConfirmContext(BaseModel):
    """Context for EMAIL_CONFIRM template."""
    user_name: str
    confirmation_url: str
    expiration_time: int
    support_email: str
    current_year: int


class OnboardingResumeContext(BaseModel):
    """Context for ONBOARDING_RESUME template — magic-link to continue registration."""
    resume_url: str
    expires_in_days: int
    support_email: str
    current_year: int


class RescueCredentialsContext(BaseModel):
    """Context for RESCUE_CREDENTIALS template — password-reset magic-link."""
    user_name: str
    user_email: str
    reset_password_url: str
    expiration_time: int  # minutes
    support_email: str
    current_year: int


class TwoFactorAuthContext(BaseModel):
    """Context for 2FA_AUTH template — email OTP on a new device."""
    login_ip: str
    otp_code: str
    user_name: str
    login_time: str
    current_year: int
    login_device: str
    support_email: str
    login_location: str
    expiration_time: int  # minutes


class CompanyDeregistrationContext(BaseModel):
    """Context for COMPANY_DEREGISTRATION — tenant closed by platform admin."""
    user_name: str
    company_name: str
    current_year: int
    support_email: str
    company_document: str
    deactivation_date: str
    deactivation_reason: str
