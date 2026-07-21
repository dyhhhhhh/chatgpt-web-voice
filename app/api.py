from __future__ import annotations

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import AUTH_KEY
from app.voice_service import (
    VoiceServiceError,
    create_voice_session,
    release_voice_session,
    upload_voice_image,
)


def require_admin(authorization: str | None) -> None:
    expected = str(AUTH_KEY or "").strip()
    if not expected:
        return
    raw = str(authorization or "").strip()
    token = raw[7:].strip() if raw.lower().startswith("bearer ") else raw
    if token != expected:
        raise HTTPException(status_code=401, detail={"error": "invalid auth key"})


class VoiceSessionRequest(BaseModel):
    offer_sdp: str = Field(..., description="Browser WebRTC offer SDP")
    voice: str = "cove"
    voice_mode: str = "wingman"
    language_code: str = "auto"
    access_token: str = ""
    device_id: str = ""
    proxy: str = ""
    voice_session_id: str = ""


class VoiceSessionResponse(BaseModel):
    answer_sdp: str
    voice: str = "cove"
    voice_mode: str = "wingman"
    device_id: str = ""
    account_email: str = ""
    proxy_source: str = ""
    session_id: str = ""
    voice_session_id: str = ""


class VoiceUploadResponse(BaseModel):
    file_id: str = ""
    name: str = ""
    mimeType: str = "image/png"
    size: int = 0
    width: int = 0
    height: int = 0
    account_email: str = ""
    proxy_source: str = ""
    session_id: str = ""
    voice_session_id: str = ""


class VoiceSessionReleaseRequest(BaseModel):
    voice_session_id: str = ""
    session_id: str = ""


def create_router() -> APIRouter:
    router = APIRouter(tags=["voice"])

    @router.get("/api/voice/health")
    async def voice_health(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {
            "ok": True,
            "endpoint": "/api/voice/session",
            "upload_image": "/api/voice/upload-image",
            "release": "/api/voice/session/release",
            "wm": "https://chatgpt.com/realtime/wm",
            "project": "chatgpt-web-voice",
        }

    @router.post("/api/voice/session", response_model=VoiceSessionResponse)
    async def voice_session(body: VoiceSessionRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            result = create_voice_session(
                body.offer_sdp,
                voice=body.voice,
                voice_mode=body.voice_mode,
                language_code=body.language_code,
                access_token=body.access_token,
                device_id=body.device_id,
                proxy=body.proxy,
                voice_session_id=body.voice_session_id,
            )
            return result
        except VoiceServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"error": exc.message, "detail": exc.detail}) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"error": str(exc)[:300]}) from exc

    @router.post("/api/voice/upload-image", response_model=VoiceUploadResponse)
    async def voice_upload_image(
        authorization: str | None = Header(default=None),
        access_token: str = Form(default=""),
        proxy: str = Form(default=""),
        voice_session_id: str = Form(default=""),
        image: UploadFile = File(...),
    ):
        require_admin(authorization)
        try:
            raw = await image.read()
            return upload_voice_image(
                image_bytes=raw,
                image_name=image.filename or "image.png",
                image_mime=image.content_type or "image/png",
                access_token=access_token,
                proxy=proxy,
                voice_session_id=voice_session_id,
            )
        except VoiceServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"error": exc.message, "detail": exc.detail}) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"error": str(exc)[:300]}) from exc

    @router.post("/api/voice/session/release")
    async def voice_session_release(body: VoiceSessionReleaseRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        session_id = body.voice_session_id or body.session_id
        return {"ok": True, "released": release_voice_session(session_id)}

    return router
