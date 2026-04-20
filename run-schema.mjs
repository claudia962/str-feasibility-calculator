import { readFileSync } from 'fs';
import https from 'https';

const token = 'sbp_541ec1b3cce5bb3d627c57c5ae5fdb1e114a492c';
const PROJECT = 'eywxieynkuioyycgnbbe';

function q(sql) {
  return new Promise((resolve) => {
    const body = JSON.stringify({query: sql});
    const opts = {hostname:'api.supabase.com',path:`/v1/projects/${PROJECT}/database/query`,method:'POST',headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json','Content-Length':Buffer.byteLength(body),'User-Agent':'claudia-code'}};
    const req = https.request(opts,r=>{let b='';r.on('data',d=>b+=d);r.on('end',()=>resolve({s:r.statusCode,b}))});
    req.on('error',e=>resolve({s:0,b:e.message}));
    req.write(body);req.end();
  });
}

const stmts = [
  `CREATE TABLE IF NOT EXISTS properties (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(500) NOT NULL, address TEXT, latitude DECIMAL(10,7), longitude DECIMAL(10,7), bedrooms INTEGER, bathrooms DECIMAL(3,1), property_type VARCHAR(50), purchase_price DECIMAL(14,2), created_at TIMESTAMPTZ DEFAULT NOW(), metadata JSONB DEFAULT '{}')`,
  `CREATE TABLE IF NOT EXISTS events (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(500) NOT NULL, event_type VARCHAR(100), start_date DATE NOT NULL, end_date DATE NOT NULL, latitude DECIMAL(10,7), longitude DECIMAL(10,7), radius_impact_km DECIMAL(6,2) DEFAULT 10.0, metadata JSONB DEFAULT '{}')`,
  `CREATE TABLE IF NOT EXISTS market_signals (id BIGSERIAL PRIMARY KEY, captured_at TIMESTAMPTZ DEFAULT NOW(), signal_type VARCHAR(100), market VARCHAR(200), value DECIMAL(12,4), metadata JSONB DEFAULT '{}')`,
  `CREATE TABLE IF NOT EXISTS feature_flags (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), flag_name VARCHAR(200) UNIQUE NOT NULL, enabled BOOLEAN DEFAULT FALSE, description TEXT, toggled_at TIMESTAMPTZ DEFAULT NOW(), metadata JSONB DEFAULT '{}')`,
  `INSERT INTO feature_flags (flag_name,enabled,description) VALUES ('FEASIBILITY_AUTO_REFRESH',TRUE,'Monthly auto-refresh') ON CONFLICT (flag_name) DO NOTHING`,
  `CREATE TABLE IF NOT EXISTS feasibility_analyses (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), property_id UUID REFERENCES properties(id), created_at TIMESTAMPTZ DEFAULT NOW(), created_by VARCHAR(200), status VARCHAR(20) DEFAULT 'pending', address TEXT NOT NULL, latitude DECIMAL(10,7), longitude DECIMAL(10,7), property_type VARCHAR(50), bedrooms INTEGER, bathrooms DECIMAL(3,1), purchase_price DECIMAL(14,2), estimated_renovation DECIMAL(12,2), down_payment_pct DECIMAL(5,2) DEFAULT 20.0, mortgage_rate_pct DECIMAL(5,3), mortgage_term_years INTEGER DEFAULT 30, overall_feasibility_score DECIMAL(4,2), risk_score DECIMAL(4,2), recommendation VARCHAR(50), recommendation_reasoning TEXT, report_content TEXT, report_pdf_path VARCHAR(500), metadata JSONB DEFAULT '{}')`,
  `CREATE INDEX IF NOT EXISTS ix_fa_status ON feasibility_analyses(status)`,
  `CREATE TABLE IF NOT EXISTS comp_analyses (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), comp_listing_id VARCHAR(200), comp_name VARCHAR(500), latitude DECIMAL(10,7), longitude DECIMAL(10,7), distance_km DECIMAL(6,2), bedrooms INTEGER, property_type VARCHAR(50), annual_revenue DECIMAL(12,2), avg_adr DECIMAL(10,2), occupancy_rate DECIMAL(5,2), avg_review_score DECIMAL(3,1), similarity_score DECIMAL(4,3), monthly_revenue JSONB, monthly_occupancy JSONB, monthly_adr JSONB, data_source VARCHAR(50) DEFAULT 'mock')`,
  `CREATE TABLE IF NOT EXISTS regulation_assessments (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), municipality VARCHAR(300), str_allowed BOOLEAN, permit_required BOOLEAN, max_nights_per_year INTEGER, regulation_risk_score DECIMAL(4,2), pending_legislation TEXT, enforcement_level VARCHAR(50), last_verified TIMESTAMPTZ, notes TEXT)`,
  `CREATE TABLE IF NOT EXISTS neighborhood_scores (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), walk_score INTEGER, transit_score INTEGER, bike_score INTEGER, nearest_airport_km DECIMAL(6,2), nearest_airport_name VARCHAR(200), nearest_beach_km DECIMAL(6,2), nearest_downtown_km DECIMAL(6,2), restaurants_within_1km INTEGER, grocery_within_1km INTEGER, neighborhood_score DECIMAL(4,2), best_for TEXT[])`,
  `CREATE TABLE IF NOT EXISTS financial_projections (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), projection_type VARCHAR(50), year1_gross_revenue DECIMAL(12,2), year2_gross_revenue DECIMAL(12,2), year3_gross_revenue DECIMAL(12,2), noi DECIMAL(12,2), cap_rate DECIMAL(5,3), cash_on_cash_return DECIMAL(5,3), break_even_occupancy DECIMAL(5,2), monthly_projections JSONB, annual_expenses JSONB, mc_revenue_p10 DECIMAL(12,2), mc_revenue_p25 DECIMAL(12,2), mc_revenue_p50 DECIMAL(12,2), mc_revenue_p75 DECIMAL(12,2), mc_revenue_p90 DECIMAL(12,2))`,
  `CREATE TABLE IF NOT EXISTS feasibility_stress_tests (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), scenario_name VARCHAR(200) NOT NULL, scenario_type VARCHAR(50), parameters JSONB NOT NULL, revenue_impact_pct DECIMAL(8,4), still_profitable BOOLEAN, adaptation_strategy TEXT)`,
  `CREATE TABLE IF NOT EXISTS supply_pipeline (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), new_listings_last_12mo INTEGER, supply_growth_pct_12mo DECIMAL(5,2), source_data JSONB)`,
  `CREATE TABLE IF NOT EXISTS portfolio_fit (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), existing_property_count INTEGER, overall_portfolio_fit_score DECIMAL(4,2), recommendation TEXT)`,
  `CREATE TABLE IF NOT EXISTS renovation_analyses (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), renovation_item VARCHAR(200) NOT NULL, estimated_cost DECIMAL(10,2), roi_1yr_pct DECIMAL(8,4), recommendation VARCHAR(50), reasoning TEXT)`,
  `CREATE TABLE IF NOT EXISTS exit_strategies (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feasibility_id UUID NOT NULL REFERENCES feasibility_analyses(id), strategy_type VARCHAR(50) NOT NULL, estimated_monthly_income DECIMAL(10,2), estimated_annual_return DECIMAL(5,3), notes TEXT)`,
  `CREATE TABLE IF NOT EXISTS feasibility_knowledge (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_type VARCHAR(50), source_name VARCHAR(500), chunk_text TEXT NOT NULL, topic_tags TEXT[], created_at TIMESTAMPTZ DEFAULT NOW())`,
];

let ok=0, fail=0;
for (const [i,sql] of stmts.entries()) {
  const r = await q(sql);
  const label = sql.slice(0,50).replace(/\n/g,' ');
  if (r.s >= 200 && r.s < 300) { console.log(`  ✓ [${i+1}/${stmts.length}]`); ok++; }
  else if (r.b.includes('already exists')||r.b.includes('duplicate')) { console.log(`  ~ [${i+1}/${stmts.length}] already exists`); ok++; }
  else { console.log(`  ✗ [${i+1}/${stmts.length}] ${r.s}: ${r.b.slice(0,150)}`); fail++; }
}
console.log(`\nDone: ${ok} OK, ${fail} failed`);
