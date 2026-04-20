"""Vercel Python serverless entry point for FastAPI."""
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="STR Feasibility API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_main_app = None
_load_error = None

try:
    from app.main import app as _main_app
except Exception as e:
    _load_error = str(e)


@app.get("/health")
def health():
    if _load_error:
        return {"status": "degraded", "error": _load_error}
    return {"status": "ok", "service": "str-feasibility", "version": "1.0.0"}


@app.get("/")
def root():
    if _load_error:
        return {"status": "degraded", "error": _load_error}
    return {"service": "str-feasibility", "version": "1.0.0"}


# If main app loaded successfully, mount all its routes
if _main_app is not None:
    app = _main_app
