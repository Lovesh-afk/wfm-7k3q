"""Vercel serverless entry point.

Vercel's Python runtime looks for an ASGI/WSGI object called `app` in files
under /api. We simply re-export the FastAPI app from the backend package, so
the same code runs locally, in Docker and on Vercel.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app  # noqa: E402,F401
