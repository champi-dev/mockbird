"""Django settings for Mockbird.

This module is plain Python that Django imports once at startup; every
UPPERCASE name defined here becomes a "setting". Anywhere else in the
code you can read them via `from django.conf import settings`. The
pattern used throughout: read an environment variable, fall back to a
sensible development default — so the same file works on a laptop
(no env vars set) and in production (everything set via env).
"""

import os
from datetime import timedelta
from pathlib import Path

# Third-party helper that parses a single DATABASE_URL string
# (e.g. "postgres://user:pass@host:5432/db") into Django's DATABASES
# dict format — much nicer than 6 separate env vars.
import dj_database_url

# __file__ is this file's path; .parent.parent climbs from
# backend/config/settings.py up to backend/ — the project root that
# other paths (db file, static dir) are built from.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load simple KEY=value pairs from backend/.env if present (dev
# convenience; real deployments set env vars directly).
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        # Skip blanks and "# comment" lines; require an "=" to parse.
        if _line and not _line.startswith("#") and "=" in _line:
            # str.partition("=") splits on the FIRST "=" only, so
            # values containing "=" (like URLs) survive intact.
            _k, _, _v = _line.partition("=")
            # setdefault: a variable already set in the real
            # environment wins over the .env file.
            os.environ.setdefault(_k.strip(), _v.strip())

# Used to sign session cookies, password-reset tokens, etc. Anyone who
# knows it can forge those, hence "set a real one in production".
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-key-change-in-production",
)

# DEBUG=True shows detailed error pages with source code and settings
# — invaluable in dev, a security hole in prod. Env vars are always
# strings, so "true"/"false" text is compared, not a boolean.
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

# Django refuses requests whose Host header isn't in this list
# (protects against Host-header attacks). "*" = allow anything (dev).
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# Every Django "app" (a self-contained module with models/views) must
# be listed here or Django won't see its models, templates, etc.
INSTALLED_APPS = [
    "django.contrib.admin",         # the /admin/ auto-generated UI
    "django.contrib.auth",          # User model, password hashing
    "django.contrib.contenttypes",  # bookkeeping auth depends on
    "django.contrib.sessions",      # session cookies (used by admin)
    "django.contrib.messages",      # flash messages (used by admin)
    "django.contrib.staticfiles",   # collects/serves CSS/JS for admin
    "rest_framework",               # Django REST Framework (DRF)
    "corsheaders",                  # adds CORS headers for the SPA
    "mocks",                        # OUR app: everything Mockbird
]

# Middleware = a stack of functions every request passes through on
# the way in and every response on the way out, in this order (top to
# bottom for requests, bottom to top for responses).
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CORS middleware must sit early so its headers are added even to
    # error responses; it answers the browser's OPTIONS "preflight".
    # Mock endpoints (/m/, /api/docs/) are meant to be consumed from
    # ANY origin — MockCorsMiddleware opens them fully; corsheaders
    # keeps the dashboard API restricted to the app's own origins.
    "mocks.middleware.MockCorsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CSRF protects cookie-authenticated form posts. Our API uses JWT
    # headers (not cookies) so DRF views are exempt; the mock server
    # opts out explicitly with @csrf_exempt.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# The module holding the root url patterns (config/urls.py).
ROOT_URLCONF = "config.urls"

# Template engine config — only the admin uses templates here (the
# real UI is the separate Vue SPA), so this is stock boilerplate.
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

# Dotted path to the WSGI app object gunicorn serves in production.
WSGI_APPLICATION = "config.wsgi.application"

# One DATABASE_URL env var decides the database. No var set -> a
# local SQLite file (zero setup); in prod -> Postgres.
# conn_max_age=600 keeps DB connections open for 10 min instead of
# reconnecting per request (a meaningful speedup with Postgres).
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# Rules applied when users pick a password (min length, not in the
# common-passwords list). Enforced by User.objects.create_user paths
# that call validate_password — and by the admin.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# Internationalization/time defaults. USE_TZ=True stores datetimes in
# UTC in the DB (always do this; convert for display only).
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Where static files are served from (URL prefix) and collected to
# (`manage.py collectstatic` copies admin CSS/JS into STATIC_ROOT).
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# New models get a 64-bit auto-increment primary key by default.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Global DRF behavior. Individual views can override any of these.
REST_FRAMEWORK = {
    # How requests prove who they are: a JWT in the
    # "Authorization: Bearer <token>" header, validated by simplejwt.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Deny-by-default: every API view requires a logged-in user
    # unless it explicitly sets AllowAny (register, public docs).
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # Named throttle buckets. A view opts in by declaring
    # `throttle_scope = "ai"`; DRF then rate-limits per user.
    "DEFAULT_THROTTLE_RATES": {
        "ai": os.environ.get("AI_THROTTLE_RATE", "6/min"),
    },
}

# AI endpoint generation — any OpenAI-compatible chat completions API.
# Defaults target a local Ollama; point AI_BASE_URL at api.openai.com/v1
# and set AI_API_KEY (or OPENAI_API_KEY) to use OpenAI instead.
AI_BASE_URL = os.environ.get("AI_BASE_URL", "http://localhost:11434/v1")
AI_MODEL = os.environ.get("AI_MODEL", "qwen3:1.7b")
# Two names accepted for the key: AI_API_KEY wins, OPENAI_API_KEY is
# honored for people following OpenAI docs.
AI_API_KEY = os.environ.get("AI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
# Server-wide cap on simultaneous AI generations (protects the local GPU)
AI_MAX_CONCURRENT = int(os.environ.get("AI_MAX_CONCURRENT", "3"))

# JWT lifetimes: the short-lived `access` token authenticates each
# request; when it expires the SPA trades the longer-lived `refresh`
# token for a new one (see frontend/src/api/client.js interceptor).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# CORS = the browser rule that JS on origin A may not read responses
# from origin B unless B's headers allow it. In dev the SPA (:5173)
# and API (:8000) are different origins, so allow everything under
# DEBUG. In prod nginx serves both from ONE origin, so this list is
# usually empty and CORS never even comes into play.
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o
]
