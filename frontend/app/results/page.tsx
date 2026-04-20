'use client'
import { useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

// Melbourne market data by bedroom count (Inside Airbnb Sep 2025 calibrated)
const MARKET_DATA: Record<number, { adr: number; occupancy: number; annual: number; active: number }> = {
  1: { adr: 195, occupancy: 0.67, annual: 47700, active: 3200 },
  2: { adr: 248, occupancy: 0.65, annual: 58900, active: 2100 },
  3: { adr: 320, occupancy: 0.61, annual: 71200, active: 890 },
  4: { adr: 410, occupancy: 0.58, annual: 86800, active: 340 },
  5: { adr: 510, occupancy: 0.55, annual: 102500, active: 120 },
  6: { adr: 620, occupancy: 0.52, annual: 117700, active: 55 },
}

const MONTHLY_FACTORS: Record<string, number> = {
  Jan: 1.22, Feb: 1.15, Mar: 1.10, Apr: 0.90,
  May: 0.72, Jun: 0.68, Jul: 0.70, Aug: 0.75,
  Sep: 0.85, Oct: 0.93, Nov: 1.05, Dec: 1.18,
}

const SAMPLE_COMPS = [
  { name: 'Modern 2BR Docklands with CBD Views', adr: 285, occ: 0.74, score: 4.92, dist: 0.8 },
  { name: 'Spacious Apartment near Southern Cross', adr: 262, occ: 0.71, score: 4.88, dist: 1.2 },
  { name: 'Luxury CBD 2BR with Parking', adr: 271, occ: 0.69, score: 4.85, dist: 1.5 },
  { name: 'West Side Place 2B2B', adr: 258, occ: 0.68, score: 4.91, dist: 0.4 },
  { name: 'City Fringe 2BR + Parking', adr: 243, occ: 0.65, score: 4.78, dist: 2.1 },
  { name: 'Highrise 2BR Seaview Parking', adr: 235, occ: 0.63, score: 4.82, dist: 1.9 },
]

const fmt = (n: number, prefix = '$') =>
  `${prefix}${Math.round(n).toLocaleString('en-AU')}`

function ResultsContent() {
  const params = useSearchParams()
  const address = params.get('address') || 'Melbourne Property'
  const beds = parseInt(params.get('beds') || '2')
  const type = params.get('type') || 'apartment'

  const market = MARKET_DATA[Math.min(beds, 6)] || MARKET_DATA[2]
  const nights = Math.round(market.occupancy * 365)
  const grossRevenue = Math.round(market.adr * nights)

  const monthlyData = Object.entries(MONTHLY_FACTORS).map(([month, f]) => ({
    month,
    revenue: Math.round(grossRevenue / 12 * f),
    occupancy: Math.round(market.occupancy * f * 100),
  }))

  const [tab, setTab] = useState<'performance' | 'pm-calculator'>('performance')

  // PM Calculator state
  const [pm, setPm] = useState({
    grossRevenue: grossRevenue.toString(),
    mgmtPct: '18',
    gst: true,
    platformPct: '15.5',
    cleaningCost: '120',
    cleaningsPerYear: '100',
    overPerfThreshold: Math.round(grossRevenue * 0.85).toString(),
    overPerfBonusPct: '10',
    ltrWeekly: '650',
  })

  const calcPM = () => {
    const gross = parseFloat(pm.grossRevenue) || 0
    const platFee = gross * (parseFloat(pm.platformPct) / 100)
    const mgmtFee = gross * (parseFloat(pm.mgmtPct) / 100)
    const gstAmt = pm.gst ? mgmtFee * 0.1 : 0
    const cleaning = parseFloat(pm.cleaningCost) * parseFloat(pm.cleaningsPerYear)
    const threshold = parseFloat(pm.overPerfThreshold) || 0
    const overPerf = gross > threshold ? (gross - threshold) * (parseFloat(pm.overPerfBonusPct) / 100) : 0
    const netOwner = gross - platFee - mgmtFee - gstAmt - cleaning - overPerf
    const ltrAnnual = parseFloat(pm.ltrWeekly) * 52
    return { gross, platFee, mgmtFee, gstAmt, cleaning, overPerf, netOwner, ltrAnnual }
  }

  const c = calcPM()

  const tabs = [
    { id: 'performance', label: 'STR Performance' },
    { id: 'pm-calculator', label: 'PM Calculator' },
  ]

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#0F172A]">{address}</h1>
        <p className="text-slate-500 text-sm mt-1">{beds} bed · {type} · Melbourne inner city</p>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Est. Annual Gross', value: fmt(grossRevenue), sub: 'Before fees & costs' },
          { label: 'Avg. Nightly Rate', value: fmt(market.adr), sub: 'Market median ADR' },
          { label: 'Projected Occupancy', value: `${Math.round(market.occupancy * 100)}%`, sub: `~${nights} nights/year` },
        ].map(m => (
          <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-5 text-center">
            <div className="text-2xl font-bold text-[#AF7225]">{m.value}</div>
            <div className="text-sm font-medium text-[#0F172A] mt-1">{m.label}</div>
            <div className="text-xs text-slate-400 mt-0.5">{m.sub}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-5">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id as 'performance' | 'pm-calculator')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t.id
                ? 'bg-[#0F172A] text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* STR Performance Tab */}
      {tab === 'performance' && (
        <div className="space-y-6">
          {/* Monthly revenue chart */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="font-semibold text-[#0F172A] mb-4">Monthly Revenue Projection</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={monthlyData} barSize={28}>
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip formatter={(v) => [`$${Number(v).toLocaleString('en-AU')}`, 'Revenue']} />
                <Bar dataKey="revenue" radius={[4,4,0,0]}>
                  {monthlyData.map((entry) => (
                    <Cell key={entry.month}
                      fill={entry.revenue > grossRevenue / 12 ? '#AF7225' : '#CBD5E1'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-xs text-slate-400 mt-3">Peak: Jan–Mar (summer + events) · Low: May–Aug (winter)</p>
          </div>

          {/* Comparable properties */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="font-semibold text-[#0F172A] mb-4">
              Comparable Properties
              <span className="ml-2 text-xs font-normal text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                Inside Airbnb · Sep 2025
              </span>
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
                    <th className="pb-2 pr-4 font-medium">Listing</th>
                    <th className="pb-2 pr-4 font-medium text-right">ADR</th>
                    <th className="pb-2 pr-4 font-medium text-right">Occ.</th>
                    <th className="pb-2 pr-4 font-medium text-right">Rating</th>
                    <th className="pb-2 font-medium text-right">Dist.</th>
                  </tr>
                </thead>
                <tbody>
                  {SAMPLE_COMPS.map((c, i) => (
                    <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                      <td className="py-2.5 pr-4 text-slate-700 max-w-[240px] truncate">{c.name}</td>
                      <td className="py-2.5 pr-4 text-right font-medium">${c.adr}</td>
                      <td className="py-2.5 pr-4 text-right">{Math.round(c.occ * 100)}%</td>
                      <td className="py-2.5 pr-4 text-right text-amber-600">★ {c.score}</td>
                      <td className="py-2.5 text-right text-slate-400">{c.dist}km</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-400 mt-3">
              Market range for {beds}BR inner Melbourne: ${Math.round(market.adr * 0.78)}–${Math.round(market.adr * 1.28)}/night
            </p>
          </div>

          {/* Regulation */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="font-semibold text-[#0F172A] mb-3">Victorian STR Regulation</h2>
            <div className="flex items-center gap-3 mb-3">
              <span className="bg-green-100 text-green-800 text-xs font-semibold px-3 py-1 rounded-full">✓ STR PERMITTED</span>
              <span className="bg-yellow-100 text-yellow-800 text-xs font-semibold px-3 py-1 rounded-full">⚠ 7.5% Levy Applies</span>
            </div>
            <p className="text-sm text-slate-600">No night cap in Victoria. Permit not required. A 7.5% short-stay levy applies to bookings under 28 nights — passed to guests via platform.</p>
            <p className="text-xs text-slate-400 mt-2">Last verified: April 2026 · Monitor City of Melbourne council for potential future caps</p>
          </div>
        </div>
      )}

      {/* PM Calculator Tab */}
      {tab === 'pm-calculator' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Inputs */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
            <h2 className="font-semibold text-[#0F172A]">LiveLuxe Hybrid PM Calculator</h2>
            <p className="text-xs text-slate-400">Adjust inputs to model different scenarios.</p>

            {[
              { key: 'grossRevenue', label: 'Gross STR Revenue (AUD)', type: 'number', prefix: '$' },
              { key: 'mgmtPct', label: 'Base Management Fee %', type: 'number' },
              { key: 'platformPct', label: 'Platform Fee % (Airbnb)', type: 'number' },
              { key: 'cleaningCost', label: 'Cleaning Cost per Turn ($)', type: 'number' },
              { key: 'cleaningsPerYear', label: 'Est. Cleans per Year', type: 'number' },
              { key: 'overPerfThreshold', label: 'Overperformance Threshold ($)', type: 'number' },
              { key: 'overPerfBonusPct', label: 'Overperformance Bonus %', type: 'number' },
              { key: 'ltrWeekly', label: 'LTR Comparison ($/week)', type: 'number' },
            ].map(field => (
              <div key={field.key}>
                <label className="block text-xs font-medium text-slate-600 mb-1">{field.label}</label>
                <input
                  type={field.type}
                  value={pm[field.key as keyof typeof pm] as string}
                  onChange={e => setPm(prev => ({ ...prev, [field.key]: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]"
                />
              </div>
            ))}

            <div className="flex items-center gap-3">
              <label className="text-xs font-medium text-slate-600">GST on management fee</label>
              <button onClick={() => setPm(p => ({ ...p, gst: !p.gst }))}
                className={`relative w-10 h-5 rounded-full transition-colors ${pm.gst ? 'bg-[#AF7225]' : 'bg-slate-300'}`}>
                <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${pm.gst ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
              <span className="text-xs text-slate-400">{pm.gst ? 'Yes (+10%)' : 'No'}</span>
            </div>
          </div>

          {/* Output */}
          <div className="space-y-4">
            {/* Net to owner — hero */}
            <div className="bg-[#0F172A] rounded-xl p-6 text-white text-center">
              <p className="text-sm text-slate-400 mb-1">Net to Owner</p>
              <p className="text-4xl font-bold text-[#AF7225]">{fmt(c.netOwner)}</p>
              <p className="text-sm text-slate-400 mt-1">per year</p>
              <p className="text-lg font-semibold mt-2">{fmt(c.netOwner / 52)}/week</p>
            </div>

            {/* Waterfall */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-2">
              <h3 className="text-sm font-semibold text-[#0F172A] mb-3">Fee Waterfall</h3>
              {[
                { label: 'Gross STR Revenue', value: c.gross, type: 'neutral' },
                { label: `Platform fees (${pm.platformPct}%)`, value: -c.platFee, type: 'deduct' },
                { label: `LiveLuxe base fee (${pm.mgmtPct}%)`, value: -c.mgmtFee, type: 'deduct' },
                ...(pm.gst ? [{ label: 'GST on management fee', value: -c.gstAmt, type: 'deduct' as const }] : []),
                { label: `Cleaning (${pm.cleaningsPerYear} × $${pm.cleaningCost})`, value: -c.cleaning, type: 'deduct' },
                ...(c.overPerf > 0 ? [{ label: `Overperformance bonus (${pm.overPerfBonusPct}% above threshold)`, value: -c.overPerf, type: 'deduct' as const }] : []),
              ].map((row, i) => (
                <div key={i} className={`flex justify-between text-sm py-1.5 border-b border-slate-50 last:border-0 ${row.type === 'deduct' ? 'text-red-600' : 'text-[#0F172A] font-medium'}`}>
                  <span>{row.label}</span>
                  <span>{row.value >= 0 ? fmt(row.value) : `−${fmt(Math.abs(row.value))}`}</span>
                </div>
              ))}
              <div className="flex justify-between text-sm font-bold pt-2 text-[#0F172A]">
                <span>NET TO OWNER</span>
                <span className="text-[#AF7225] text-base">{fmt(c.netOwner)}</span>
              </div>
            </div>

            {/* LTR comparison */}
            <div className={`rounded-xl p-4 text-sm ${c.netOwner > c.ltrAnnual ? 'bg-green-50 border border-green-200' : 'bg-amber-50 border border-amber-200'}`}>
              <div className="flex justify-between items-center">
                <span className="font-medium">vs Long-Term Rental</span>
                <span className={`font-bold ${c.netOwner > c.ltrAnnual ? 'text-green-700' : 'text-amber-700'}`}>
                  {c.netOwner > c.ltrAnnual ? '+' : ''}{fmt(c.netOwner - c.ltrAnnual)}/yr
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                LTR at ${pm.ltrWeekly}/wk = {fmt(c.ltrAnnual)}/yr net.
                STR {c.netOwner > c.ltrAnnual ? 'outperforms' : 'underperforms'} by {fmt(Math.abs(c.netOwner - c.ltrAnnual))}/yr.
              </p>
            </div>

            <p className="text-xs text-slate-400 text-center">
              Estimate only · Does not include strata, council rates, insurance or income tax
            </p>
          </div>
        </div>
      )}

      <div className="mt-8 text-center">
        <a href="/" className="text-sm text-[#AF7225] hover:underline">← Analyse another property</a>
      </div>
    </div>
  )
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<div className="text-center py-20 text-slate-400">Loading...</div>}>
      <ResultsContent />
    </Suspense>
  )
}
