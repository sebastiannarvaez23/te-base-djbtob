from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT


class LoginBody(RequestBody):
    username = Field(str,  required=True,  min_length=3,  max_length=200, pattern=PATTERN_CONTENT)
    password = Field(str,  required=True,  min_length=8, max_length=64, pattern=PATTERN_CONTENT)
    remember_me = Field(bool, required=False, default=False)


class VerifyTwoFactorBody(RequestBody):
    challenge_id = Field(str, required=True, min_length=20, max_length=128, pattern=PATTERN_CONTENT)
    otp_code = Field(str, required=True, min_length=6, max_length=6, pattern=r'^\d{6}$')
    remember_device = Field(bool, required=False, default=False)


class ResendTwoFactorBody(RequestBody):
    challenge_id = Field(str, required=True, min_length=20, max_length=128, pattern=PATTERN_CONTENT)


class ConfirmEmailBody(RequestBody):
    token = Field(str, required=True, min_length=20, max_length=128, pattern=PATTERN_CONTENT)


class ResendConfirmationBody(RequestBody):
    # Accept either to support resend from the unauthenticated post-login error path
    # and from a separate resend form. Exactly one must be present (validated in view).
    email    = Field(str, required=False, is_email=True, max_length=254)
    username = Field(str, required=False, min_length=3, max_length=200, pattern=PATTERN_CONTENT)


class PasswordResetRequestBody(RequestBody):
    email = Field(str, required=True, is_email=True, max_length=254)


class PasswordResetValidateBody(RequestBody):
    token = Field(str, required=True, min_length=20, max_length=128, pattern=PATTERN_CONTENT)


class PasswordResetConfirmBody(RequestBody):
    token    = Field(str, required=True, min_length=20, max_length=128, pattern=PATTERN_CONTENT)
    password = Field(str, required=True, min_length=8, max_length=64, pattern=PATTERN_CONTENT)


class ChangePasswordBody(RequestBody):
    username = Field(str, required=True, min_length=3, max_length=200, pattern=PATTERN_CONTENT)
    current_password = Field(str, required=True, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
    new_password = Field(str, required=True, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
