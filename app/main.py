from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import create_router
from app.config import STATIC_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="chatgpt-web-voice", version="0.1.0")
    app.include_router(create_router())

    static_dir = Path(STATIC_DIR)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def index():
            return RedirectResponse(url="/voice.html")

        @app.get("/voice.html")
        async def voice_page():
            path = static_dir / "voice.html"
            if not path.exists():
                return {"error": "voice.html missing"}
            return FileResponse(path)

    return app


app = create_app()
