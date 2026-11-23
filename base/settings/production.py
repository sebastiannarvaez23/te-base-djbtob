import os

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

from .databases import build_analytics_database, build_default_database

DATABASES = {
    'default': build_default_database(env),
    'analytics': build_analytics_database(env),
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

TRUST_X_FORWARDED_FOR = env.bool('TRUST_X_FORWARDED_FOR', default=True)
TRUST_GEO_HEADERS = env.bool('TRUST_GEO_HEADERS', default=True)