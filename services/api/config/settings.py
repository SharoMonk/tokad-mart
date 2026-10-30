from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY == "dev-only-change-me"):
    raise RuntimeError("Set a strong, unique DJANGO_SECRET_KEY (50+ characters) in production")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "").split(",") if h.strip()]
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise RuntimeError("Explicit DJANGO_ALLOWED_HOSTS values are required in production")


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
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Set the forwarded header only behind an ingress that strips untrusted client headers.
if not DEBUG and os.getenv("DJANGO_TRUST_PROXY_SSL_HEADER", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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

# Production login throttle uses shared Redis with atomic Lua operations.
POS_LOGIN_REDIS_URL = os.getenv('POS_LOGIN_REDIS_URL', '')

POS_LOGIN_MAX_IP_ATTEMPTS = int(os.getenv('POS_LOGIN_MAX_IP_ATTEMPTS', '50'))

# Reports are strictly opt-in; recipients are approved by deployment configuration.
TOKAD_REPORT_DELIVERY_ENABLED = os.getenv("TOKAD_REPORT_DELIVERY_ENABLED", "0") == "1"
TOKAD_REPORT_ALLOWED_EMAILS = os.getenv("TOKAD_REPORT_ALLOWED_EMAILS", "")
EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "1") == "1"
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = 20
