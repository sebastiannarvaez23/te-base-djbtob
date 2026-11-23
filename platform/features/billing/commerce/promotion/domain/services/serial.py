"""Pure voucher-serial generation (no Django)."""

import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits
_DEFAULT_PREFIX = 'WLGX'


def generate_voucher_serial(voucher_type: str, *, prefix: str = _DEFAULT_PREFIX) -> str:
    type_code = 'GFT' if voucher_type == 'GIFT' else 'DSC'
    suffix = ''.join(secrets.choice(_ALPHABET) for _ in range(8))
    return f'{prefix}-{type_code}-{suffix}'
