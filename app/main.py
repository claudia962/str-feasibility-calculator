"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from typing import Any
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyze, comps, exit, financials, portfolio, properties, regulations, renovations, reports, scenarios
from app.config import get_settings
from app.database import close_db, engine

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    logger.info("app.startup", environment=settings.environment)
    # Verify DB connection
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("db.connected")
    except Exception as exc:
        logger.warning("db.connection_failed", error=str(exc))
    yield
    await close_db()
    logger.info("app.shutdown")


app = FastAPI(
    title="STR Feasibility Calculator",
    version="1.0.0",
    description="Production-grade STR feasibility and risk analysis platform.",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "str-feasibility", "version": "1.0.0"}


app.include_router(analyze.router)
app.include_router(properties.router)
app.include_router(comps.router)
app.include_router(regulations.router)
app.include_router(financials.router)
app.include_router(scenarios.router)
app.include_router(portfolio.router)
app.include_router(renovations.router)
app.include_router(exit.router)
app.include_router(reports.router)
