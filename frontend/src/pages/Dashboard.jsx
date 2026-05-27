import { useEffect, useState } from 'react'
import client from '../api/client'
import StatCard from '../components/StatCard'
import { RefreshCw } from 'lucide-react'

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get('/review/summary/')
      setSummary(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="p-8 text-gray-500 text-sm">Loading summary...</div>
  )

  const co2t = summary ? (Number(summary.total_co2e_kg) / 1000).toFixed(2) : '—'

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Emissions data intake overview</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800">
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Review status */}
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Review Status</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Records"  value={summary?.total_records ?? '—'} color="gray" />
        <StatCard label="Pending"        value={summary?.pending ?? '—'}        color="yellow" />
        <StatCard label="Approved"       value={summary?.approved ?? '—'}       color="green" />
        <StatCard label="Flagged"        value={summary?.flagged ?? '—'}        color="red" />
      </div>

      {/* Emissions */}
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Approved Emissions</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total CO₂e"  value={`${co2t} t`}  sub="approved records only" color="blue" />
        <StatCard label="Scope 1"     value={`${(summary?.by_scope?.scope1 / 1000).toFixed(2)} t`} color="gray" />
        <StatCard label="Scope 2"     value={`${(summary?.by_scope?.scope2 / 1000).toFixed(2)} t`} color="gray" />
        <StatCard label="Scope 3"     value={`${(summary?.by_scope?.scope3 / 1000).toFixed(2)} t`} color="gray" />
      </div>

      {/* By source */}
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Records by Source</h2>
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="SAP (Fuel)"     value={summary?.by_source?.SAP ?? 0}     color="gray" />
        <StatCard label="Utility (Elec)" value={summary?.by_source?.UTILITY ?? 0} color="gray" />
        <StatCard label="Travel"         value={summary?.by_source?.TRAVEL ?? 0}  color="gray" />
      </div>
    </div>
  )
}