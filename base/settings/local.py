import os

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = ['.base.local', '.localhost', 'localhost', '127.0.0.1']

# CORS is configured in base.py (shared-root-domain block).
# Only add local-only overrides here if needed.
CSRF_TRUSTED_ORIGINS = [
    'http://base.local:4100',
    'http://app.base.local:4110',
    'http://app.base.local:8100',
    'http://admin.base.local:4120',
    'http://docs.base.local:4130',
    'http://lib.base.local:4140',
    'http://prosandbox.base.local:4141',
    'http://localhost:4100',
    'http://localhost:4110',
    'http://localhost:4120',
    'http://localhost:4130',
    'http://localhost:4140',
    'http://localhost:4141',
]

from .databases import build_analytics_database, build_default_database

DATABASES = {
    'default': build_default_database(env),
    'analytics': build_analytics_database(env),
}

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Local Neurana product app (see base/settings/.env.ex). Production sets this in env.
if not NE_PRODUCT_CLIENT_ID:
    NE_PRODUCT_CLIENT_ID = 'base_dev'
