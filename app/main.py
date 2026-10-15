import logging
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.webhook import router as webhook_router
from app.portal import router as portal_router
from app.core.config import execution_mode
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
    if execution_mode() == "live":
        Thread(target=preload_positions, daemon=True).start()
    yield


app = FastAPI(title="Signal Nexus", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(portal_router)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/portal", status_code=302)


@app.get("/health")
def health() -> JSONResponse:
    # Keep this tiny: cron-job.org aborts above 64 KiB (headers + body).
    return JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})
