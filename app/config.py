from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(_env("VOICE_DATA_DIR", str(BASE_DIR / "data")))
STATIC_DIR = Path(_env("VOICE_STATIC_DIR", str(BASE_DIR / "static")))
ACCOUNTS_FILE = Path(_env("VOICE_ACCOUNTS_FILE", str(DATA_DIR / "accounts.json")))

AUTH_KEY = _env("VOICE_AUTH_KEY", "change-me")
HTTP_PROXY = _env("VOICE_HTTP_PROXY") or _env("HTTPS_PROXY") or _env("HTTP_PROXY")
IMPERSONATE = _env("VOICE_IMPERSONATE", "chrome136")
SKIP_SSL_VERIFY = _env_bool("VOICE_SKIP_SSL_VERIFY", True)
SESSION_TTL_SECONDS = int(_env("VOICE_SESSION_TTL_SECONDS", str(6 * 60 * 60)))
MAX_ACCOUNT_ATTEMPTS = max(1, int(_env("VOICE_MAX_ACCOUNT_ATTEMPTS", "4")))

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"
)
CLIENT_VERSION = _env("VOICE_CLIENT_VERSION", "prod-fb4a8a2a751dfec391053cfd7b01c52699ccf78c")
CLIENT_BUILD_NUMBER = _env("VOICE_CLIENT_BUILD_NUMBER", "8370486")
