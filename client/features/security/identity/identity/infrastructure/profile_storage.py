"""Bootstrap MinIO bucket, public-read policy and default profile avatar."""
import logging
from pathlib import Path

from core.storage.domain.schemas import UploadFileSchema
from core.storage.infrastructure.minio_storage import MinioStorageService
from core.storage.profile_bucket import PROFILE_BUCKET, ensure_profile_bucket

from ..domain.profile_picture import (
    DEFAULT_AVATAR_PUBLIC_PATTERN,
    DEFAULT_PROFILE_AVATAR_KEY,
    PROFILE_PUBLIC_PATTERN,
)

_logger = logging.getLogger('app.api')

_ASSET_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'profile'
_DEFAULT_AVATAR_FILE = _ASSET_DIR / 'avatar.png'

PUBLIC_READ_PATTERNS = [
    PROFILE_PUBLIC_PATTERN,
    DEFAULT_AVATAR_PUBLIC_PATTERN,
    DEFAULT_PROFILE_AVATAR_KEY,
]


def ensure_profile_storage(storage=None) -> None:
    """Ensure bucket policy, public paths and default avatar object exist."""
    storage = storage or MinioStorageService()

    ensure_profile_bucket(storage)

    if not storage.file_exists(PROFILE_BUCKET, DEFAULT_PROFILE_AVATAR_KEY):
        _upload_default_avatar(storage)


def _upload_default_avatar(storage) -> None:
    if not _DEFAULT_AVATAR_FILE.is_file():
        _logger.error('Default avatar asset missing at %s', _DEFAULT_AVATAR_FILE)
        return

    storage.upload_file(UploadFileSchema(
        bucket=PROFILE_BUCKET,
        object_name=DEFAULT_PROFILE_AVATAR_KEY,
        data=_DEFAULT_AVATAR_FILE.read_bytes(),
        content_type='image/png',
        metadata={'purpose': 'default-profile-avatar'},
    ))
    _logger.info(
        'Uploaded default profile avatar to %s/%s',
        PROFILE_BUCKET,
        DEFAULT_PROFILE_AVATAR_KEY,
    )
