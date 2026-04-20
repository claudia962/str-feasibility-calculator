'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function Home() {
  const router = useRouter()
  const [form, setForm] = useState({
    address: '', property_type: 'apartment',
    bedrooms: '2', bathrooms: '2',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const params = new URLSearchParams({
      address: form.address,
      type: form.property_type,
      beds: form.bedrooms,
      baths: form.bathrooms,
    })
    router.push(`/results?${params.toString()}`)
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-[#0F172A] mb-2">STR Performance Analyser</h1>
        <p className="text-slate-500">Enter a Melbourne property to see estimated STR performance based on real Airbnb market data.</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Property Address *</label>
          <input name="address" value={form.address} onChange={handleChange} required
            placeholder="58 Jeffcott St, West Melbourne VIC 3003"
            className="w-full border border-slate-300 rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-[#AF7225] focus:border-[#AF7225] outline-none text-sm" />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
            <select name="property_type" value={form.property_type} onChange={handleChange}
              className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[#AF7225]">
              {['apartment','house','townhouse','villa'].map(t => (
                <option key={t} value={t}>{t[0].toUpperCase()+t.slice(1)}</option>
              ))}
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

        <button type="submit"
          className="w-full bg-[#AF7225] hover:bg-[#8d5c1e] text-white font-semibold py-3 rounded-lg transition-colors text-sm">
          → Analyse STR Performance
        </button>
      </form>

      <p className="text-center text-xs text-slate-400 mt-4">
        Powered by 62,034 real Melbourne Airbnb listings · Data: Inside Airbnb Sep 2025
      </p>
    </div>
  )
}
