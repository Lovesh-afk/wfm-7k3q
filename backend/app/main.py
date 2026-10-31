"""
FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload   (from the backend/ folder)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Wind Forecast Monitor API",
    description="Compares UK national wind forecasts (Elexon WINDFOR) with "
                "actual generation (Elexon FUELHH) for January 2026.",
    version="1.0.0",
)

# The React dev server runs on a different port, so allow cross-origin calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router)
