from __future__ import annotations

from typing import Any

from curl_cffi import requests

from app.config import HTTP_PROXY, IMPERSONATE, SKIP_SSL_VERIFY


def build_session(*, proxy: str = "", impersonate: str | None = None) -> requests.Session:
    proxy_url = str(proxy or HTTP_PROXY or "").strip()
    kwargs: dict[str, Any] = {
        "impersonate": impersonate or IMPERSONATE,
        "verify": not SKIP_SSL_VERIFY,
        "timeout": 60,
    }
    if proxy_url:
        kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}
    return requests.Session(**kwargs)
