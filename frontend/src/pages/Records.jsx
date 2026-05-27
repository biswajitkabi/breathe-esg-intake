import { useEffect, useState, useCallback } from 'react'
import client from '../api/client'
import toast from 'react-hot-toast'
import StatusBadge from '../components/StatusBadge'
import ScopeBadge from '../components/ScopeBadge'
import { CheckCheck, X, Flag, ChevronLeft, ChevronRight } from 'lucide-react'

const STATUSES  = ['', 'PENDING', 'APPROVED', 'REJECTED', 'FLAGGED']
const SCOPES    = ['', '1', '2', '3']
const SOURCES   = ['', 'SAP', 'UTILITY', 'TRAVEL']
const CATEGORIES = ['', 'FUEL', 'PROCUREMENT', 'ELECTRICITY', 'FLIGHT', 'HOTEL', 'GROUND']

export default function Records() {
  const [records, setRecords]   = useState([])
  const [count, setCount]       = useState(0)
  const [page, setPage]         = useState(1)
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState([])
  const [filters, setFilters]   = useState({
    status: '', scope: '', source_type: '', category: ''
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) }
      const res = await client.get('/review/records/', { params })
      setRecords(res.data.results)
      setCount(res.data.count)
    } finally {
      setLoading(false)
    }
  }, [page, filters])

  useEffect(() => { load() }, [load])

  const handleFilter = (key, val) => {
    setFilters(f => ({ ...f, [key]: val }))
    setPage(1)
    setSelected([])
  }

  const toggleSelect = (id) => {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  }

  const toggleAll = () => {
    setSelected(selected.length === records.length ? [] : records.map(r => r.id))
  }

  const singleAction = async (id, action) => {
    try {
      await client.post(`/review/records/${id}/action/`, { action })
      toast.success(`Record ${action.toLowerCase()}d`)
      load()
    } catch {
      toast.error('Action failed')
    }
  }

  const bulkAction = async (action) => {
    if (!selected.length) return toast.error('Select records first')
    try {
      const res = await client.post('/review/records/bulk-action/', { ids: selected, action })
      toast.success(`${res.data.updated} records ${action.toLowerCase()}d`)
      setSelected([])
      load()
    } catch {
      toast.error('Bulk action failed')
    }
  }

  const totalPages = Math.ceil(count / 50)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Emission Records</h1>
          <p className="text-sm text-gray-500">{count} total records</p>
        </div>

        {/* Bulk actions */}
        {selected.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">{selected.length} selected</span>
            <button onClick={() => bulkAction('APPROVE')}
              className="flex items-center gap-1 bg-green-600 hover:bg-green-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg">
              <CheckCheck size={14} /> Approve All
            </button>
            <button onClick={() => bulkAction('REJECT')}
              className="flex items-center gap-1 bg-red-600 hover:bg-red-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg">
              <X size={14} /> Reject All
            </button>
            <button onClick={() => bulkAction('FLAG')}
              className="flex items-center gap-1 bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg">
              <Flag size={14} /> Flag All
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-5">
        {[
          { key: 'status',      label: 'Status',   options: STATUSES },
          { key: 'scope',       label: 'Scope',    options: SCOPES },
          { key: 'source_type', label: 'Source',   options: SOURCES },
          { key: 'category',    label: 'Category', options: CATEGORIES },
        ].map(({ key, label, options }) => (
          <select
            key={key}
            value={filters[key]}
            onChange={e => handleFilter(key, e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">{label}: All</option>
            {options.filter(Boolean).map(o => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left">
                <input type="checkbox"
                  checked={selected.length === records.length && records.length > 0}
                  onChange={toggleAll}
                  className="rounded"
                />
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Scope</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Category</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Activity</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">CO₂e (kg)</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Period</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Facility / Detail</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            ) : records.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">No records found</td></tr>
            ) : records.map(r => (
              <tr key={r.id} className={`hover:bg-gray-50 ${selected.includes(r.id) ? 'bg-brand-50' : ''}`}>
                <td className="px-4 py-3">
                  <input type="checkbox" checked={selected.includes(r.id)}
                    onChange={() => toggleSelect(r.id)} className="rounded" />
                </td>
                <td className="px-4 py-3"><ScopeBadge scope={r.scope} /></td>
                <td className="px-4 py-3 text-gray-700">{r.category}</td>
                <td className="px-4 py-3 text-gray-700">
                  {Number(r.activity_value).toLocaleString()} {r.activity_unit}
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {r.co2e_kg ? Number(r.co2e_kg).toFixed(2) : '—'}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {r.period_start}<br/>{r.period_end !== r.period_start ? `→ ${r.period_end}` : ''}
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs max-w-xs truncate">
                  {r.facility_name || r.origin_iata
                    ? `${r.facility_name}${r.origin_iata ? ` ${r.origin_iata}→${r.destination_iata}` : ''}`
                    : r.description?.slice(0, 40) || '—'}
                  {r.flag_reason && (
                    <p className="text-orange-500 mt-0.5 truncate">{r.flag_reason}</p>
                  )}
                </td>
                <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <button onClick={() => singleAction(r.id, 'APPROVE')}
                      title="Approve"
                      className="p-1 rounded hover:bg-green-100 text-green-600 disabled:opacity-30"
                      disabled={r.status === 'APPROVED' || r.is_locked}>
                      <CheckCheck size={15} />
                    </button>
                    <button onClick={() => singleAction(r.id, 'FLAG')}
                      title="Flag"
                      className="p-1 rounded hover:bg-orange-100 text-orange-500 disabled:opacity-30"
                      disabled={r.is_locked}>
                      <Flag size={15} />
                    </button>
                    <button onClick={() => singleAction(r.id, 'REJECT')}
                      title="Reject"
                      className="p-1 rounded hover:bg-red-100 text-red-500 disabled:opacity-30"
                      disabled={r.status === 'REJECTED' || r.is_locked}>
                      <X size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
            <p className="text-xs text-gray-500">Page {page} of {totalPages}</p>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="p-1 rounded hover:bg-gray-100 disabled:opacity-30">
                <ChevronLeft size={16} />
              </button>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="p-1 rounded hover:bg-gray-100 disabled:opacity-30">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}