"""SQLAlchemy ORM models for all feasibility tables."""
import uuid
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator, TEXT
import json as _json
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class Property(Base):
    __tablename__ = "properties"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    address = Column(Text)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(3, 1))
    property_type = Column(String(50))
    purchase_price = Column(Numeric(14, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_ = Column("metadata", JSON, default=dict)
    feasibility_analyses = relationship("FeasibilityAnalysis", back_populates="property")


class Event(Base):
    __tablename__ = "events"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    event_type = Column(String(100))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    radius_impact_km = Column(Numeric(6, 2), default=Decimal("10.0"))
    metadata_ = Column("metadata", JSON, default=dict)


class MarketSignal(Base):
    __tablename__ = "market_signals"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    signal_type = Column(String(100))
    market = Column(String(200))
    value = Column(Numeric(12, 4))
    metadata_ = Column("metadata", JSON, default=dict)


class ModelMetric(Base):
    __tablename__ = "model_metrics"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    product = Column(String(50), default="feasibility")
    metric_name = Column(String(200))
    metric_value = Column(Numeric(12, 6))
    property_id = Column(Uuid(as_uuid=True), ForeignKey("properties.id"))
    metadata_ = Column("metadata", JSON, default=dict)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flag_name = Column(String(200), unique=True, nullable=False)
    enabled = Column(Boolean, default=False)
    description = Column(Text)
    toggled_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_ = Column("metadata", JSON, default=dict)


class FeasibilityAnalysis(Base):
    __tablename__ = "feasibility_analyses"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(Uuid(as_uuid=True), ForeignKey("properties.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String(200))
    status = Column(String(20), default="pending")
    address = Column(Text, nullable=False)
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    property_type = Column(String(50))
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(3, 1))
    purchase_price = Column(Numeric(14, 2))
    estimated_renovation = Column(Numeric(12, 2))
    down_payment_pct = Column(Numeric(5, 2), default=Decimal("20.0"))
    mortgage_rate_pct = Column(Numeric(5, 3))
    mortgage_term_years = Column(Integer, default=30)
    overall_feasibility_score = Column(Numeric(4, 2))
    risk_score = Column(Numeric(4, 2))
    recommendation = Column(String(50))
    recommendation_reasoning = Column(Text)
    report_content = Column(Text)
    report_pdf_path = Column(String(500))
    metadata_ = Column("metadata", JSON, default=dict)

    property = relationship("Property", back_populates="feasibility_analyses")
    comp_analyses = relationship("CompAnalysis", back_populates="feasibility", cascade="all, delete-orphan")
    regulation_assessments = relationship("RegulationAssessment", back_populates="feasibility", cascade="all, delete-orphan")
    neighborhood_scores = relationship("NeighborhoodScore", back_populates="feasibility", cascade="all, delete-orphan")
    financial_projections = relationship("FinancialProjection", back_populates="feasibility", cascade="all, delete-orphan")
    stress_tests = relationship("FeasibilityStressTest", back_populates="feasibility", cascade="all, delete-orphan")
    supply_pipeline = relationship("SupplyPipeline", back_populates="feasibility", cascade="all, delete-orphan")
    portfolio_fit = relationship("PortfolioFit", back_populates="feasibility", cascade="all, delete-orphan")
    renovation_analyses = relationship("RenovationAnalysis", back_populates="feasibility", cascade="all, delete-orphan")
    exit_strategies = relationship("ExitStrategy", back_populates="feasibility", cascade="all, delete-orphan")


class CompAnalysis(Base):
    __tablename__ = "comp_analyses"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    comp_listing_id = Column(String(200))
    comp_name = Column(String(500))
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    distance_km = Column(Numeric(6, 2))
    bedrooms = Column(Integer)
    property_type = Column(String(50))
    annual_revenue = Column(Numeric(12, 2))
    avg_adr = Column(Numeric(10, 2))
    occupancy_rate = Column(Numeric(5, 2))
    avg_review_score = Column(Numeric(3, 1))
    similarity_score = Column(Numeric(4, 3))
    monthly_revenue = Column(JSON)
    monthly_occupancy = Column(JSON)
    monthly_adr = Column(JSON)
    data_source = Column(String(50), default="mock")
    feasibility = relationship("FeasibilityAnalysis", back_populates="comp_analyses")


class RegulationAssessment(Base):
    __tablename__ = "regulation_assessments"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    municipality = Column(String(300))
    str_allowed = Column(Boolean)
    permit_required = Column(Boolean)
    max_nights_per_year = Column(Integer)
    regulation_risk_score = Column(Numeric(4, 2))
    last_verified = Column(DateTime(timezone=True))
    notes = Column(Text)
    feasibility = relationship("FeasibilityAnalysis", back_populates="regulation_assessments")


class NeighborhoodScore(Base):
    __tablename__ = "neighborhood_scores"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    walk_score = Column(Integer)
    transit_score = Column(Integer)
    bike_score = Column(Integer)
    nearest_airport_km = Column(Numeric(6, 2))
    nearest_airport_name = Column(String(200))
    nearest_beach_km = Column(Numeric(6, 2))
    nearest_downtown_km = Column(Numeric(6, 2))
    restaurants_within_1km = Column(Integer)
    grocery_within_1km = Column(Integer)
    neighborhood_score = Column(Numeric(4, 2))
    best_for = Column(JSON)
    feasibility = relationship("FeasibilityAnalysis", back_populates="neighborhood_scores")


class FinancialProjection(Base):
    __tablename__ = "financial_projections"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    projection_type = Column(String(50))
    year1_gross_revenue = Column(Numeric(12, 2))
    year2_gross_revenue = Column(Numeric(12, 2))
    year3_gross_revenue = Column(Numeric(12, 2))
    noi = Column(Numeric(12, 2))
    cap_rate = Column(Numeric(5, 3))
    cash_on_cash_return = Column(Numeric(5, 3))
    break_even_occupancy = Column(Numeric(5, 2))
    monthly_projections = Column(JSON)
    annual_expenses = Column(JSON)
    mc_revenue_p10 = Column(Numeric(12, 2))
    mc_revenue_p25 = Column(Numeric(12, 2))
    mc_revenue_p50 = Column(Numeric(12, 2))
    mc_revenue_p75 = Column(Numeric(12, 2))
    mc_revenue_p90 = Column(Numeric(12, 2))
    feasibility = relationship("FeasibilityAnalysis", back_populates="financial_projections")


class FeasibilityStressTest(Base):
    __tablename__ = "feasibility_stress_tests"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    scenario_name = Column(String(200), nullable=False)
    scenario_type = Column(String(50))
    parameters = Column(JSON, nullable=False)
    revenue_impact_pct = Column(Numeric(8, 4))
    still_profitable = Column(Boolean)
    adaptation_strategy = Column(Text)
    feasibility = relationship("FeasibilityAnalysis", back_populates="stress_tests")


class SupplyPipeline(Base):
    __tablename__ = "supply_pipeline"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    new_listings_last_12mo = Column(Integer)
    supply_growth_pct_12mo = Column(Numeric(5, 2))
    source_data = Column(JSON)
    feasibility = relationship("FeasibilityAnalysis", back_populates="supply_pipeline")


class PortfolioFit(Base):
    __tablename__ = "portfolio_fit"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    existing_property_count = Column(Integer)
    overall_portfolio_fit_score = Column(Numeric(4, 2))
    recommendation = Column(Text)
    feasibility = relationship("FeasibilityAnalysis", back_populates="portfolio_fit")


class RenovationAnalysis(Base):
    __tablename__ = "renovation_analyses"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    renovation_item = Column(String(200), nullable=False)
    estimated_cost = Column(Numeric(10, 2))
    roi_1yr_pct = Column(Numeric(8, 4))
    recommendation = Column(String(50))
    reasoning = Column(Text)
    feasibility = relationship("FeasibilityAnalysis", back_populates="renovation_analyses")


class ExitStrategy(Base):
    __tablename__ = "exit_strategies"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feasibility_id = Column(Uuid(as_uuid=True), ForeignKey("feasibility_analyses.id"), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    estimated_monthly_income = Column(Numeric(10, 2))
    estimated_annual_return = Column(Numeric(5, 3))
    notes = Column(Text)
    feasibility = relationship("FeasibilityAnalysis", back_populates="exit_strategies")


class FeasibilityKnowledge(Base):
    __tablename__ = "feasibility_knowledge"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(50))
    source_name = Column(String(500))
    chunk_text = Column(Text, nullable=False)
    topic_tags = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
