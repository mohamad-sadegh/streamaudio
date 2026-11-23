from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import db
from app.routers import auth, mediamtx_auth, publishers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("API starting…")
    await db.init_pool()
    await db.wait_for_db()
    await db.migrate()
    await db.bootstrap_admin()
    logger.info("API ready")
    yield
    await db.close_pool()


app = FastAPI(title="StreamAudio API", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("error") or detail.get("msg") or str(detail)
    else:
        message = str(detail)
    return JSONResponse(status_code=exc.status_code, content={"error": message})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request", "details": exc.errors()},
    )


@app.get("/api/health")
async def health():
    return {"ok": True}


app.include_router(auth.router)
app.include_router(publishers.router)
app.include_router(mediamtx_auth.router)
