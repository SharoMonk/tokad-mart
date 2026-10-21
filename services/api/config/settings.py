from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "transactional",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "transactional.session_middleware.POSSessionIdleTimeoutMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "tokad_mart"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"

# Session cookies remain HTTP-only; HTTPS is required for non-local deployments.
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000' if DEBUG else ''
).split(',') if origin.strip()]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG

# Compatibility checkout remains enabled in development for legacy test coverage.
# Explicitly disable in production; do not bypass the shift-bound endpoint.
POS_ENABLE_LEGACY_CHECKOUT = DEBUG and os.getenv("POS_ENABLE_LEGACY_CHECKOUT", "1") == "1"
SESSION_COOKIE_AGE = int(os.getenv("POS_SESSION_AGE_SECONDS", "28800"))
SESSION_SAVE_EVERY_REQUEST = False

# POS login rate limits must be shared by all production workers.
# Provision the database cache table with: python manage.py createcachetable
CACHES = {"default": {
    "BACKEND": ("django.core.cache.backends.locmem.LocMemCache" if DEBUG
                else "django.core.cache.backends.db.DatabaseCache"),
    "LOCATION": ("tokad-pos-dev-login-throttle" if DEBUG
                 else os.getenv("POS_LOGIN_CACHE_TABLE", "pos_login_throttle_cache")),
}}
POS_LOGIN_MAX_FAILURES = int(os.getenv("POS_LOGIN_MAX_FAILURES", "5"))
POS_LOGIN_WINDOW_SECONDS = int(os.getenv("POS_LOGIN_WINDOW_SECONDS", "900"))
POS_SESSION_IDLE_SECONDS = int(os.getenv("POS_SESSION_IDLE_SECONDS", "900"))
