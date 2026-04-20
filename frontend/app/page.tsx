'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function Home() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    address: '', property_type: 'apartment',
    bedrooms: '2', bathrooms: '1',
    purchase_price: '', estimated_renovation: '',
    down_payment_pct: '20', mortgage_rate_pct: '6.5', mortgage_term_years: '30',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const payload = {
        address: form.address,
        property_type: form.property_type,
        bedrooms: parseInt(form.bedrooms),
        bathrooms: parseFloat(form.bathrooms),
        purchase_price: parseFloat(form.purchase_price),
        estimated_renovation: form.estimated_renovation ? parseFloat(form.estimated_renovation) : null,
        down_payment_pct: parseFloat(form.down_payment_pct),
        mortgage_rate_pct: parseFloat(form.mortgage_rate_pct),
        mortgage_term_years: parseInt(form.mortgage_term_years),
      }
      const res = await fetch(`${apiUrl}/api/feasibility/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Analysis failed') }
      const data = await res.json()
      router.push(`/analysis/${data.analysis_id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-[#0F172A] mb-2">Analyse a Property</h1>
        <p className="text-slate-500">Get a comprehensive STR feasibility report powered by real Melbourne Airbnb data.</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Property Address *</label>
          <input name="address" value={form.address} onChange={handleChange} required
            placeholder="123 Example St, Melbourne VIC 3000"
            className="w-full border border-slate-300 rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-[#AF7225] focus:border-[#AF7225] outline-none text-sm" />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
            <select name="property_type" value={form.property_type} onChange={handleChange}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]">
              {['apartment','house','townhouse','villa'].map(t => <option key={t} value={t}>{t[0].toUpperCase()+t.slice(1)}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Bedrooms</label>
            <select name="bedrooms" value={form.bedrooms} onChange={handleChange}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]">
              {[1,2,3,4,5,6].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Bathrooms</label>
            <select name="bathrooms" value={form.bathrooms} onChange={handleChange}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]">
              {[1,1.5,2,2.5,3,4].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Purchase Price (AUD) *</label>
            <input name="purchase_price" type="number" value={form.purchase_price} onChange={handleChange}
              required placeholder="780000" min="50000"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Renovation Estimate (optional)</label>
            <input name="estimated_renovation" type="number" value={form.estimated_renovation} onChange={handleChange}
              placeholder="0"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]" />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Down Payment %</label>
            <input name="down_payment_pct" type="number" value={form.down_payment_pct} onChange={handleChange}
              min="5" max="100" step="1"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Mortgage Rate %</label>
            <input name="mortgage_rate_pct" type="number" value={form.mortgage_rate_pct} onChange={handleChange}
              min="0" max="25" step="0.1"
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Term (years)</label>
            <select name="mortgage_term_years" value={form.mortgage_term_years} onChange={handleChange}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]">
              {[15,20,25,30].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>

        {error && <p className="text-red-500 text-sm bg-red-50 border border-red-200 rounded p-3">{error}</p>}

        <button type="submit" disabled={loading}
          className="w-full bg-[#AF7225] hover:bg-[#8d5c1e] disabled:bg-[#d4a96a] text-white font-semibold py-3 rounded-lg transition-colors text-sm">
          {loading ? 'Starting Analysis...' : '→ Analyse Property'}
        </button>
      </form>
    </div>
  )
}
