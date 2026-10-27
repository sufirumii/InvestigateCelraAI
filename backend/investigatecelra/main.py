"""InvestigateCelra — application entrypoint.

FastAPI serves both the JSON API and the static desk UI, so the whole product
is one process and one deployment unit.
"""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pipeline
from .api import admin, companies, edition
from .config import FRONTEND_DIR, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")
log = logging.getLogger("investigatecelra")

GATE_COOKIE = "ic_access"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("booting %s (data mode: %s)", settings.app_name, settings.data_mode)
    pipeline.bootstrap()
    store = pipeline.store()
    log.info(
        "ready — %s stories, %s companies, %s setbacks",
        len(store.items), len(store.companies), store.stats.get("setbacks", 0),
    )
    yield


app = FastAPI(
    title=settings.app_name,
    description=settings.tagline,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Optional access gate
# ---------------------------------------------------------------------------
class AccessRequest(BaseModel):
    code: str


@app.middleware("http")
async def access_gate(request: Request, call_next):
    if settings.gate_enabled and request.url.path.startswith("/api/"):
        allowed = {"/api/meta", "/api/health", "/api/session", "/api/docs", "/api/openapi.json"}
        if request.url.path not in allowed:
            token = request.cookies.get(GATE_COOKIE, "")
            if not hmac.compare_digest(token, settings.access_code):
                return JSONResponse({"detail": "access code required"}, status_code=401)
    return await call_next(request)


@app.post("/api/session")
def open_session(payload: AccessRequest) -> JSONResponse:
    if not settings.gate_enabled:
        return JSONResponse({"ok": True, "gate": False})
    if not hmac.compare_digest(payload.code.strip(), settings.access_code):
        raise HTTPException(status_code=401, detail="invalid access code")
    response = JSONResponse({"ok": True, "gate": True})
    response.set_cookie(
        GATE_COOKIE, settings.access_code, httponly=True, samesite="lax", max_age=60 * 60 * 12
    )
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(admin.router)
app.include_router(edition.router)
app.include_router(companies.router)


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
    app.mount("/styles", StaticFiles(directory=FRONTEND_DIR / "styles"), name="styles")
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(FRONTEND_DIR / "index.html")
