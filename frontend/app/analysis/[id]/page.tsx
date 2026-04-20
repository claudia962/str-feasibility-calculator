'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Comp = { comp_name: string | null; distance_km: number | null; bedrooms: number | null; avg_adr: number | null; occupancy_rate: number | null; similarity_score: number | null; data_source: string }
type Financials = { projection_type: string; year1_gross_revenue: number | null; noi: number | null; cap_rate: number | null; cash_on_cash_return: number | null; break_even_occupancy: number | null; mc_revenue_p10?: number | null; mc_revenue_p50?: number | null; mc_revenue_p90?: number | null; annual_expenses?: Record<string, number> }
type Neighbourhood = { walk_score: number | null; transit_score: number | null; nearest_airport_km: number | null; nearest_beach_km: number | null; nearest_downtown_km: number | null; restaurants_within_1km: number | null; neighborhood_score: number | null; best_for: string[] }
type StressTest = { scenario_name: string; revenue_impact_pct: number | null; still_profitable: boolean | null; adaptation_strategy: string | null }
type Analysis = {
  id: string; status: string; address: string; created_at: string;
  overall_feasibility_score: number | null; recommendation: string | null;
  neighborhood: Neighbourhood | null; comps: Comp[]; financials: Financials | null;
  steps_complete: string[]
}

const STEPS = ['geocoded','neighbourhood','comps','financials','stress_tests','complete']
const REC_COLORS: Record<string, string> = { strong_buy: 'bg-emerald-100 text-emerald-800', buy: 'bg-green-100 text-green-800', hold: 'bg-yellow-100 text-yellow-800', avoid: 'bg-orange-100 text-orange-800', strong_avoid: 'bg-red-100 text-red-800' }
const fmt = (n: number | null | undefined, d = 0, pre = '') => n == null ? '—' : `${pre}${n.toLocaleString('en-AU', { minimumFractionDigits: d, maximumFractionDigits: d })}`
const pct = (n: number | null | undefined, d = 1) => n == null ? '—' : `${(n * 100).toFixed(d)}%`

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState('overview')
  const [stressTests, setStressTests] = useState<StressTest[]>([])
  const [renovations, setRenovations] = useState<{ renovation_item: string; estimated_cost: number; roi_1yr_pct: number; recommendation: string }[]>([])

  useEffect(() => {
    if (!id) return
    let stopped = false
    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/feasibility/${id}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json: Analysis = await res.json()
        setData(json)
        if (json.status === 'complete') {
          // Fetch stress tests and renovations separately from extended response
          const extRes = await fetch(`${API}/api/feasibility/${id}`)
          const ext = await extRes.json()
          if (ext.stress_tests) setStressTests(ext.stress_tests)
          if (ext.renovations) setRenovations(ext.renovations)
        }
        if (json.status !== 'complete' && json.status !== 'failed' && !stopped) setTimeout(poll, 3000)
      } catch (e) { setError(e instanceof Error ? e.message : 'Failed to load') }
    }
    poll()
    return () => { stopped = true }
  }, [id])

  if (error) return <div className="p-8 text-red-500 bg-red-50 rounded-xl">Error: {error}</div>
  if (!data) return <div className="p-8 text-slate-400 text-center">Loading...</div>

  const stepsComplete = new Set(data.steps_complete)
  const progress = Math.round((stepsComplete.size / STEPS.length) * 100)
  const fp = data.financials
  const mc_expenses = (fp as unknown as Record<string, unknown>)?.annual_expenses as Record<string, number> | undefined

  const TABS = ['overview','financials','monte_carlo','stress','renovations','comps']
  const TAB_LABELS: Record<string, string> = { overview: 'Overview', financials: 'Financials', monte_carlo: 'Monte Carlo', stress: 'Stress Tests', renovations: 'Renovations', comps: 'Comps' }

  return (
    <div className="space-y-6">
      <div>
        <a href="/" className="text-[#AF7225] text-sm hover:underline">← New Analysis</a>
        <h1 className="text-2xl font-bold text-[#0F172A] mt-1">{data.address}</h1>
        <p className="text-sm text-slate-500 mt-0.5">Analysis ID: {data.id}</p>
      </div>

      {/* Progress */}
      {data.status !== 'complete' && data.status !== 'failed' && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">{data.status === 'pending' ? 'Queued...' : 'Analysing...'}</span>
            <span className="text-sm text-slate-400">{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 mb-3">
            <div className="bg-[#AF7225] h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
          </div>
          <div className="flex gap-3 flex-wrap text-xs text-slate-400">
            {STEPS.map(s => <span key={s} className={stepsComplete.has(s) ? 'text-emerald-600 font-semibold' : ''}>{stepsComplete.has(s) ? '✓' : '○'} {s}</span>)}
          </div>
        </div>
      )}

      {data.status === 'failed' && <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">Analysis failed. Please try again.</div>}

      {/* Hero score card */}
      {data.overall_feasibility_score !== null && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <p className="text-sm text-slate-500 mb-1">Feasibility Score</p>
              <div className="text-5xl font-bold text-[#0F172A]">
                {Math.round(data.overall_feasibility_score)}<span className="text-xl text-slate-400">/100</span>
              </div>
            </div>
            <div className="space-y-2">
              {data.recommendation && (
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${REC_COLORS[data.recommendation] || 'bg-slate-100 text-slate-700'}`}>
                  {data.recommendation.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase())}
                </span>
              )}
            </div>
            {fp && (
              <div className="flex gap-6">
                {[['Gross Revenue', fmt(fp.year1_gross_revenue, 0, '$')], ['NOI', fmt(fp.noi, 0, '$')], ['Cap Rate', pct(fp.cap_rate)]].map(([label, val]) => (
                  <div key={label} className="text-center">
                    <p className="text-xs text-slate-400">{label}</p>
                    <p className={`text-lg font-bold ${label === 'NOI' && (fp.noi ?? 0) < 0 ? 'text-red-600' : 'text-[#0F172A]'}`}>{val}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      {data.status === 'complete' && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="flex border-b border-slate-200 overflow-x-auto">
            {TABS.map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-5 py-3 text-sm whitespace-nowrap transition-colors ${tab === t ? 'tab-active' : 'tab-inactive'}`}>
                {TAB_LABELS[t]}
              </button>
            ))}
          </div>

          <div className="p-6">
            {/* Overview Tab */}
            {tab === 'overview' && (
              <div className="space-y-5">
                {data.neighborhood && (
                  <div>
                    <h3 className="font-semibold text-slate-700 mb-3">Neighbourhood</h3>
                    <div className="grid grid-cols-3 gap-3 mb-4">
                      {[['Walk Score', data.neighborhood.walk_score], ['Transit Score', data.neighborhood.transit_score], ['Nbhd Score', data.neighborhood.neighborhood_score ? Math.round(data.neighborhood.neighborhood_score) : null]].map(([label, val]) => (
                        <div key={String(label)} className="bg-slate-50 rounded-lg p-3 text-center">
                          <p className="text-2xl font-bold text-[#AF7225]">{val ?? '—'}</p>
                          <p className="text-xs text-slate-500 mt-1">{label}</p>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm text-slate-600">
                      <p>✈️ Airport: <span className="font-medium">{fmt(data.neighborhood.nearest_airport_km, 1)} km</span></p>
                      <p>🏙️ CBD: <span className="font-medium">{fmt(data.neighborhood.nearest_downtown_km, 1)} km</span></p>
                      <p>🍽️ Restaurants: <span className="font-medium">{data.neighborhood.restaurants_within_1km ?? '—'}</span></p>
                      {data.neighborhood.best_for?.length > 0 && <p>👥 Best for: <span className="font-medium">{data.neighborhood.best_for.join(', ')}</span></p>}
                    </div>
                  </div>
                )}
                {fp && (
                  <div>
                    <h3 className="font-semibold text-slate-700 mb-3">Key Metrics</h3>
                    <div className="grid grid-cols-2 gap-3">
                      {[['Gross Revenue (Y1)', fmt(fp.year1_gross_revenue, 0, '$')], ['Net Operating Income', fmt(fp.noi, 0, '$')], ['Cap Rate', pct(fp.cap_rate)], ['Cash-on-Cash', pct(fp.cash_on_cash_return)], ['Break-Even Occ', pct(fp.break_even_occupancy, 0)]].map(([label, val]) => (
                        <div key={String(label)} className="flex justify-between items-center py-2 border-b border-slate-50">
                          <span className="text-sm text-slate-500">{label}</span>
                          <span className="text-sm font-semibold text-[#0F172A]">{val}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex gap-3">
                  <a href={`${API}/api/reports/${data.id}/pdf`} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 bg-[#0F172A] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#1e293b] transition-colors">
                    📄 Download Report
                  </a>
                </div>
              </div>
            )}

            {/* Financials Tab */}
            {tab === 'financials' && fp && (
              <div className="space-y-5">
                <h3 className="font-semibold text-slate-700">Financial Summary</h3>
                <div className="grid grid-cols-2 gap-3">
                  {[['Year 1 Gross Revenue', fmt(fp.year1_gross_revenue, 0, '$')], ['Net Operating Income', fmt(fp.noi, 0, '$')], ['Cap Rate', pct(fp.cap_rate)], ['Cash-on-Cash Return', pct(fp.cash_on_cash_return)], ['Break-Even Occupancy', pct(fp.break_even_occupancy, 0)]].map(([label, val]) => (
                    <div key={String(label)} className="flex justify-between items-center py-2.5 border-b border-slate-100">
                      <span className="text-sm text-slate-500">{label}</span>
                      <span className={`text-sm font-semibold ${String(val).startsWith('-') ? 'text-red-600' : 'text-[#0F172A]'}`}>{val}</span>
                    </div>
                  ))}
                </div>
                {mc_expenses && Object.keys(mc_expenses).filter(k => !k.startsWith('mc_')).length > 0 && (
                  <div>
                    <h4 className="font-medium text-slate-600 mb-2 text-sm">Expense Breakdown</h4>
                    {Object.entries(mc_expenses).filter(([k]) => !k.startsWith('mc_')).map(([k, v]) => (
                      <div key={k} className="flex justify-between text-sm py-1">
                        <span className="text-slate-500">{k.replace(/_/g, ' ')}</span>
                        <span className="font-medium">{fmt(v as number, 0, '$')}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Monte Carlo Tab */}
            {tab === 'monte_carlo' && fp && (
              <div className="space-y-5">
                <h3 className="font-semibold text-slate-700">Monte Carlo Simulation (2,000 runs)</h3>
                <div className="grid grid-cols-3 gap-4">
                  {[['P10 (pessimistic)', fp.mc_revenue_p10], ['P50 (median)', fp.mc_revenue_p50], ['P90 (optimistic)', fp.mc_revenue_p90]].map(([label, val]) => (
                    <div key={String(label)} className="bg-slate-50 rounded-lg p-4 text-center">
                      <p className="text-xs text-slate-500 mb-1">{label}</p>
                      <p className="text-xl font-bold text-[#0F172A]">{fmt(val as number | null, 0, '$')}</p>
                    </div>
                  ))}
                </div>
                {mc_expenses?.mc_probability_of_loss !== undefined && (
                  <p className="text-sm text-slate-600">
                    <span className="font-medium">Probability of Loss:</span> {((mc_expenses.mc_probability_of_loss as number) * 100).toFixed(1)}%
                  </p>
                )}
                {mc_expenses?.mc_histogram_bins && Array.isArray(mc_expenses.mc_histogram_bins) && (
                  <div>
                    <h4 className="font-medium text-slate-600 mb-3 text-sm">Revenue Distribution</h4>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={(mc_expenses.mc_histogram_bins as unknown as number[]).map((bin: number, i: number) => ({ bin: `$${Math.round(bin/1000)}k`, count: ((mc_expenses.mc_histogram_counts as unknown as number[]) || [])[i] || 0 }))}>
                        <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Bar dataKey="count" fill="#AF7225" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}

            {/* Stress Tests Tab */}
            {tab === 'stress' && (
              <div>
                <h3 className="font-semibold text-slate-700 mb-3">Stress Test Scenarios</h3>
                {stressTests.length === 0 ? <p className="text-slate-400 text-sm">No stress test data available.</p> : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead><tr className="text-left text-slate-400 text-xs border-b">
                        <th className="pb-2 pr-3">Scenario</th>
                        <th className="pb-2 pr-3">Revenue Impact</th>
                        <th className="pb-2 pr-3">Profitable?</th>
                        <th className="pb-2">Adaptation</th>
                      </tr></thead>
                      <tbody>{stressTests.map((st, i) => (
                        <tr key={i} className="border-b border-slate-50">
                          <td className="py-2 pr-3 font-medium text-slate-700">{st.scenario_name}</td>
                          <td className={`py-2 pr-3 ${(st.revenue_impact_pct ?? 0) < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                            {st.revenue_impact_pct != null ? `${((st.revenue_impact_pct) * 100).toFixed(1)}%` : '—'}
                          </td>
                          <td className="py-2 pr-3">{st.still_profitable === true ? '✅' : st.still_profitable === false ? '🚫' : '—'}</td>
                          <td className="py-2 text-slate-500 text-xs max-w-xs truncate">{st.adaptation_strategy?.slice(0, 80)}...</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Renovations Tab */}
            {tab === 'renovations' && (
              <div>
                <h3 className="font-semibold text-slate-700 mb-3">Renovation Opportunities</h3>
                {renovations.length === 0 ? <p className="text-slate-400 text-sm">No renovation data available.</p> : (
                  <table className="w-full text-sm">
                    <thead><tr className="text-left text-slate-400 text-xs border-b">
                      <th className="pb-2 pr-3">Item</th><th className="pb-2 pr-3">Cost</th><th className="pb-2 pr-3">ROI</th><th className="pb-2">Recommendation</th>
                    </tr></thead>
                    <tbody>{renovations.map((r, i) => {
                      const recColor: Record<string, string> = { highly_recommended: 'text-emerald-600', recommended: 'text-green-600', marginal: 'text-yellow-600', not_recommended: 'text-red-500' }
                      return (
                        <tr key={i} className="border-b border-slate-50">
                          <td className="py-2 pr-3 font-medium">{r.renovation_item.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</td>
                          <td className="py-2 pr-3">{fmt(r.estimated_cost, 0, '$')}</td>
                          <td className="py-2 pr-3">{r.roi_1yr_pct != null ? `${(r.roi_1yr_pct * 100).toFixed(0)}%` : '—'}</td>
                          <td className={`py-2 text-xs font-medium ${recColor[r.recommendation] || 'text-slate-500'}`}>{r.recommendation?.replace(/_/g, ' ')}</td>
                        </tr>
                      )
                    })}</tbody>
                  </table>
                )}
              </div>
            )}

            {/* Comps Tab */}
            {tab === 'comps' && (
              <div>
                <h3 className="font-semibold text-slate-700 mb-1">Comparable Properties</h3>
                {data.comps?.[0]?.data_source === 'mock' && <p className="text-xs text-amber-600 mb-3">Demo data — live data from Inside Airbnb / Airbnb search</p>}
                {data.comps?.[0]?.data_source && data.comps[0].data_source !== 'mock' && <p className="text-xs text-emerald-600 mb-3">Source: {data.comps[0].data_source}</p>}
                {data.comps.length === 0 ? <p className="text-slate-400 text-sm">No comp data.</p> : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead><tr className="text-left text-slate-400 text-xs border-b">
                        <th className="pb-2 pr-3">Property</th><th className="pb-2 pr-3">Dist</th><th className="pb-2 pr-3">BR</th><th className="pb-2 pr-3">ADR</th><th className="pb-2 pr-3">Occ</th><th className="pb-2">Sim</th>
                      </tr></thead>
                      <tbody>{data.comps.slice(0, 10).map((c, i) => (
                        <tr key={i} className="border-b border-slate-50">
                          <td className="py-2 pr-3 text-slate-700">{(c.comp_name || `Comp ${i+1}`).slice(0, 35)}</td>
                          <td className="py-2 pr-3 text-slate-500">{fmt(c.distance_km, 1)} km</td>
                          <td className="py-2 pr-3 text-slate-500">{c.bedrooms ?? '—'}</td>
                          <td className="py-2 pr-3 font-medium">{fmt(c.avg_adr, 0, '$')}</td>
                          <td className="py-2 pr-3">{c.occupancy_rate != null ? `${(c.occupancy_rate * 100).toFixed(0)}%` : '—'}</td>
                          <td className="py-2 text-slate-500">{c.similarity_score?.toFixed(2) ?? '—'}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
