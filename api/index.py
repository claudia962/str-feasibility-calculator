"""Vercel Python entry point — wraps FastAPI app with Mangum ASGI adapter."""
from app.main import app

# Vercel uses this module directly — 'app' must be the ASGI callable
# Mangum handles the Lambda/serverless event → ASGI translation
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    # Fallback: Vercel's Python runtime can also use the app directly
    handler = app
