import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(title="PR Review Agent", version="1.0.0")
app.include_router(webhook_router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": app.version})
