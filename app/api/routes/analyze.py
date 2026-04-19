"""
Core feasibility analysis endpoints.
POST /api/feasibility/analyze — create + trigger async pipeline
GET  /api/feasibility/{id}   — poll for status + progressive results
GET  /api/feasibility/       — list recent analyses
"""
import asyncio
import uuid
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session
from app.database import AsyncSessionLocal
from app.models.database_models import (
    CompAnalysis, FeasibilityAnalysis, FinancialProjection, NeighborhoodScore
)
from app.models.enums import AnalysisStatus
from app.models.schemas import (
    CompAnalysisResponse, FeasibilityAnalysisRequest, FeasibilityAnalysisResponse,
    FeasibilityStatusResponse, FinancialProjectionResponse, NeighborhoodResponse
)
from app.services.airdna_client import get_market_overview, search_comps
from app.services.property_intel import geocode_address, get_neighborhood_score

router = APIRouter(prefix="/api/feasibility", tags=["feasibility"])
logger = structlog.get_logger(__name__)


@router.post(
    "/analyze",
    response_model=FeasibilityAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_analysis(
    request: FeasibilityAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> FeasibilityAnalysisResponse:
    """Start a new feasibility analysis. Returns analysis_id immediately."""
    analysis = FeasibilityAnalysis(
        address=request.address,
        property_type=request.property_type,
        bedrooms=request.bedrooms,
        bathrooms=request.bathrooms,
        purchase_price=request.purchase_price,
        estimated_renovation=request.estimated_renovation,
        down_payment_pct=request.down_payment_pct,
        mortgage_rate_pct=request.mortgage_rate_pct,
        mortgage_term_years=request.mortgage_term_years,
        status=AnalysisStatus.PENDING,
        created_by=request.created_by,
    )
    db.add(analysis)
    await db.flush()
    analysis_id = analysis.id
    await db.commit()

    logger.info("analysis.created", analysis_id=str(analysis_id), address=request.address)
    background_tasks.add_task(_run_pipeline, analysis_id, request)

    return FeasibilityAnalysisResponse(
        analysis_id=analysis_id,
        status=AnalysisStatus.PENDING,
        message=f"Analysis started. Poll GET /api/feasibility/{analysis_id}",
    )


@router.get("/", response_model=list[FeasibilityStatusResponse])
async def list_analyses(
    db: AsyncSession = Depends(get_session), limit: int = 20
) -> list[FeasibilityStatusResponse]:
    """List recent analyses."""
    result = await db.execute(
        select(FeasibilityAnalysis)
        .options(
            selectinload(FeasibilityAnalysis.neighborhood_scores),
            selectinload(FeasibilityAnalysis.comp_analyses),
            selectinload(FeasibilityAnalysis.financial_projections),
        )
        .order_by(desc(FeasibilityAnalysis.created_at))
        .limit(limit)
    )
    analyses = result.scalars().all()
    return [_build_status_response(a) for a in analyses]


@router.get("/{analysis_id}", response_model=FeasibilityStatusResponse)
async def get_analysis(
    analysis_id: UUID, db: AsyncSession = Depends(get_session)
) -> FeasibilityStatusResponse:
    """Get analysis status and progressively available results."""
    result = await db.execute(
        select(FeasibilityAnalysis)
        .options(
            selectinload(FeasibilityAnalysis.neighborhood_scores),
            selectinload(FeasibilityAnalysis.comp_analyses),
            selectinload(FeasibilityAnalysis.financial_projections),
        )
        .where(FeasibilityAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return _build_status_response(analysis)


def _build_status_response(analysis: FeasibilityAnalysis) -> FeasibilityStatusResponse:
    """Build progressive status response from related records."""
    steps = []
    neighborhood = None
    financials = None

    if analysis.neighborhood_scores:
        steps.append("neighbourhood")
        ns = analysis.neighborhood_scores[0]
        neighborhood = NeighborhoodResponse(
            walk_score=ns.walk_score,
            transit_score=ns.transit_score,
            bike_score=ns.bike_score,
            nearest_airport_km=float(ns.nearest_airport_km) if ns.nearest_airport_km else None,
            nearest_airport_name=ns.nearest_airport_name,
            nearest_beach_km=float(ns.nearest_beach_km) if ns.nearest_beach_km else None,
            nearest_downtown_km=float(ns.nearest_downtown_km) if ns.nearest_downtown_km else None,
            restaurants_within_1km=ns.restaurants_within_1km,
            grocery_within_1km=ns.grocery_within_1km,
            neighborhood_score=float(ns.neighborhood_score) if ns.neighborhood_score else None,
            best_for=ns.best_for or [],
        )

    comps = []
    if analysis.comp_analyses:
        steps.append("comps")
        comps = [
            CompAnalysisResponse(
                comp_listing_id=c.comp_listing_id,
                comp_name=c.comp_name,
                distance_km=float(c.distance_km) if c.distance_km else None,
                bedrooms=c.bedrooms,
                annual_revenue=float(c.annual_revenue) if c.annual_revenue else None,
                avg_adr=float(c.avg_adr) if c.avg_adr else None,
                occupancy_rate=float(c.occupancy_rate) if c.occupancy_rate else None,
                similarity_score=float(c.similarity_score) if c.similarity_score else None,
                data_source=c.data_source or "mock",
            )
            for c in analysis.comp_analyses[:10]
        ]

    if analysis.financial_projections:
        steps.append("financials")
        fp = analysis.financial_projections[0]
        financials = FinancialProjectionResponse(
            projection_type=fp.projection_type,
            year1_gross_revenue=float(fp.year1_gross_revenue) if fp.year1_gross_revenue else None,
            noi=float(fp.noi) if fp.noi else None,
            cap_rate=float(fp.cap_rate) if fp.cap_rate else None,
            cash_on_cash_return=float(fp.cash_on_cash_return) if fp.cash_on_cash_return else None,
            break_even_occupancy=float(fp.break_even_occupancy) if fp.break_even_occupancy else None,
        )

    if analysis.latitude:
        steps.append("geocoded")
    if neighborhood:
        steps = [s for s in ["geocoded", "market", "neighbourhood", "comps", "financials"] if s in steps + ["market"]]

    return FeasibilityStatusResponse(
        id=analysis.id,
        status=AnalysisStatus(analysis.status),
        address=analysis.address,
        created_at=analysis.created_at,
        overall_feasibility_score=float(analysis.overall_feasibility_score) if analysis.overall_feasibility_score else None,
        risk_score=float(analysis.risk_score) if analysis.risk_score else None,
        recommendation=analysis.recommendation,
        neighborhood=neighborhood,
        comps=comps,
        financials=financials,
        steps_complete=steps,
    )


async def _run_pipeline(analysis_id: UUID, request: FeasibilityAnalysisRequest) -> None:
    """Async analysis pipeline: geocode → market → neighbourhood → comps → financials."""
    log = logger.bind(analysis_id=str(analysis_id))
    async with AsyncSessionLocal() as db:
        try:
            analysis = await _fetch(db, analysis_id)
            analysis.status = AnalysisStatus.ANALYZING
            await db.commit()

            # Step 1: Geocode
            log.info("pipeline.geocode")
            geo = await geocode_address(request.address)
            if geo:
                analysis = await _fetch(db, analysis_id)
                analysis.latitude = geo.latitude
                analysis.longitude = geo.longitude
                await db.commit()
            else:
                raise ValueError(f"Could not geocode address: {request.address}")

            lat, lng = float(analysis.latitude), float(analysis.longitude)

            # Step 2: Market overview
            log.info("pipeline.market")
            market = await get_market_overview(lat, lng)

            # Step 3: Neighbourhood
            log.info("pipeline.neighbourhood")
            nbhd = await get_neighborhood_score(lat, lng, request.address)
            ns = NeighborhoodScore(
                feasibility_id=analysis_id,
                walk_score=nbhd.walk_score,
                transit_score=nbhd.transit_score,
                bike_score=nbhd.bike_score,
                nearest_airport_km=nbhd.nearest_airport_km,
                nearest_airport_name=nbhd.nearest_airport_name,
                nearest_beach_km=nbhd.nearest_beach_km,
                nearest_downtown_km=nbhd.nearest_downtown_km,
                restaurants_within_1km=nbhd.restaurants_within_1km,
                grocery_within_1km=nbhd.grocery_within_1km,
                neighborhood_score=nbhd.neighborhood_score,
                best_for=nbhd.best_for,
            )
            db.add(ns)
            await db.commit()

            # Step 4: Comps
            log.info("pipeline.comps")
            raw_comps = await search_comps(
                lat=lat, lng=lng,
                radius_km=5.0,
                bedrooms=request.bedrooms,
                property_type=request.property_type or "apartment",
                max_results=20,
            )
            for comp in raw_comps[:15]:
                db.add(CompAnalysis(
                    feasibility_id=analysis_id,
                    comp_listing_id=comp.listing_id,
                    comp_name=comp.name,
                    latitude=comp.latitude,
                    longitude=comp.longitude,
                    distance_km=comp.distance_km,
                    bedrooms=comp.bedrooms,
                    property_type=comp.property_type,
                    annual_revenue=comp.annual_revenue,
                    avg_adr=comp.avg_adr,
                    occupancy_rate=comp.occupancy_rate,
                    avg_review_score=comp.avg_review_score,
                    similarity_score=comp.similarity_score,
                    monthly_revenue=comp.monthly_revenue,
                    monthly_occupancy=comp.monthly_occupancy,
                    monthly_adr=comp.monthly_adr,
                    data_source=comp.data_source,
                ))
            await db.commit()

            # Step 5: Basic financials
            log.info("pipeline.financials")
            gross = market.avg_adr * market.avg_occupancy * 365
            noi = gross * 0.55  # ~45% expense ratio
            purchase = float(request.purchase_price)
            cap_rate = noi / purchase if purchase > 0 else 0
            cash_invested = purchase * float(request.down_payment_pct) / 100 + float(request.estimated_renovation or 0)
            mortgage_monthly = _monthly_mortgage(
                principal=purchase * (1 - float(request.down_payment_pct) / 100),
                annual_rate=float(request.mortgage_rate_pct or 6.5) / 100,
                term_years=int(request.mortgage_term_years),
            )
            coc = (noi - mortgage_monthly * 12) / cash_invested if cash_invested > 0 else 0
            break_even = (gross * 0.45 + mortgage_monthly * 12) / (market.avg_adr * 365) if market.avg_adr > 0 else 0

            score = min(100, max(0, round(
                (cap_rate * 1000) + (coc * 300) + (market.avg_occupancy * 50) + (nbhd.neighborhood_score * 0.2)
            )))

            db.add(FinancialProjection(
                feasibility_id=analysis_id,
                projection_type="base",
                year1_gross_revenue=round(gross, 2),
                noi=round(noi, 2),
                cap_rate=round(cap_rate, 4),
                cash_on_cash_return=round(coc, 4),
                break_even_occupancy=round(break_even, 4),
            ))

            analysis = await _fetch(db, analysis_id)
            analysis.overall_feasibility_score = score
            analysis.risk_score = round(100 - score, 1)
            analysis.recommendation = _score_to_rec(score)
            analysis.status = AnalysisStatus.COMPLETE
            await db.commit()
            log.info("pipeline.complete", score=score)

        except Exception as exc:
            log.error("pipeline.failed", error=str(exc))
            try:
                analysis = await _fetch(db, analysis_id)
                analysis.status = AnalysisStatus.FAILED
                analysis.metadata_ = {"error": str(exc)}
                await db.commit()
            except Exception:
                pass


def _monthly_mortgage(principal: float, annual_rate: float, term_years: int) -> float:
    r = annual_rate / 12
    n = term_years * 12
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def _score_to_rec(score: float) -> str:
    if score >= 75:
        return "strong_buy"
    elif score >= 60:
        return "buy"
    elif score >= 45:
        return "hold"
    elif score >= 30:
        return "avoid"
    return "strong_avoid"


async def _fetch(db: AsyncSession, analysis_id: UUID) -> FeasibilityAnalysis:
    result = await db.execute(select(FeasibilityAnalysis).where(FeasibilityAnalysis.id == analysis_id))
    a = result.scalar_one_or_none()
    if not a:
        raise ValueError(f"Analysis {analysis_id} not found")
    return a
