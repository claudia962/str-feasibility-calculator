"""
Monte Carlo simulation engine.
Samples from actual comp distributions rather than assumed normal distributions.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.services.airdna_client import CompData
from app.services.financial_engine import MONTHS, ProFormaInputs, _monthly_mortgage


@dataclass
class MCResult:
    n_simulations: int

    # Revenue percentiles
    revenue_p10: float
    revenue_p25: float
    revenue_p50: float
    revenue_p75: float
    revenue_p90: float

    # NOI percentiles
    noi_p10: float
    noi_p25: float
    noi_p50: float
    noi_p75: float
    noi_p90: float

    # Cash-on-cash distribution
    coc_p10: float
    coc_p25: float
    coc_p50: float
    coc_p75: float
    coc_p90: float

    probability_of_loss: float    # % of sims where NOI < 0
    mean_revenue: float
    std_revenue: float

    # Histogram data for frontend chart (20 bins)
    histogram_bins: list[float]
    histogram_counts: list[int]

    def as_dict(self) -> dict:
        return {k: (round(v, 2) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


class MonteCarloEngine:
    """Monte Carlo simulation using actual comp distribution sampling."""

    def run_simulation(
        self,
        comp_set: list[CompData],
        inputs: ProFormaInputs,
        n_sims: int = 2000,
        seed: Optional[int] = None,
    ) -> MCResult:
        """
        Run Monte Carlo simulation sampling from actual comp set.

        Sampling strategy:
        - ADR: np.random.choice from actual comp ADR values (with replacement)
        - Occupancy: beta distribution fitted to comp occupancy range
        - Expenses: uniform ±15% around base estimates
        """
        rng = np.random.default_rng(seed)

        # Extract comp data for sampling
        comp_adrs = np.array([c.avg_adr for c in comp_set if c.avg_adr and c.avg_adr > 0]) if comp_set else None
        comp_occs = np.array([c.occupancy_rate for c in comp_set if c.occupancy_rate and c.occupancy_rate > 0]) if comp_set else None

        if comp_adrs is None or len(comp_adrs) == 0:
            comp_adrs = np.array([inputs.avg_adr * x for x in [0.7, 0.85, 1.0, 1.15, 1.3]])
        if comp_occs is None or len(comp_occs) == 0:
            comp_occs = np.array([inputs.avg_occupancy * x for x in [0.7, 0.85, 1.0, 1.10, 1.15]])

        comp_occs = np.clip(comp_occs, 0.01, 0.99)

        # Fit beta distribution to comp occupancy data
        occ_mean = float(np.mean(comp_occs))
        occ_var = float(np.var(comp_occs))
        if occ_var > 0 and occ_mean > 0 and occ_mean < 1:
            alpha = occ_mean * (occ_mean * (1 - occ_mean) / occ_var - 1)
            beta_param = (1 - occ_mean) * (occ_mean * (1 - occ_mean) / occ_var - 1)
            alpha = max(0.5, alpha)
            beta_param = max(0.5, beta_param)
        else:
            alpha, beta_param = 5.0, 3.0  # Sensible defaults

        # Fixed inputs
        loan_amount = inputs.purchase_price * (1 - inputs.down_payment_pct / 100)
        monthly_mortgage = _monthly_mortgage(loan_amount, inputs.mortgage_rate_pct / 100, inputs.mortgage_term_years)
        annual_mortgage = monthly_mortgage * 12
        cash_invested = inputs.purchase_price * (inputs.down_payment_pct / 100) + inputs.estimated_renovation

        base_fixed_expenses = (
            inputs.purchase_price * 0.005 +   # insurance
            inputs.purchase_price * 0.01 +    # maintenance
            inputs.purchase_price * 0.0035 +  # property tax
            200 * 12                           # utilities base
        )

        revenues = np.zeros(n_sims)
        nois = np.zeros(n_sims)
        cocs = np.zeros(n_sims)

        for i in range(n_sims):
            # Sample ADR from comp distribution
            sim_adr = float(rng.choice(comp_adrs))

            # Sample occupancy from fitted beta distribution
            sim_occ = float(rng.beta(alpha, beta_param))
            sim_occ = np.clip(sim_occ, 0.3, 0.97)

            # Apply seasonal curve from inputs
            gross = 0.0
            occupied_nights = 0.0
            for month in MONTHS:
                base_occ = inputs.monthly_occupancy.get(month, inputs.avg_occupancy)
                seasonal_factor = base_occ / inputs.avg_occupancy if inputs.avg_occupancy > 0 else 1.0
                month_occ = min(0.97, sim_occ * seasonal_factor)

                base_adr = inputs.monthly_adr.get(month, inputs.avg_adr)
                adr_seasonal_factor = base_adr / inputs.avg_adr if inputs.avg_adr > 0 else 1.0
                month_adr = sim_adr * adr_seasonal_factor

                import calendar
                days = calendar.monthrange(2024, list(inputs.monthly_adr.keys()).index(month) + 1 if month in inputs.monthly_adr else MONTHS.index(month) + 1)[1]
                gross += month_adr * month_occ * days
                occupied_nights += month_occ * days

            # Variable expenses with ±15% noise
            expense_noise = float(rng.uniform(0.85, 1.15))
            platform_fee = gross * 0.155 * expense_noise
            cleaning = (occupied_nights / 2.5) * 85 * expense_noise
            supplies = occupied_nights * 8 * expense_noise
            utilities_variable = occupied_nights * 2 * expense_noise
            fixed_exp = base_fixed_expenses * expense_noise

            total_operating = platform_fee + cleaning + supplies + utilities_variable + fixed_exp
            noi = gross - total_operating
            coc = (noi - annual_mortgage) / cash_invested if cash_invested > 0 else 0

            revenues[i] = gross
            nois[i] = noi
            cocs[i] = coc

        # Percentiles
        prob_loss = float(np.mean(nois < 0))

        # Histogram (20 bins over revenue distribution)
        hist_counts, hist_edges = np.histogram(revenues, bins=20)
        hist_bins = [round(float(e), 0) for e in hist_edges[:-1]]

        return MCResult(
            n_simulations=n_sims,
            revenue_p10=round(float(np.percentile(revenues, 10)), 2),
            revenue_p25=round(float(np.percentile(revenues, 25)), 2),
            revenue_p50=round(float(np.percentile(revenues, 50)), 2),
            revenue_p75=round(float(np.percentile(revenues, 75)), 2),
            revenue_p90=round(float(np.percentile(revenues, 90)), 2),
            noi_p10=round(float(np.percentile(nois, 10)), 2),
            noi_p25=round(float(np.percentile(nois, 25)), 2),
            noi_p50=round(float(np.percentile(nois, 50)), 2),
            noi_p75=round(float(np.percentile(nois, 75)), 2),
            noi_p90=round(float(np.percentile(nois, 90)), 2),
            coc_p10=round(float(np.percentile(cocs, 10)), 4),
            coc_p25=round(float(np.percentile(cocs, 25)), 4),
            coc_p50=round(float(np.percentile(cocs, 50)), 4),
            coc_p75=round(float(np.percentile(cocs, 75)), 4),
            coc_p90=round(float(np.percentile(cocs, 90)), 4),
            probability_of_loss=round(prob_loss, 4),
            mean_revenue=round(float(np.mean(revenues)), 2),
            std_revenue=round(float(np.std(revenues)), 2),
            histogram_bins=hist_bins,
            histogram_counts=[int(c) for c in hist_counts],
        )
