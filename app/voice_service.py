"""Standalone ChatGPT Web voice gateway service.

Browser owns WebRTC media.
This service only:
  - picks a web access_token
  - POSTs /realtime/wm for SDP answer
  - uploads images for DataChannel relay_message
  - binds voice_session_id -> token
"""
from __future__ import annotations

import base64
import io
import json
import threading
import time
import uuid
from typing import Any

from app.accounts import AccountError, account_pool
from app.config import (
    CLIENT_BUILD_NUMBER,
    CLIENT_VERSION,
    DEFAULT_UA,
    MAX_ACCOUNT_ATTEMPTS,
    SESSION_TTL_SECONDS,
)
from app.http_client import build_session

WM_URL = "https://chatgpt.com/realtime/wm?dcid=0"
FILES_URL = "https://chatgpt.com/backend-api/files"

ALLOWED_REALTIME_VOICES = frozenset({
    "breeze", "cove", "ember", "fathom", "glimmer", "juniper", "maple", "orbit", "vale",
})
REALTIME_VOICE_ALIASES = {
    "arbor": "fathom",
    "sol": "glimmer",
    "spruce": "orbit",
}

_VOICE_SESSION_BINDINGS: dict[str, dict[str, Any]] = {}
_VOICE_SESSION_LOCK = threading.RLock()


class VoiceServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


def _normalize_voice(voice: str) -> str:
    clean = str(voice or "").strip().lower()
    clean = REALTIME_VOICE_ALIASES.get(clean, clean)
    return clean if clean in ALLOWED_REALTIME_VOICES else "cove"


def _new_voice_session_id() -> str:
    return "vs_" + uuid.uuid4().hex


def _cleanup_voice_session_bindings_locked(now: float | None = None) -> None:
    current = time.time() if now is None else float(now)
    expired = [
        session_id
        for session_id, item in _VOICE_SESSION_BINDINGS.items()
        if current - float(item.get("updated_at") or item.get("created_at") or 0) > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        _VOICE_SESSION_BINDINGS.pop(session_id, None)


def _bind_voice_session(session_id: str, token: str, account: dict[str, Any]) -> str:
    session_id = str(session_id or "").strip() or _new_voice_session_id()
    now = time.time()
    with _VOICE_SESSION_LOCK:
        _cleanup_voice_session_bindings_locked(now)
        _VOICE_SESSION_BINDINGS[session_id] = {
            "access_token": token,
            "email": account.get("email") or "",
            "device_id": account.get("device_id") or "",
            "proxy": account.get("proxy") or "",
            "created_at": now,
            "updated_at": now,
        }
    return session_id


def release_voice_session(voice_session_id: str) -> bool:
    session_id = str(voice_session_id or "").strip()
    if not session_id:
        return False
    with _VOICE_SESSION_LOCK:
        return _VOICE_SESSION_BINDINGS.pop(session_id, None) is not None


def _bound_voice_session(voice_session_id: str) -> dict[str, Any]:
    session_id = str(voice_session_id or "").strip()
    if not session_id:
        return {}
    now = time.time()
    with _VOICE_SESSION_LOCK:
        _cleanup_voice_session_bindings_locked(now)
        item = _VOICE_SESSION_BINDINGS.get(session_id)
        if not item:
            return {}
        item["updated_at"] = now
        return dict(item)


def _encode_multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex[:16]
    chunks: list[bytes] = []
    for name, value in fields.items():
        part = (
            "--%s\r\n"
            'Content-Disposition: form-data; name="%s"\r\n'
            "\r\n"
            "%s\r\n"
        ) % (boundary, name, value)
        chunks.append(part.encode("utf-8"))
    chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(chunks), "multipart/form-data; boundary=%s" % boundary


def _normalize_sdp(offer_sdp: str) -> str:
    text = str(offer_sdp or "").strip()
    if not text.startswith("v=0"):
        raise VoiceServiceError("offer_sdp invalid; must be WebRTC offer SDP text")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    if not text.endswith("\r\n"):
        text += "\r\n"
    return text


def _build_session_json(voice: str, voice_mode: str, language_code: str = "auto") -> str:
    sid = str(uuid.uuid4()).upper()
    payload = {
        "backend_reasoning_effort": "instant",
        "language_code": language_code or "auto",
        "requested_default_model": "",
        "voice": _normalize_voice(voice),
        "voice_session_id": sid,
        "voice_status_request_id": sid,
        "timezone_offset_min": -480,
        "timezone": "Etc/GMT-8",
        "voice_mode": voice_mode or "wingman",
        "model_slug": "",
        "model_slug_advanced": "",
        "client_tools": [],
        "history_and_training_disabled": False,
        "conversation_mode": {"kind": "primary_assistant"},
        "enable_message_streaming": True,
    }
    return json.dumps(payload, separators=(",", ":"))


def _auth_headers(token: str, device_id: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "accept": "*/*",
        "origin": "https://chatgpt.com",
        "referer": "https://chatgpt.com/",
        "user-agent": DEFAULT_UA,
        "oai-device-id": device_id,
        "oai-language": "zh-CN",
        "oai-client-version": CLIENT_VERSION,
        "oai-client-build-number": CLIENT_BUILD_NUMBER,
        "authorization": "Bearer " + token,
    }
    if extra:
        headers.update(extra)
    return headers


def _post_wm_once(token: str, offer_sdp: str, session_json: str, device: str, proxy: str) -> tuple[int, str, str]:
    sess = build_session(proxy=proxy)
    try:
        body, content_type = _encode_multipart({"sdp": offer_sdp, "session": session_json})
        headers = _auth_headers(token, device, {"content-type": content_type})
        resp = sess.post(WM_URL, data=body, headers=headers, timeout=60)
        return int(resp.status_code or 0), str(resp.headers.get("content-type") or ""), (resp.text or "")
    finally:
        try:
            sess.close()
        except Exception:
            pass


def create_voice_session(
    offer_sdp: str,
    *,
    voice: str = "cove",
    voice_mode: str = "wingman",
    language_code: str = "auto",
    access_token: str = "",
    device_id: str = "",
    proxy: str = "",
    voice_session_id: str = "",
) -> dict[str, Any]:
    offer_sdp = _normalize_sdp(offer_sdp)
    voice = _normalize_voice(voice)
    bound = _bound_voice_session(voice_session_id)
    preferred = str(bound.get("access_token") or access_token or "").strip()
    session_json = _build_session_json(voice, voice_mode, language_code)
    excluded: set[str] = set()
    last_error = ""
    last_detail: Any = None
    last_status = 0

    for attempt in range(1, MAX_ACCOUNT_ATTEMPTS + 1):
        try:
            token, account = account_pool.pick(
                preferred if attempt == 1 else "",
                excluded_tokens=excluded,
            )
        except AccountError as exc:
            raise VoiceServiceError(str(exc), status_code=503) from exc

        excluded.add(token)
        device = str(device_id or account.get("device_id") or bound.get("device_id") or uuid.uuid4())
        explicit_proxy = str(proxy or account.get("proxy") or bound.get("proxy") or "").strip()
        proxy_source = "proxy" if explicit_proxy else "direct"

        try:
            status, ctype, text = _post_wm_once(token, offer_sdp, session_json, device, explicit_proxy)
        except Exception as exc:
            raise VoiceServiceError("realtime/wm network failed", status_code=502, detail=str(exc)[:300]) from exc

        if status == 401:
            last_status = status
            last_error = "account token invalid"
            last_detail = text[:300]
            account_pool.mark_invalid(token)
            if bound and token == bound.get("access_token"):
                release_voice_session(voice_session_id)
            preferred = ""
            continue

        if status not in (200, 201) or not text.lstrip().startswith("v=0"):
            raise VoiceServiceError(
                "realtime/wm failed status=%s" % status,
                status_code=502,
                detail=text[:500],
            )

        voice_session_id = _bind_voice_session(voice_session_id, token, account)
        return {
            "answer_sdp": text,
            "session_id": voice_session_id,
            "voice_session_id": voice_session_id,
            "voice": voice,
            "voice_mode": voice_mode or "wingman",
            "device_id": device,
            "account_email": account.get("email") or "",
            "proxy_source": proxy_source,
            "ctype": ctype,
        }

    raise VoiceServiceError(
        last_error or "no available web access_token",
        status_code=401 if last_status == 401 else 503,
        detail=last_detail,
    )


def _image_size(image_bytes: bytes) -> tuple[int, int]:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        return int(img.size[0]), int(img.size[1])
    except Exception:
        return 0, 0


def upload_voice_image(
    *,
    image_bytes: bytes,
    image_name: str,
    image_mime: str = "image/png",
    access_token: str = "",
    proxy: str = "",
    voice_session_id: str = "",
) -> dict[str, Any]:
    """Upload image for realtime voice relay_message (sediment://file_id)."""
    if not image_bytes:
        raise VoiceServiceError("image is empty", status_code=400)

    bound = _bound_voice_session(voice_session_id)
    preferred = str(bound.get("access_token") or access_token or "").strip()
    try:
        token, account = account_pool.pick(preferred)
    except AccountError as exc:
        raise VoiceServiceError(str(exc), status_code=503) from exc

    if voice_session_id:
        _bind_voice_session(voice_session_id, token, account)

    device = str(account.get("device_id") or bound.get("device_id") or uuid.uuid4())
    explicit_proxy = str(proxy or account.get("proxy") or bound.get("proxy") or "").strip()
    width, height = _image_size(image_bytes)
    mime = image_mime or "image/png"
    name = image_name or "image.png"

    sess = build_session(proxy=explicit_proxy)
    try:
        # 1) request upload url
        meta_resp = sess.post(
            FILES_URL,
            headers=_auth_headers(token, device, {
                "content-type": "application/json",
                "accept": "application/json",
            }),
            json={
                "file_name": name,
                "file_size": len(image_bytes),
                "use_case": "multimodal",
                "timezone_offset_min": -480,
                "reset_rate_limits": False,
                "supports_direct_azure_multipart": True,
                "mime_type": mime,
                "width": width or None,
                "height": height or None,
            },
            timeout=60,
        )
        if meta_resp.status_code != 200:
            if meta_resp.status_code == 401:
                account_pool.mark_invalid(token)
                if voice_session_id:
                    release_voice_session(voice_session_id)
                raise VoiceServiceError(
                    "account token invalid",
                    status_code=401,
                    detail=(meta_resp.text or "")[:400],
                )
            raise VoiceServiceError(
                "files request failed status=%s" % meta_resp.status_code,
                status_code=502 if meta_resp.status_code != 403 else 403,
                detail=(meta_resp.text or "")[:400],
            )
        meta = meta_resp.json() or {}
        upload_url = str(meta.get("upload_url") or "")
        file_id = str(meta.get("file_id") or "")
        if not upload_url or not file_id:
            raise VoiceServiceError("files response missing upload_url/file_id", status_code=502, detail=str(meta)[:200])

        # 2) PUT bytes to Azure SAS
        put_resp = sess.put(
            upload_url,
            headers={
                "content-type": mime,
                "x-ms-blob-type": "BlockBlob",
                "x-ms-version": "2020-04-08",
                "origin": "https://chatgpt.com",
                "referer": "https://chatgpt.com/",
                "user-agent": DEFAULT_UA,
                "accept": "application/json, text/plain, */*",
            },
            data=image_bytes,
            timeout=120,
        )
        if put_resp.status_code not in (200, 201):
            raise VoiceServiceError(
                "azure upload failed status=%s" % put_resp.status_code,
                status_code=502,
                detail=(put_resp.text or "")[:300],
            )

        # 3) mark uploaded / process
        uploaded_path = f"{FILES_URL}/{file_id}/uploaded"
        done_resp = sess.post(
            uploaded_path,
            headers=_auth_headers(token, device, {
                "content-type": "application/json",
                "accept": "application/json",
            }),
            data="{}",
            timeout=60,
        )
        # some deployments use process_upload_stream instead; tolerate non-critical failures if file_id exists
        if done_resp.status_code not in (200, 201):
            process_resp = sess.post(
                "https://chatgpt.com/backend-api/files/process_upload_stream",
                headers=_auth_headers(token, device, {"content-type": "application/json"}),
                json={
                    "file_id": file_id,
                    "use_case": "multimodal",
                    "index_for_retrieval": False,
                    "file_name": name,
                },
                timeout=60,
            )
            if process_resp.status_code not in (200, 201):
                # still return file_id; browser may succeed if blob is already written
                pass

        return {
            "file_id": file_id,
            "name": name,
            "mimeType": mime,
            "size": len(image_bytes),
            "width": width,
            "height": height,
            "session_id": voice_session_id,
            "voice_session_id": voice_session_id,
            "account_email": account.get("email") or "",
            "proxy_source": "proxy" if explicit_proxy else "direct",
        }
    except VoiceServiceError:
        raise
    except Exception as exc:
        raise VoiceServiceError("image upload failed: %s" % str(exc)[:240], status_code=502, detail=str(exc)[:400]) from exc
    finally:
        try:
            sess.close()
        except Exception:
            pass
