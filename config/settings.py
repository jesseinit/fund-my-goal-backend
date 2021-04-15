"""
Django settings for config project.
Generated by 'django-admin startproject' using Django 2.2.6.
For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/
For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
import sentry_sdk
import os
from dotenv import load_dotenv
import datetime

load_dotenv()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG") == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')
APPEND_SLASH = False


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django.contrib.humanize',
    'userservice.apps.UserserviceConfig',
    'goalservice.apps.GoalserviceConfig',
    'walletservice.apps.WalletserviceConfig',
    'django_filters',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'utils.middleware.LoggingMiddleware'
]

DEFAULT_RENDERER_CLASSES = (
    'rest_framework.renderers.JSONRenderer',
)

if DEBUG:
    DEFAULT_RENDERER_CLASSES = DEFAULT_RENDERER_CLASSES + (
        'rest_framework.renderers.BrowsableAPIRenderer',
    )

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'userservice.authentication.JSONWebTokenAuthentication',
    ),
    'DEFAULT_RENDERER_CLASSES': DEFAULT_RENDERER_CLASSES,
    'DEFAULT_PERMISSION_CLASSES': (
        'userservice.permissions.IsTokenBlackListed',
    ),
    'DATETIME_FORMAT': "%Y-%m-%dT%H:%M:%S.%fZ",
    'DATETIME_INPUT_FORMATS': ['%Y-%m-%d %H:%M:%S', ]
}

JWT_SETTINGS = {
    'ISS_AT': lambda: datetime.datetime.utcnow(),
    'EXP_AT': lambda: datetime.datetime.utcnow() + datetime.timedelta(days=2)
}

ROOT_URLCONF = 'config.urls'
# TEMPT_DIR = os.path.join(BASE_DIR, 'userservice/templates/')
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('DB_NAME', 'userdb'),
        'USER': os.environ.get('DB_USERNAME', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', 5432),
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'userservice.User'
CORS_ORIGIN_ALLOW_ALL = True


FRONTEND_URL = os.environ.get(
    'FRONTEND_URL', 'https://neon.mytudo.com')

PASSWORD_RESET_TIMEOUT_DAYS = 1

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

DATA_UPLOAD_MAX_MEMORY_SIZE = 31000000  # 30mb

# Sendgrid Settings
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# Redis setting
REDIS_CONNECTION_URL = os.getenv("REDIS_CONNECTION_URL")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_CONNECTION_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# App Id
MOBILE_APP_ID = os.getenv("MOBILE_APP_ID")

# Celery Setting
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_URL = CELERY_RESULT_BACKEND = REDIS_CONNECTION_URL

# SMS Gateway Setting
SMS_GATEWAY_TOKEN = os.getenv("SMS_GATEWAY_TOKEN")
SMS_GATEWAY_USERNAME = os.getenv("SMS_GATEWAY_USERNAME")
SMS_GATEWAY_SENDER_ID = os.getenv("SMS_GATEWAY_SENDER_ID")

ENV = os.getenv('ENV', 'local')

# Core Banking API
VFD_WALLET = os.getenv('VFD_WALLET')
VFD_URL = os.getenv('VFD_URL')
VFD_ACCESS_TOKEN = os.getenv('VFD_ACCESS_TOKEN')
VFD_BANK_CODE_PREFIX = os.getenv('VFD_BANK_CODE_PREFIX')
VFD_DEV_TO_ACCOUNT = os.getenv('VFD_DEV_TO_ACCOUNT')
VFD_XERDE_POOL_ACCOUNT_BVN = os.getenv('VFD_XERDE_POOL_ACCOUNT_BVN')
VFD_DEV_BANK_CODE = os.getenv('VFD_DEV_BANK_CODE')

# FlutterWave
FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY')
FLUTTERWAVE_PUBLIC_KEY = os.getenv('FLUTTERWAVE_PUBLIC_KEY')
FLUTTERWAVE_HASH = os.getenv('FLUTTERWAVE_HASH')

# Recipient Email address
DEFAULT_FROM_EMAIL = f'Fund My Goals App <{os.getenv("DEFAULT_FROM_EMAIL")}>'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = '/static/'


if ENV.lower() in ['production', 'staging', 'test', 'local']:
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[DjangoIntegration(), CeleryIntegration(),
                      RedisIntegration()],
        environment=ENV,
    )

# AWS KEYS
SPACE_ACCESS_KEY_ID = os.getenv('SPACE_ACCESS_KEY_ID')
SPACE_SECRET_ACCESS_KEY = os.getenv('SPACE_SECRET_ACCESS_KEY')
SPACE_STORAGE_BUCKET_NAME = os.getenv('SPACE_STORAGE_BUCKET_NAME')
SPACE_REGION = os.getenv('SPACE_REGION')
SPACE_ENDPOINT = os.getenv('SPACE_ENDPOINT')

# LOGGING
# LOGGING = {
#     'version': 1,
#     'filters': {
#         'require_debug_true': {
#             '()': 'django.utils.log.RequireDebugTrue',
#         }
#     },
#     'handlers': {
#         'console': {
#             'level': 'DEBUG',
#             'filters': ['require_debug_true'],
#             'class': 'logging.StreamHandler',
#         },
#         'file': {
#             'level': 'DEBUG',
#             'class': 'logging.FileHandler',
#             'filename': 'sql.log',
#         },
#     },
#     'loggers': {
#         'django.db.backends': {
#             'level': 'DEBUG',
#             'handlers': ['file'],
#         },
#         'django.request': {
#             'level': 'DEBUG',
#             'handlers': ['console'],
#         }
#     }
# }