"""
Vercel Python entry point — wraps FastAPI app.
Uses Mangum ASGI adapter for Lambda/serverless compatibility.
"""
import os
import sys

# Add project root to path so 'app' module is findable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.main import app
    try:
        from mangum import Mangum
        handler = Mangum(app, lifespan="off")
    except ImportError:
        handler = app
except Exception as e:
    # Fallback: minimal health-check app if main app fails to load
    from fastapi import FastAPI
    _fallback = FastAPI()

    @_fallback.get("/health")
    def health():
        return {"status": "degraded", "error": str(e), "service": "str-feasibility"}

    @_fallback.get("/")
    def root():
        return {"status": "degraded", "error": str(e)}

    try:
        from mangum import Mangum
        handler = Mangum(_fallback, lifespan="off")
    except ImportError:
        handler = _fallback
