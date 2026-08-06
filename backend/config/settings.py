"""Django settings for PharmaCore (by Medlink).

12-factor: configuration comes from environment variables. Business rules
(statutory rates, insurance schemes, tax classes) live in the database, not here.
See docs/development/environments-and-config.md.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core ---
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-me-in-production")
MEDLINK_ENV = os.environ.get("MEDLINK_ENV", "dev")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
VERSION = "0.0.0"

ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "*").split(",") if h]

# --- Applications ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    # Local apps
    "apps.iam",
    "apps.catalog",
    "apps.inventory",
    "apps.distribution",
    "apps.documents",
    "apps.retail",
    "apps.workspace",
    "apps.approvals",
    "apps.finance",
    "apps.hr",
    "apps.core",
]

# --- Media (generated document vault) ---
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DOCUMENT_VERIFY_BASE_URL = os.environ.get(
    "DOCUMENT_VERIFY_BASE_URL", "https://pharmacore.local/verify"
)

AUTH_USER_MODEL = "iam.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --- Security hardening (see docs/08). Baseline always on; strict flags in prod. ---
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Behind a TLS-terminating reverse proxy (Caddy/Nginx).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database ---
# SQLite default keeps the app bootable with no services; staging/production
# override DATABASE_URL with PostgreSQL.
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'pharmacore_dev.sqlite3'}"),
        conn_max_age=600,
    )
}

# --- Password hashing (argon2 first, per security design) ---
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# Allow sign-in by username OR PF/staff number; keep the default backend as fallback.
AUTHENTICATION_BACKENDS = [
    "apps.iam.backends.PFOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# --- i18n / tz (English-only UI per ADR-004; Rwanda locale conventions) ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Kigali"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Token-version aware JWT for interactive users (so an admin can force-logout
        # a user), then service-account API keys for machine access.
        "apps.iam.authentication.VersionedJWTAuthentication",
        "apps.iam.authentication.ApiKeyAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Rate limiting (foundational — see docs/08 §5). Scoped throttles tighten
    # sensitive endpoints (e.g. login) as they are added.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "1000/min"},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "PharmaCore API",
    "DESCRIPTION": "PharmaCore — pharmaceutical ERP for Rwanda, by Medlink.",
    "VERSION": VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- JWT (djangorestframework-simplejwt) ---
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_TTL_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_TTL_DAYS", "14"))),
}

# --- CORS (React SPA) ---
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o
]
# In development the Vite port can vary (5173/5174/…); allow any local origin.
# Production (DEBUG=False) still uses the explicit allow-list above.
CORS_ALLOW_ALL_ORIGINS = DEBUG
