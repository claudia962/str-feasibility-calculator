"""001 initial schema — all tables.
Revision ID: 001_initial_schema
Revises:
Create Date: 2026-04-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table("properties",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("address", sa.Text), sa.Column("latitude", sa.Numeric(10, 7)), sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("bedrooms", sa.Integer), sa.Column("bathrooms", sa.Numeric(3, 1)), sa.Column("property_type", sa.String(50)),
        sa.Column("purchase_price", sa.Numeric(14, 2)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", JSONB, server_default="{}"),
    )
    op.create_table("events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(500), nullable=False), sa.Column("event_type", sa.String(100)),
        sa.Column("start_date", sa.Date, nullable=False), sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7)), sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("radius_impact_km", sa.Numeric(6, 2), server_default="10.0"),
        sa.Column("metadata", JSONB, server_default="{}"),
    )
    op.create_table("market_signals",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("signal_type", sa.String(100)), sa.Column("market", sa.String(200)),
        sa.Column("value", sa.Numeric(12, 4)), sa.Column("metadata", JSONB, server_default="{}"),
    )
    op.execute("SELECT create_hypertable('market_signals', 'captured_at', if_not_exists => TRUE)")

    op.create_table("feature_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("flag_name", sa.String(200), unique=True, nullable=False),
        sa.Column("enabled", sa.Boolean, server_default="false"),
        sa.Column("description", sa.Text),
        sa.Column("toggled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("metadata", JSONB, server_default="{}"),
    )
    op.execute("INSERT INTO feature_flags (flag_name, enabled, description) VALUES ('FEASIBILITY_AUTO_REFRESH', TRUE, 'Monthly auto-refresh') ON CONFLICT DO NOTHING")

    op.create_table("feasibility_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("property_id", UUID(as_uuid=True), sa.ForeignKey("properties.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.String(200)), sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("address", sa.Text, nullable=False), sa.Column("latitude", sa.Numeric(10, 7)), sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("property_type", sa.String(50)), sa.Column("bedrooms", sa.Integer), sa.Column("bathrooms", sa.Numeric(3, 1)),
        sa.Column("purchase_price", sa.Numeric(14, 2)), sa.Column("estimated_renovation", sa.Numeric(12, 2)),
        sa.Column("down_payment_pct", sa.Numeric(5, 2), server_default="20.0"),
        sa.Column("mortgage_rate_pct", sa.Numeric(5, 3)), sa.Column("mortgage_term_years", sa.Integer, server_default="30"),
        sa.Column("overall_feasibility_score", sa.Numeric(4, 2)), sa.Column("risk_score", sa.Numeric(4, 2)),
        sa.Column("recommendation", sa.String(50)), sa.Column("recommendation_reasoning", sa.Text),
        sa.Column("report_content", sa.Text), sa.Column("report_pdf_path", sa.String(500)),
        sa.Column("metadata", JSONB, server_default="{}"),
    )
    op.create_index("ix_fa_status", "feasibility_analyses", ["status"])

    for tbl, fk_cols in [
        ("comp_analyses", [sa.Column("comp_listing_id", sa.String(200)), sa.Column("comp_name", sa.String(500)),
            sa.Column("latitude", sa.Numeric(10, 7)), sa.Column("longitude", sa.Numeric(10, 7)),
            sa.Column("distance_km", sa.Numeric(6, 2)), sa.Column("bedrooms", sa.Integer),
            sa.Column("property_type", sa.String(50)), sa.Column("annual_revenue", sa.Numeric(12, 2)),
            sa.Column("avg_adr", sa.Numeric(10, 2)), sa.Column("occupancy_rate", sa.Numeric(5, 2)),
            sa.Column("avg_review_score", sa.Numeric(3, 1)), sa.Column("similarity_score", sa.Numeric(4, 3)),
            sa.Column("monthly_revenue", JSONB), sa.Column("monthly_occupancy", JSONB), sa.Column("monthly_adr", JSONB),
            sa.Column("data_source", sa.String(50), server_default="mock")]),
        ("regulation_assessments", [sa.Column("municipality", sa.String(300)), sa.Column("str_allowed", sa.Boolean),
            sa.Column("permit_required", sa.Boolean), sa.Column("max_nights_per_year", sa.Integer),
            sa.Column("regulation_risk_score", sa.Numeric(4, 2)), sa.Column("last_verified", sa.DateTime(timezone=True)),
            sa.Column("notes", sa.Text)]),
        ("neighborhood_scores", [sa.Column("walk_score", sa.Integer), sa.Column("transit_score", sa.Integer),
            sa.Column("bike_score", sa.Integer), sa.Column("nearest_airport_km", sa.Numeric(6, 2)),
            sa.Column("nearest_airport_name", sa.String(200)), sa.Column("nearest_beach_km", sa.Numeric(6, 2)),
            sa.Column("nearest_downtown_km", sa.Numeric(6, 2)), sa.Column("restaurants_within_1km", sa.Integer),
            sa.Column("grocery_within_1km", sa.Integer), sa.Column("neighborhood_score", sa.Numeric(4, 2)),
            sa.Column("best_for", ARRAY(sa.Text))]),
        ("financial_projections", [sa.Column("projection_type", sa.String(50)),
            sa.Column("year1_gross_revenue", sa.Numeric(12, 2)), sa.Column("noi", sa.Numeric(12, 2)),
            sa.Column("cap_rate", sa.Numeric(5, 3)), sa.Column("cash_on_cash_return", sa.Numeric(5, 3)),
            sa.Column("break_even_occupancy", sa.Numeric(5, 2)), sa.Column("monthly_projections", JSONB),
            sa.Column("annual_expenses", JSONB), sa.Column("mc_revenue_p10", sa.Numeric(12, 2)),
            sa.Column("mc_revenue_p25", sa.Numeric(12, 2)), sa.Column("mc_revenue_p50", sa.Numeric(12, 2)),
            sa.Column("mc_revenue_p75", sa.Numeric(12, 2)), sa.Column("mc_revenue_p90", sa.Numeric(12, 2))]),
        ("feasibility_stress_tests", [sa.Column("scenario_name", sa.String(200), nullable=False),
            sa.Column("scenario_type", sa.String(50)), sa.Column("parameters", JSONB, nullable=False),
            sa.Column("revenue_impact_pct", sa.Numeric(8, 4)), sa.Column("still_profitable", sa.Boolean),
            sa.Column("adaptation_strategy", sa.Text)]),
        ("supply_pipeline", [sa.Column("new_listings_last_12mo", sa.Integer),
            sa.Column("supply_growth_pct_12mo", sa.Numeric(5, 2)), sa.Column("source_data", JSONB)]),
        ("portfolio_fit", [sa.Column("existing_property_count", sa.Integer),
            sa.Column("overall_portfolio_fit_score", sa.Numeric(4, 2)), sa.Column("recommendation", sa.Text)]),
        ("renovation_analyses", [sa.Column("renovation_item", sa.String(200), nullable=False),
            sa.Column("estimated_cost", sa.Numeric(10, 2)), sa.Column("roi_1yr_pct", sa.Numeric(8, 4)),
            sa.Column("recommendation", sa.String(50)), sa.Column("reasoning", sa.Text)]),
        ("exit_strategies", [sa.Column("strategy_type", sa.String(50), nullable=False),
            sa.Column("estimated_monthly_income", sa.Numeric(10, 2)),
            sa.Column("estimated_annual_return", sa.Numeric(5, 3)), sa.Column("notes", sa.Text)]),
    ]:
        op.create_table(tbl,
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("feasibility_id", UUID(as_uuid=True), sa.ForeignKey("feasibility_analyses.id"), nullable=False),
            *fk_cols,
        )

    op.create_table("feasibility_knowledge",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_type", sa.String(50)), sa.Column("source_name", sa.String(500)),
        sa.Column("chunk_text", sa.Text, nullable=False), sa.Column("topic_tags", ARRAY(sa.Text)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for tbl in ["feasibility_knowledge", "exit_strategies", "renovation_analyses", "portfolio_fit",
                "supply_pipeline", "feasibility_stress_tests", "financial_projections",
                "neighborhood_scores", "regulation_assessments", "comp_analyses",
                "feasibility_analyses", "feature_flags", "market_signals", "events", "properties"]:
        op.drop_table(tbl)
