from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from app.config import ACCOUNTS_FILE


class AccountError(Exception):
    pass


class AccountPool:
    """Minimal JSON account pool for web access tokens."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or ACCOUNTS_FILE)
        self._lock = threading.RLock()
        self._accounts: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._accounts = []
                return
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                items = data.get("accounts") or data.get("items") or []
            else:
                items = data
            if not isinstance(items, list):
                raise AccountError("accounts.json must be a list or {accounts:[...]}")
            cleaned: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                token = str(item.get("access_token") or item.get("token") or "").strip()
                if not token:
                    continue
                cleaned.append({
                    "email": str(item.get("email") or ""),
                    "access_token": token,
                    "refresh_token": str(item.get("refresh_token") or ""),
                    "device_id": str(item.get("device_id") or item.get("oai-device-id") or ""),
                    "proxy": str(item.get("proxy") or ""),
                    "status": str(item.get("status") or "正常"),
                    "disabled": bool(item.get("disabled") or item.get("status") == "禁用"),
                })
            self._accounts = cleaned

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(x) for x in self._accounts]

    def pick(
        self,
        preferred_token: str = "",
        *,
        excluded_tokens: set[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        preferred = str(preferred_token or "").strip()
        excluded = set(excluded_tokens or set())
        with self._lock:
            if preferred:
                if preferred in excluded:
                    raise AccountError("preferred account already failed in this request")
                for acc in self._accounts:
                    if acc["access_token"] == preferred and not acc.get("disabled"):
                        return preferred, dict(acc)
                # allow raw token not present in pool
                return preferred, {"access_token": preferred, "email": "", "device_id": "", "proxy": ""}

            for acc in self._accounts:
                token = acc["access_token"]
                if token in excluded or acc.get("disabled"):
                    continue
                if str(acc.get("status") or "") == "禁用":
                    continue
                return token, dict(acc)
        raise AccountError("no available web access_token in accounts.json")

    def mark_invalid(self, token: str) -> None:
        token = str(token or "").strip()
        if not token:
            return
        with self._lock:
            changed = False
            for acc in self._accounts:
                if acc["access_token"] == token:
                    acc["disabled"] = True
                    acc["status"] = "禁用"
                    acc["invalid_at"] = time.time()
                    changed = True
            if changed:
                self._save_unlocked()

    def _save_unlocked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"accounts": self._accounts}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


account_pool = AccountPool()
