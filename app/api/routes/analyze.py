"""
Core feasibility analysis endpoints — Phase 2 full pipeline.

POST /api/feasibility/analyze  — create + trigger 8-step async pipeline
GET  /api/feasibility/{id}     — progressive results + full financial data
GET  /api/feasibility/         — list recent analyses
"""
import calendar as _calendar
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session
from app.database import AsyncSessionLocal
from app.models.database_models import (
    CompAnalysis, FeasibilityAnalysis, FeasibilityStressTest,
    FinancialProjection, NeighborhoodScore
)
from app.models.enums import AnalysisStatus
from app.models.schemas import (
    CompAnalysisResponse, FeasibilityAnalysisRequest, FeasibilityAnalysisResponse,
    FeasibilityStatusResponse, FinancialProjectionResponse, NeighborhoodResponse
)
from app.services.airdna_client import get_market_overview, search_comps
from app.services.financial_engine import FinancialEngine, ProFormaInputs, MONTHS
from app.services.monte_carlo import MonteCarloEngine
from app.services.property_intel import geocode_address, get_neighborhood_score
from app.services.stress_tester import StressTester
from app.services.renovation_roi import analyze_renovation_roi
from app.services.exit_strategy import model_exit_strategies
from app.services.supply_pipeline import analyze_supply_pipeline

router = APIRouter(prefix="/api/feasibility", tags=["feasibility"])
logger = structlog.get_logger(__name__)


@router.post("/analyze", response_model=FeasibilityStatusResponse, status_code=status.HTTP_200_OK)
async def create_analysis(
    request: FeasibilityAnalysisRequest,
    db: AsyncSession = Depends(get_session),
) -> FeasibilityStatusResponse:
    """
    Run a full feasibility analysis synchronously.
    Returns the complete result (all 12 steps) in a single response.
    Typical response time: 5-15 seconds. Vercel Pro timeout: 60s.
    """
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

    # Run pipeline synchronously (no background tasks — works on serverless)
    await _run_pipeline(analysis_id, request)

    # Fetch and return the complete result
    result = await db.execute(
        select(FeasibilityAnalysis)
        .options(
            selectinload(FeasibilityAnalysis.neighborhood_scores),
            selectinload(FeasibilityAnalysis.comp_analyses),
            selectinload(FeasibilityAnalysis.financial_projections),
            selectinload(FeasibilityAnalysis.stress_tests),
        )
        .where(FeasibilityAnalysis.id == analysis_id)
    )
    completed = result.scalar_one_or_none()
    if completed:
        return _build_response(completed)

    # Fallback if something went wrong
    return _build_response(analysis)


@router.get("/", response_model=list[FeasibilityStatusResponse])
async def list_analyses(db: AsyncSession = Depends(get_session), limit: int = 20) -> list[FeasibilityStatusResponse]:
    result = await db.execute(
        select(FeasibilityAnalysis)
        .options(
            selectinload(FeasibilityAnalysis.neighborhood_scores),
            selectinload(FeasibilityAnalysis.comp_analyses),
            selectinload(FeasibilityAnalysis.financial_projections),
            selectinload(FeasibilityAnalysis.stress_tests),
        )
        .order_by(desc(FeasibilityAnalysis.created_at))
        .limit(limit)
    )
    return [_build_response(a) for a in result.scalars().all()]


@router.get("/{analysis_id}", response_model=FeasibilityStatusResponse)
async def get_analysis(analysis_id: UUID, db: AsyncSession = Depends(get_session)) -> FeasibilityStatusResponse:
    result = await db.execute(
        select(FeasibilityAnalysis)
        .options(
            selectinload(FeasibilityAnalysis.neighborhood_scores),
            selectinload(FeasibilityAnalysis.comp_analyses),
            selectinload(FeasibilityAnalysis.financial_projections),
            selectinload(FeasibilityAnalysis.stress_tests),
        )
        .where(FeasibilityAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return _build_response(analysis)


def _build_response(analysis: FeasibilityAnalysis) -> FeasibilityStatusResponse:
    steps = []
    neighborhood = None
    financials = None
    comps_out = []

    if analysis.latitude:
        steps.append("geocoded")

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

    if analysis.comp_analyses:
        steps.append("comps")
        comps_out = [
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

    # Find base projection
    base_fp = next((fp for fp in analysis.financial_projections if fp.projection_type == "base"), None)
    if base_fp:
        steps.append("financials")
        financials = FinancialProjectionResponse(
            projection_type=base_fp.projection_type,
            year1_gross_revenue=float(base_fp.year1_gross_revenue) if base_fp.year1_gross_revenue else None,
            noi=float(base_fp.noi) if base_fp.noi else None,
            cap_rate=float(base_fp.cap_rate) if base_fp.cap_rate else None,
            cash_on_cash_return=float(base_fp.cash_on_cash_return) if base_fp.cash_on_cash_return else None,
            break_even_occupancy=float(base_fp.break_even_occupancy) if base_fp.break_even_occupancy else None,
        )

    # Build extended data
    all_projections = []
    for fp in analysis.financial_projections:
        all_projections.append({
            "projection_type": fp.projection_type,
            "year1_gross_revenue": float(fp.year1_gross_revenue) if fp.year1_gross_revenue else None,
            "year2_gross_revenue": float(fp.year2_gross_revenue) if fp.year2_gross_revenue else None,
            "year3_gross_revenue": float(fp.year3_gross_revenue) if fp.year3_gross_revenue else None,
            "noi": float(fp.noi) if fp.noi else None,
            "cap_rate": float(fp.cap_rate) if fp.cap_rate else None,
            "cash_on_cash_return": float(fp.cash_on_cash_return) if fp.cash_on_cash_return else None,
            "break_even_occupancy": float(fp.break_even_occupancy) if fp.break_even_occupancy else None,
            "monthly_projections": fp.monthly_projections,
            "annual_expenses": fp.annual_expenses,
            "mc_revenue_p10": float(fp.mc_revenue_p10) if fp.mc_revenue_p10 else None,
            "mc_revenue_p25": float(fp.mc_revenue_p25) if fp.mc_revenue_p25 else None,
            "mc_revenue_p50": float(fp.mc_revenue_p50) if fp.mc_revenue_p50 else None,
            "mc_revenue_p75": float(fp.mc_revenue_p75) if fp.mc_revenue_p75 else None,
            "mc_revenue_p90": float(fp.mc_revenue_p90) if fp.mc_revenue_p90 else None,
        })

    stress_results = []
    if analysis.stress_tests:
        steps.append("stress_tests")
        for st in analysis.stress_tests:
            stress_results.append({
                "scenario_name": st.scenario_name,
                "scenario_type": st.scenario_type,
                "revenue_impact_pct": float(st.revenue_impact_pct) if st.revenue_impact_pct else None,
                "still_profitable": st.still_profitable,
                "adaptation_strategy": st.adaptation_strategy,
            })

    return FeasibilityStatusResponse(
        id=analysis.id,
        status=AnalysisStatus(analysis.status),
        address=analysis.address,
        created_at=analysis.created_at,
        overall_feasibility_score=float(analysis.overall_feasibility_score) if analysis.overall_feasibility_score else None,
        risk_score=float(analysis.risk_score) if analysis.risk_score else None,
        recommendation=analysis.recommendation,
        neighborhood=neighborhood,
        comps=comps_out,
        financials=financials,
        steps_complete=steps,
    )


# ---------------------------------------------------------------------------
# Full 8-step pipeline
# ---------------------------------------------------------------------------

async def _run_pipeline(analysis_id: UUID, request: FeasibilityAnalysisRequest) -> None:
    log = logger.bind(analysis_id=str(analysis_id))
    async with AsyncSessionLocal() as db:
        try:
            analysis = await _fetch(db, analysis_id)
            analysis.status = AnalysisStatus.ANALYZING
            await db.commit()

            # Step 1: Geocode
            log.info("pipeline.geocode")
            geo = await geocode_address(request.address)
            if not geo:
                raise ValueError(f"Could not geocode: {request.address}")
            analysis = await _fetch(db, analysis_id)
            analysis.latitude = geo.latitude
            analysis.longitude = geo.longitude
            await db.commit()
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
                lat=lat, lng=lng, radius_km=5.0,
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

            # Build ProFormaInputs from market + comps
            comp_adrs = [c.avg_adr for c in raw_comps if c.avg_adr]
            comp_occs = [c.occupancy_rate for c in raw_comps if c.occupancy_rate]

            import statistics
            avg_adr = statistics.median(comp_adrs) if comp_adrs else market.avg_adr
            avg_occ = statistics.median(comp_occs) if comp_occs else market.avg_occupancy

            # Build seasonal curves from comp medians
            monthly_adr_curve: dict[str, float] = {}
            monthly_occ_curve: dict[str, float] = {}
            from app.services.airdna_client import MELBOURNE_SEASONAL
            for m, factor in MELBOURNE_SEASONAL.items():
                monthly_adr_curve[m] = avg_adr * (1 + (factor - 1) * 0.25)
                monthly_occ_curve[m] = min(0.97, avg_occ * factor)

            pf_inputs = ProFormaInputs(
                purchase_price=float(request.purchase_price),
                down_payment_pct=float(request.down_payment_pct),
                mortgage_rate_pct=float(request.mortgage_rate_pct or 6.5),
                mortgage_term_years=int(request.mortgage_term_years),
                avg_adr=avg_adr,
                avg_occupancy=avg_occ,
                monthly_adr=monthly_adr_curve,
                monthly_occupancy=monthly_occ_curve,
                estimated_renovation=float(request.estimated_renovation or 0),
                is_self_managed=True,
            )

            # Step 5: Full financial engine (3 scenarios)
            log.info("pipeline.financials")
            engine = FinancialEngine()
            scenarios = engine.generate_three_scenarios(pf_inputs, comp_adrs, comp_occs)

            for label, result in scenarios.items():
                mp_data = [{"month": mp.month, "adr": mp.adr, "occupancy": mp.occupancy,
                            "revenue": mp.revenue, "occupied_nights": mp.occupied_nights}
                           for mp in result.monthly_projections]
                db.add(FinancialProjection(
                    feasibility_id=analysis_id,
                    projection_type=label,
                    year1_gross_revenue=result.year1_revenue,
                    year2_gross_revenue=result.year2_revenue,
                    year3_gross_revenue=result.year3_revenue,
                    noi=result.noi,
                    cap_rate=result.cap_rate,
                    cash_on_cash_return=result.cash_on_cash,
                    break_even_occupancy=result.break_even_occupancy,
                    monthly_projections=mp_data,
                    annual_expenses=result.expenses.as_dict(),
                ))
            await db.commit()

            # Step 6: Monte Carlo
            log.info("pipeline.monte_carlo")
            mc_engine = MonteCarloEngine()
            mc_result = mc_engine.run_simulation(raw_comps, pf_inputs, n_sims=2000)

            base_fp_db = next(fp for fp in (await db.execute(
                select(FinancialProjection).where(
                    FinancialProjection.feasibility_id == analysis_id,
                    FinancialProjection.projection_type == "base"
                )
            )).scalars().all() for _ in [None])

            base_fp_db.mc_revenue_p10 = mc_result.revenue_p10
            base_fp_db.mc_revenue_p25 = mc_result.revenue_p25
            base_fp_db.mc_revenue_p50 = mc_result.revenue_p50
            base_fp_db.mc_revenue_p75 = mc_result.revenue_p75
            base_fp_db.mc_revenue_p90 = mc_result.revenue_p90
            # Store histogram in monthly_projections extension field
            mc_extra = base_fp_db.annual_expenses or {}
            mc_extra["mc_noi_p10"] = mc_result.noi_p10
            mc_extra["mc_noi_p50"] = mc_result.noi_p50
            mc_extra["mc_noi_p90"] = mc_result.noi_p90
            mc_extra["mc_coc_p50"] = mc_result.coc_p50
            mc_extra["mc_probability_of_loss"] = mc_result.probability_of_loss
            mc_extra["mc_histogram_bins"] = mc_result.histogram_bins
            mc_extra["mc_histogram_counts"] = mc_result.histogram_counts
            base_fp_db.annual_expenses = mc_extra
            await db.commit()

            # Step 7: Stress tests
            log.info("pipeline.stress_tests")
            base_result = scenarios["base"]
            tester = StressTester(pf_inputs, base_result)
            stress_results = tester.run_all()
            for sr in stress_results:
                db.add(FeasibilityStressTest(
                    feasibility_id=analysis_id,
                    scenario_name=sr.scenario_name,
                    scenario_type=sr.scenario_type,
                    parameters=sr.parameters,
                    revenue_impact_pct=sr.revenue_impact_pct,
                    still_profitable=sr.still_profitable,
                    adaptation_strategy=sr.adaptation_strategy,
                ))
            await db.commit()

            # Step 8: Regulation assessment
            log.info("pipeline.regulations")
            try:
                import json as _json
                from pathlib import Path
                reg_path = Path(__file__).parent.parent.parent.parent / "app" / "data" / "regulations.json"
                if not reg_path.exists():
                    reg_path = Path(__file__).parent.parent.parent / "data" / "regulations.json"
                reg_data = _json.loads(reg_path.read_text())
                # Detect state from geocoded address
                state_key = "victoria"  # default; detect from address string if possible
                addr_lower = request.address.lower()
                if "nsw" in addr_lower or "new south wales" in addr_lower or "sydney" in addr_lower:
                    state_key = "new_south_wales"
                elif "qld" in addr_lower or "queensland" in addr_lower or "brisbane" in addr_lower:
                    state_key = "queensland"
                reg = reg_data.get(state_key, reg_data["default"])
                from app.models.database_models import RegulationAssessment
                from datetime import datetime, timezone
                db.add(RegulationAssessment(
                    feasibility_id=analysis_id,
                    municipality=state_key.replace("_", " ").title(),
                    str_allowed=reg["str_allowed"],
                    permit_required=reg["permit_required"],
                    max_nights_per_year=reg.get("max_nights_per_year"),
                    regulation_risk_score=reg["regulation_risk_score"],
                    pending_legislation=reg.get("pending_legislation"),
                    enforcement_level=reg.get("enforcement_level"),
                    last_verified=datetime.now(timezone.utc),
                    notes=reg.get("notes"),
                ))
                await db.commit()
            except Exception as exc:
                log.warning("pipeline.regulations.error", error=str(exc))

            # Step 9: Renovation ROI
            log.info("pipeline.renovation_roi")
            try:
                reno_results = analyze_renovation_roi(raw_comps, avg_adr, avg_occ)
                from app.models.database_models import RenovationAnalysis
                for rr in reno_results:
                    db.add(RenovationAnalysis(
                        feasibility_id=analysis_id,
                        renovation_item=rr.renovation_item,
                        estimated_cost=rr.estimated_cost,
                        roi_1yr_pct=rr.roi_1yr_pct / 100,
                        recommendation=rr.recommendation,
                        reasoning=rr.reasoning,
                    ))
                await db.commit()
            except Exception as exc:
                log.warning("pipeline.renovation_roi.error", error=str(exc))

            # Step 10: Exit strategies
            log.info("pipeline.exit_strategies")
            try:
                exit_result = model_exit_strategies(
                    purchase_price=float(request.purchase_price),
                    annual_str_noi=base_result.noi,
                    annual_mortgage=base_result.expenses.mortgage_annual,
                    cash_invested=base_result.cash_invested,
                    avg_adr=avg_adr,
                )
                from app.models.database_models import ExitStrategy
                for path in exit_result.paths:
                    db.add(ExitStrategy(
                        feasibility_id=analysis_id,
                        strategy_type=path.strategy_type,
                        estimated_monthly_income=path.estimated_monthly_income,
                        estimated_annual_return=path.estimated_annual_return,
                        notes=path.notes,
                    ))
                await db.commit()
            except Exception as exc:
                log.warning("pipeline.exit_strategies.error", error=str(exc))

            # Step 11: Supply pipeline
            log.info("pipeline.supply_pipeline")
            try:
                supply = analyze_supply_pipeline(lat, lng)
                from app.models.database_models import SupplyPipeline
                db.add(SupplyPipeline(
                    feasibility_id=analysis_id,
                    new_listings_last_12mo=supply.new_listings_last_12mo,
                    supply_growth_pct_12mo=supply.supply_growth_pct_12mo,
                    source_data={"source": supply.source, "total_in_radius": supply.total_in_radius, "new_6mo": supply.new_listings_last_6mo},
                ))
                await db.commit()
            except Exception as exc:
                log.warning("pipeline.supply_pipeline.error", error=str(exc))

            # Step 12: Compute overall score and complete

            base = scenarios["base"]
            score = min(100, max(0, round(
                (base.cap_rate * 800) +
                (base.cash_on_cash * 300) +
                (avg_occ * 40) +
                (nbhd.neighborhood_score * 0.15) +
                (50 if base.cash_on_cash > 0 else 0)
            )))
            analysis = await _fetch(db, analysis_id)
            analysis.overall_feasibility_score = score
            analysis.risk_score = round(100 - score, 1)
            analysis.recommendation = _score_to_rec(score)
            analysis.status = AnalysisStatus.COMPLETE
            await db.commit()
            log.info("pipeline.complete", score=score, noi=base.noi, cap_rate=base.cap_rate)

        except Exception as exc:
            log.error("pipeline.failed", error=str(exc))
            try:
                a = await _fetch(db, analysis_id)
                a.status = AnalysisStatus.FAILED
                a.metadata_ = {"error": str(exc)}
                await db.commit()
            except Exception:
                pass


def _monthly_mortgage(principal: float, annual_rate: float, term_years: int) -> float:
    r = annual_rate / 12
    n = term_years * 12
    if r == 0:
        return principal / n if n > 0 else 0
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
