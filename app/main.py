import logging
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.api.webhook import router as webhook_router
from app.portal import router as portal_router
from app.core.config import execution_mode, fastapi_doc_kwargs, max_bar_age_seconds, require_secret_strength
from app.execution.arcus import ArcusError
from app.execution.arcus_remote import apply_remote_leverage

logger = logging.getLogger(__name__)


def preload_positions() -> None:
    try:
        apply_remote_leverage()
    except ArcusError as exc:
        logger.warning("%s", exc)
    except Exception:
        logger.warning("arcus leverage was not applied")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.execution.venue_port import load_ports

    require_secret_strength("WEBHOOK_SECRET", "PORTAL_PASSWORD", "ANALYTICS_API_SECRET")
    max_bar_age_seconds()
    load_ports()
    if execution_mode() == "live":
        Thread(target=preload_positions, daemon=True).start()
    yield


app = FastAPI(title="Signal Nexus", lifespan=lifespan, **fastapi_doc_kwargs())
app.include_router(webhook_router)
app.include_router(portal_router)

_ICON_DIR = Path(__file__).resolve().parent / "static"
_ICON_CACHE = {"Cache-Control": "public, max-age=86400"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(_ICON_DIR / "favicon-32.png", media_type="image/png", headers=_ICON_CACHE)


@app.get("/apple-touch-icon.png", include_in_schema=False)
def apple_touch_icon() -> FileResponse:
    return FileResponse(_ICON_DIR / "favicon-180.png", media_type="image/png", headers=_ICON_CACHE)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/portal", status_code=302)


@app.get("/health")
def health() -> JSONResponse:
    # Keep this tiny: cron-job.org aborts above 64 KiB (headers + body).
    return JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})
