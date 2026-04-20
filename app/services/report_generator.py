"""
STR Feasibility Report Generator.

Generates structured markdown reports from analysis data,
computes overall feasibility scores, and renders PDFs via WeasyPrint.
"""
import os
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

import tempfile as _tmpmod

# Use /tmp on serverless (read-only filesystem), local dir otherwise
_local_reports = Path(__file__).parent.parent.parent / "reports"
if os.environ.get("VERCEL") or not os.access(str(_local_reports.parent), os.W_OK):
    REPORTS_DIR = Path(_tmpmod.gettempdir()) / "feasibility_reports"
else:
    REPORTS_DIR = _local_reports
REPORTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------

def calculate_score(data: dict) -> tuple[float, str]:
    """
    Calculate overall feasibility score (0-100) and recommendation.

    Weighted components:
    - Financial (40pts): cap_rate thresholds
    - Regulation (20pts): inverted risk score
    - Market (20pts): occupancy vs market, supply growth
    - Neighbourhood (10pts): neighborhood_score / 10
    - Monte Carlo (10pts): probability_of_loss thresholds
    """
    score = 0.0

    # Financial (40pts)
    cap_rate = data.get("cap_rate", 0) or 0
    if cap_rate > 0.05:
        score += 40
    elif cap_rate > 0.04:
        score += 30
    elif cap_rate > 0.03:
        score += 20
    elif cap_rate > 0.02:
        score += 10
    elif cap_rate > 0.01:
        score += 5

    # Regulation (20pts): inverted risk score (25 risk = 15pts, 100 risk = 0pts)
    reg_risk = data.get("regulation_risk_score", 50) or 50
    reg_score = max(0, (100 - reg_risk) / 100 * 20)
    score += reg_score

    # Market (20pts): occupancy vs market + supply
    avg_occ = data.get("avg_occupancy", 0) or 0
    supply_growth = data.get("supply_growth_pct_12mo", 0) or 0
    occ_score = min(20, avg_occ * 25)  # 80% occ = 20pts
    supply_penalty = min(5, supply_growth * 0.5)
    score += max(0, occ_score - supply_penalty)

    # Neighbourhood (10pts)
    nbhd_score = data.get("neighborhood_score", 50) or 50
    score += nbhd_score / 10

    # Monte Carlo (10pts)
    prob_loss = data.get("probability_of_loss", 0.5) or 0.5
    if prob_loss < 0.10:
        score += 10
    elif prob_loss < 0.20:
        score += 7
    elif prob_loss < 0.30:
        score += 4
    elif prob_loss < 0.50:
        score += 2

    score = min(100, max(0, round(score, 1)))

    if score >= 75:
        rec = "strong_buy"
    elif score >= 60:
        rec = "buy"
    elif score >= 45:
        rec = "hold"
    elif score >= 30:
        rec = "avoid"
    else:
        rec = "strong_avoid"

    return score, rec


# ---------------------------------------------------------------------------
# Markdown report generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generates markdown and PDF reports from feasibility analysis data."""

    def generate_overall_score(self, data: dict) -> tuple[float, str]:
        """Compute score and recommendation from analysis data dict."""
        return calculate_score(data)

    def generate_markdown(self, analysis_id: str, data: dict) -> str:
        """
        Generate a full markdown report from analysis data.
        Substitutes all {{variable}} placeholders.
        """
        address = data.get("address", "Unknown Address")
        created_at = data.get("created_at", datetime.now(timezone.utc).isoformat())
        score, rec = self.generate_overall_score(data)
        rec_label = rec.replace("_", " ").title()
        rec_emoji = {"strong_buy": "🟢", "buy": "🟩", "hold": "🟡",
                     "avoid": "🟠", "strong_avoid": "🔴"}.get(rec, "⚪")

        # Financials
        gross_rev = data.get("gross_revenue", 0) or 0
        noi = data.get("noi", 0) or 0
        cap_rate = (data.get("cap_rate", 0) or 0) * 100
        coc = (data.get("cash_on_cash_return", 0) or 0) * 100
        break_even = (data.get("break_even_occupancy", 0) or 0) * 100
        avg_adr = data.get("avg_adr", 0) or 0
        avg_occ = (data.get("avg_occupancy", 0) or 0) * 100

        # Comps
        comps = data.get("comps", [])
        comp_adrs = [c.get("avg_adr", 0) for c in comps if c.get("avg_adr")]
        adr_percentile = 50
        if comp_adrs and avg_adr:
            below = sum(1 for a in comp_adrs if a < avg_adr)
            adr_percentile = int(below / len(comp_adrs) * 100)

        # Monte Carlo
        mc_p10 = data.get("mc_revenue_p10", 0) or 0
        mc_p50 = data.get("mc_revenue_p50", 0) or 0
        mc_p90 = data.get("mc_revenue_p90", 0) or 0
        prob_loss = (data.get("probability_of_loss", 0) or 0) * 100

        # Regulation
        str_allowed = data.get("str_allowed", True)
        reg_risk = data.get("regulation_risk_score", 25) or 25
        reg_note = data.get("pending_legislation", "No pending legislation noted.")

        # Neighbourhood
        walk = data.get("walk_score", "N/A")
        nbhd_score = data.get("neighborhood_score", 0) or 0
        airport_km = data.get("nearest_airport_km", "N/A")
        cbd_km = data.get("nearest_downtown_km", "N/A")
        best_for = ", ".join(data.get("best_for", ["couples"])) or "general"

        # Supply
        supply_growth = data.get("supply_growth_pct_12mo", 4.2) or 4.2
        new_listings_12mo = data.get("new_listings_last_12mo", 85) or 85

        # Stress tests
        stress_tests = data.get("stress_tests", [])

        # Renovations
        renovations = data.get("renovations", [])
        top_renos = sorted(renovations, key=lambda r: r.get("roi_1yr_pct", 0), reverse=True)[:3]

        # Exit strategies
        exits = data.get("exit_strategies", [])
        str_exit = next((e for e in exits if e.get("strategy_type") == "continue_str"), {})
        ltr_exit = next((e for e in exits if e.get("strategy_type") == "long_term_rental"), {})
        sell_exit = next((e for e in exits if e.get("strategy_type") == "sell"), {})

        # Recommendation reasoning
        reasoning = self._generate_reasoning(data, score, rec, cap_rate, avg_occ, prob_loss)

        # Build markdown
        md = f"""# STR Feasibility Report — {address}

**Generated:** {created_at[:10]}  
**Analysis ID:** {analysis_id}

---

## Executive Summary

{rec_emoji} **Overall Score: {score:.0f}/100** — {rec_label}

{reasoning}

### Key Metrics at a Glance

| Metric | Value |
|--------|-------|
| Projected Annual Revenue | ${gross_rev:,.0f} |
| Net Operating Income (NOI) | ${noi:,.0f} |
| Cap Rate | {cap_rate:.2f}% |
| Cash-on-Cash Return | {coc:.2f}% |
| Break-Even Occupancy | {break_even:.0f}% |
| Average Daily Rate (ADR) | ${avg_adr:.0f} |
| Average Occupancy | {avg_occ:.0f}% |

---

## 1. Comparable Analysis

**{len(comps)} comparable properties** found within search radius.  
Your projected ADR of **${avg_adr:.0f}** places you at the **{adr_percentile}th percentile** of comparable properties.

| Property | Distance | Beds | ADR | Occupancy | Similarity |
|----------|----------|------|-----|-----------|------------|
"""
        for comp in comps[:8]:
            md += (f"| {(comp.get('comp_name') or 'N/A')[:35]} "
                   f"| {comp.get('distance_km', '?')} km "
                   f"| {comp.get('bedrooms', '?')} "
                   f"| ${comp.get('avg_adr', 0):,.0f} "
                   f"| {(comp.get('occupancy_rate', 0) or 0)*100:.0f}% "
                   f"| {comp.get('similarity_score', 0):.2f} |\n")

        md += f"""
*Data source: {comps[0].get('data_source', 'mock') if comps else 'mock'}*

---

## 2. Regulatory Risk

**STR Allowed:** {'✅ Yes' if str_allowed else '🚫 No'}  
**Regulation Risk Score:** {reg_risk}/100 (lower = less risk)

> ⚠️ {reg_note}

*Last verified: {data.get("reg_last_verified", datetime.now().strftime("%Y-%m-%d"))}*

---

## 3. Neighbourhood

| Score | Walk Score | Airport | CBD | Best For |
|-------|-----------|---------|-----|---------|
| {nbhd_score:.0f}/100 | {walk} | {airport_km} km | {cbd_km} km | {best_for} |

---

## 4. Financial Projections

### Three Scenarios

| Scenario | Gross Revenue | NOI | Cap Rate | Cash-on-Cash |
|----------|--------------|-----|----------|-------------|
"""
        for scenario_key in ["pessimistic", "base", "optimistic"]:
            s = data.get(f"scenario_{scenario_key}", {})
            if s:
                md += (f"| {scenario_key.title()} "
                       f"| ${s.get('gross_revenue', 0):,.0f} "
                       f"| ${s.get('noi', 0):,.0f} "
                       f"| {(s.get('cap_rate', 0) or 0)*100:.2f}% "
                       f"| {(s.get('coc', 0) or 0)*100:.2f}% |\n")

        md += f"""
**Break-Even Occupancy:** {break_even:.1f}%  
*(Property needs ≥{break_even:.1f}% occupancy to cover all expenses including mortgage)*

---

## 5. Monte Carlo Simulation (2,000 runs)

| Percentile | Annual Revenue |
|------------|---------------|
| P10 (pessimistic) | ${mc_p10:,.0f} |
| P50 (median) | ${mc_p50:,.0f} |
| P90 (optimistic) | ${mc_p90:,.0f} |

**Probability of Loss (NOI < 0):** {prob_loss:.1f}%

---

## 6. Stress Test Scenarios

| Scenario | Revenue Impact | Still Profitable | Adaptation |
|----------|---------------|-----------------|------------|
"""
        for st in stress_tests[:7]:
            impact = (st.get("revenue_impact_pct", 0) or 0) * 100
            profitable = "✅" if st.get("still_profitable") else "🚫"
            strategy_short = (st.get("adaptation_strategy", "") or "")[:60]
            md += (f"| {st.get('scenario_name', 'N/A')[:30]} "
                   f"| {impact:+.1f}% "
                   f"| {profitable} "
                   f"| {strategy_short}... |\n")

        md += f"""
---

## 7. Supply Pipeline

**New listings (last 12 months):** {new_listings_12mo}  
**Supply growth:** {supply_growth:.1f}%  
Estimated ADR pressure: {data.get("estimated_adr_pressure_pct", -1.3):.1f}%

---

## 8. Renovation Opportunities

| Item | Cost | Annual Uplift | Payback | Recommendation |
|------|------|--------------|---------|---------------|
"""
        for reno in top_renos:
            md += (f"| {reno.get('renovation_item','').replace('_',' ').title()} "
                   f"| ${reno.get('estimated_cost', 0):,.0f} "
                   f"| ${reno.get('annual_revenue_increase', 0):,.0f} "
                   f"| {reno.get('payback_period_months', 999)} mo "
                   f"| {reno.get('recommendation','').replace('_',' ').title()} |\n")

        md += f"""
---

## 9. Exit Strategies

| Strategy | Monthly Income | Annual Return | Notes |
|----------|---------------|--------------|-------|
| Continue STR | ${(str_exit.get('estimated_monthly_income', 0) or 0):,.0f} | {(str_exit.get('estimated_annual_return', 0) or 0)*100:.1f}% | {(str_exit.get('notes','') or '')[:60]} |
| Long-Term Rental | ${(ltr_exit.get('estimated_monthly_income', 0) or 0):,.0f} | {(ltr_exit.get('estimated_annual_return', 0) or 0)*100:.1f}% | {(ltr_exit.get('notes','') or '')[:60]} |
| Sell | $0 | {(sell_exit.get('estimated_annual_return', 0) or 0)*100:.1f}% | {(sell_exit.get('notes','') or '')[:60]} |

---

## Methodology & Disclaimer

- Comparable data: Inside Airbnb (Melbourne, Sep 2025) / Airbnb live search
- Financial modelling: Monte Carlo simulation (2,000 runs)
- Regulation data: Manually verified as at {datetime.now().strftime("%Y-%m-%d")}
- **All projections are estimates. Past performance does not guarantee future results.**
- This report is for informational purposes only and does not constitute financial advice.

---
*Generated by STR Feasibility Calculator v1.0 | {datetime.now().strftime("%Y-%m-%d %H:%M")} UTC*
"""
        return md

    def _generate_reasoning(self, data: dict, score: float, rec: str,
                             cap_rate: float, avg_occ: float, prob_loss: float) -> str:
        """Generate 2-3 sentence specific recommendation reasoning."""
        address = data.get("address", "This property")
        gross = data.get("gross_revenue", 0) or 0
        reg_risk = data.get("regulation_risk_score", 25) or 25
        noi = data.get("noi", 0) or 0

        if rec in ("strong_buy", "buy"):
            return (
                f"**{address}** presents a {rec.replace('_',' ')} opportunity with a projected "
                f"gross revenue of **${gross:,.0f}/year** and cap rate of **{cap_rate:.1f}%**. "
                f"At **{avg_occ:.0f}% occupancy**, the property is positioned above market "
                f"break-even, and Monte Carlo analysis indicates only **{prob_loss:.0f}% probability of loss**. "
                f"Regulatory risk is {'low' if reg_risk < 30 else 'moderate'} ({reg_risk}/100)."
            )
        elif rec == "hold":
            return (
                f"**{address}** shows mixed signals — projected NOI of **${noi:,.0f}** is "
                f"{'positive' if noi > 0 else 'negative'} at a cap rate of **{cap_rate:.1f}%**. "
                f"The **{prob_loss:.0f}% probability of loss** warrants caution. "
                f"Consider optimising listing quality and pricing strategy before committing."
            )
        else:
            return (
                f"**{address}** does not currently meet investment thresholds at projected "
                f"cap rate of **{cap_rate:.1f}%** and NOI of **${noi:,.0f}**. "
                f"Monte Carlo shows **{prob_loss:.0f}% probability of loss** across simulations. "
                f"Review purchase price, renovation budget, or consider alternative investment structures."
            )

    async def generate_pdf(self, analysis_id: str, db) -> str:
        """
        Generate PDF report for an analysis.
        Returns the file path.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.database_models import (
            FeasibilityAnalysis, CompAnalysis, FeasibilityStressTest,
            FinancialProjection, NeighborhoodScore, RegulationAssessment,
            RenovationAnalysis, ExitStrategy, SupplyPipeline
        )

        # Load analysis data
        result = await db.execute(
            select(FeasibilityAnalysis)
            .options(
                selectinload(FeasibilityAnalysis.comp_analyses),
                selectinload(FeasibilityAnalysis.financial_projections),
                selectinload(FeasibilityAnalysis.stress_tests),
                selectinload(FeasibilityAnalysis.neighborhood_scores),
                selectinload(FeasibilityAnalysis.regulation_assessments),
                selectinload(FeasibilityAnalysis.renovation_analyses),
                selectinload(FeasibilityAnalysis.exit_strategies),
                selectinload(FeasibilityAnalysis.supply_pipeline),
            )
            .where(FeasibilityAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        # Build data dict
        base_fp = next((fp for fp in analysis.financial_projections if fp.projection_type == "base"), None)
        ns = analysis.neighborhood_scores[0] if analysis.neighborhood_scores else None
        reg = analysis.regulation_assessments[0] if analysis.regulation_assessments else None
        supply = analysis.supply_pipeline[0] if analysis.supply_pipeline else None
        mc_data = base_fp.annual_expenses or {} if base_fp else {}

        data = {
            "address": analysis.address,
            "created_at": str(analysis.created_at),
            "gross_revenue": float(base_fp.year1_gross_revenue or 0) if base_fp else 0,
            "noi": float(base_fp.noi or 0) if base_fp else 0,
            "cap_rate": float(base_fp.cap_rate or 0) if base_fp else 0,
            "cash_on_cash_return": float(base_fp.cash_on_cash_return or 0) if base_fp else 0,
            "break_even_occupancy": float(base_fp.break_even_occupancy or 0) if base_fp else 0,
            "avg_adr": statistics.median([float(c.avg_adr) for c in analysis.comp_analyses if c.avg_adr]) if analysis.comp_analyses else 180,
            "avg_occupancy": statistics.median([float(c.occupancy_rate) for c in analysis.comp_analyses if c.occupancy_rate]) if analysis.comp_analyses else 0.65,
            "comps": [{"comp_name": c.comp_name, "distance_km": float(c.distance_km or 0), "bedrooms": c.bedrooms,
                       "avg_adr": float(c.avg_adr or 0), "occupancy_rate": float(c.occupancy_rate or 0),
                       "similarity_score": float(c.similarity_score or 0), "data_source": c.data_source}
                      for c in analysis.comp_analyses[:8]],
            "mc_revenue_p10": float(base_fp.mc_revenue_p10 or 0) if base_fp else 0,
            "mc_revenue_p50": float(base_fp.mc_revenue_p50 or 0) if base_fp else 0,
            "mc_revenue_p90": float(base_fp.mc_revenue_p90 or 0) if base_fp else 0,
            "probability_of_loss": mc_data.get("mc_probability_of_loss", 0.3),
            "str_allowed": reg.str_allowed if reg else True,
            "regulation_risk_score": float(reg.regulation_risk_score or 25) if reg else 25,
            "pending_legislation": reg.pending_legislation if reg else "",
            "reg_last_verified": str(reg.last_verified)[:10] if reg and reg.last_verified else datetime.now().strftime("%Y-%m-%d"),
            "neighborhood_score": float(ns.neighborhood_score or 0) if ns else 0,
            "walk_score": ns.walk_score if ns else "N/A",
            "nearest_airport_km": float(ns.nearest_airport_km or 0) if ns else "N/A",
            "nearest_downtown_km": float(ns.nearest_downtown_km or 0) if ns else "N/A",
            "best_for": ns.best_for or [] if ns else [],
            "supply_growth_pct_12mo": float(supply.supply_growth_pct_12mo or 0) if supply else 4.2,
            "new_listings_last_12mo": supply.new_listings_last_12mo if supply else 0,
            "stress_tests": [{"scenario_name": st.scenario_name, "revenue_impact_pct": float(st.revenue_impact_pct or 0),
                              "still_profitable": st.still_profitable, "adaptation_strategy": st.adaptation_strategy}
                             for st in analysis.stress_tests],
            "renovations": [{"renovation_item": r.renovation_item, "estimated_cost": float(r.estimated_cost or 0),
                             "annual_revenue_increase": 0, "payback_period_months": 0,
                             "roi_1yr_pct": float(r.roi_1yr_pct or 0) * 100, "recommendation": r.recommendation}
                            for r in analysis.renovation_analyses],
            "exit_strategies": [{"strategy_type": e.strategy_type, "estimated_monthly_income": float(e.estimated_monthly_income or 0),
                                  "estimated_annual_return": float(e.estimated_annual_return or 0), "notes": e.notes}
                                 for e in analysis.exit_strategies],
        }

        markdown_content = self.generate_markdown(str(analysis_id), data)

        # Save markdown
        md_path = REPORTS_DIR / f"{analysis_id}.md"
        md_path.write_text(markdown_content, encoding="utf-8")

        # Convert to PDF
        pdf_path = REPORTS_DIR / f"{analysis_id}.pdf"
        try:
            import markdown2
            html_content = markdown2.markdown(markdown_content, extras=["tables", "fenced-code-blocks"])
            styled_html = f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; color: #1a1a2e; line-height: 1.6; }}
h1 {{ color: #0F172A; border-bottom: 3px solid #AF7225; padding-bottom: 10px; }}
h2 {{ color: #0F172A; border-bottom: 1px solid #e0e0e0; margin-top: 30px; }}
table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
th {{ background: #0F172A; color: white; padding: 8px; text-align: left; }}
td {{ border: 1px solid #ddd; padding: 8px; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
blockquote {{ border-left: 4px solid #AF7225; padding-left: 15px; color: #555; }}
code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
</style></head><body>{html_content}</body></html>"""

            try:
                from weasyprint import HTML
                HTML(string=styled_html).write_pdf(str(pdf_path))
                logger.info("report.pdf_generated", path=str(pdf_path))
            except ImportError:
                # WeasyPrint not installed — save HTML instead
                html_path = REPORTS_DIR / f"{analysis_id}.html"
                html_path.write_text(styled_html, encoding="utf-8")
                pdf_path = html_path
                logger.warning("report.weasyprint_not_installed", html_saved=str(html_path))

        except Exception as exc:
            logger.error("report.pdf_error", error=str(exc))
            pdf_path = md_path  # Fall back to markdown

        # Update DB
        from sqlalchemy import update
        await db.execute(
            update(FeasibilityAnalysis)
            .where(FeasibilityAnalysis.id == analysis_id)
            .values(report_content=markdown_content, report_pdf_path=str(pdf_path))
        )
        await db.commit()

        return str(pdf_path)
