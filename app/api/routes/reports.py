"""Reports endpoint — generate and download PDF feasibility reports."""
import os
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.models.database_models import FeasibilityAnalysis
from app.services.report_generator import ReportGenerator, REPORTS_DIR

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = structlog.get_logger(__name__)


@router.get("/{analysis_id}/pdf")
async def get_report_pdf(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_session),
) -> FileResponse:
    """
    Generate (if needed) and return the PDF feasibility report.
    Falls back to HTML if WeasyPrint is not installed.
    """
    result = await db.execute(
        select(FeasibilityAnalysis).where(FeasibilityAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    if analysis.status != "complete":
        raise HTTPException(status_code=409, detail="Analysis not yet complete")

    # Check if already generated
    if analysis.report_pdf_path and Path(analysis.report_pdf_path).exists():
        path = Path(analysis.report_pdf_path)
        media_type = "application/pdf" if path.suffix == ".pdf" else "text/html"
        return FileResponse(str(path), media_type=media_type,
                            filename=f"feasibility-report-{analysis_id}.{path.suffix[1:]}")

    # Generate now
    try:
        generator = ReportGenerator()
        pdf_path = await generator.generate_pdf(str(analysis_id), db)
        path = Path(pdf_path)
        media_type = "application/pdf" if path.suffix == ".pdf" else "text/html"
        return FileResponse(str(path), media_type=media_type,
                            filename=f"feasibility-report-{analysis_id}.{path.suffix[1:]}")
    except Exception as exc:
        logger.error("reports.pdf_failed", error=str(exc), analysis_id=str(analysis_id))
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")


@router.get("/{analysis_id}/markdown")
async def get_report_markdown(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Return the raw markdown report content."""
    result = await db.execute(
        select(FeasibilityAnalysis).where(FeasibilityAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Not found")
    if not analysis.report_content:
        raise HTTPException(status_code=404, detail="Report not yet generated. GET /pdf to trigger generation.")
    return JSONResponse({"markdown": analysis.report_content})
