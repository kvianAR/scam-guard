"""Scam Guard — FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000

Or as a module:
    python -m app.main
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import calls, simulator, tts, ws
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.seed_on_start:
        from scripts.seed_data import seed

        try:
            seed()
        except Exception as e:  # noqa: BLE001
            logging.getLogger("scamguard").warning("Seed skipped: %s", e)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Scam Guard",
        version="1.0.0",
        description="AI scam-call detection & defense agent",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(calls.router)
    app.include_router(simulator.router)
    app.include_router(tts.router)
    app.include_router(ws.router)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "llm_configured": s.llm_configured,
            "fish_configured": s.fish_configured,
            "llm_provider": s.llm_provider,
            "llm_model": s.llm_model,
        }

    static_dir = s.db_path_resolved.parent.parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
