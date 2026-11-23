from core.validators import Field, RequestBody
from necore.query.patterns import PATTERN_CONTENT


class AdminLoginBody(RequestBody):
    username = Field(str, required=True, min_length=3, max_length=150, pattern=PATTERN_CONTENT)
    password = Field(str, required=True, min_length=8, max_length=64, pattern=PATTERN_CONTENT)


class AdminVerifyTwoFactorBody(RequestBody):
    challenge_id = Field(str, required=True, min_length=16, max_length=128, pattern=PATTERN_CONTENT)
    otp_code = Field(str, required=True, min_length=6, max_length=6, pattern=r'^\d{6}$')
    remember_device = Field(bool, required=False, default=False)


class AdminResendTwoFactorBody(RequestBody):
    challenge_id = Field(str, required=True, min_length=16, max_length=128, pattern=PATTERN_CONTENT)


class AdminChangePasswordBody(RequestBody):
    username = Field(str, required=True, min_length=3, max_length=150, pattern=PATTERN_CONTENT)
    current_password = Field(str, required=True, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
    new_password = Field(str, required=True, min_length=8, max_length=64, pattern=PATTERN_CONTENT)
