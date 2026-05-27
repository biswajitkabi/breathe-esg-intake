import { useState } from 'react'
import client from '../api/client'
import toast from 'react-hot-toast'
import { Upload as UploadIcon, CheckCircle, XCircle } from 'lucide-react'

const SOURCES = [
  {
    key: 'SAP',
    label: 'SAP — Fuel & Procurement',
    accept: '.csv',
    hint: 'Semicolon or comma-delimited CSV export from SAP MB51/ME2M. Columns: WERKS, MATNR, MENGE, MEINS, BLDAT, LIFNR.',
  },
  {
    key: 'UTILITY',
    label: 'Utility — Electricity',
    accept: '.csv',
    hint: 'Portal CSV export. Columns: meter_id, site_name, billing_period_start, billing_period_end, consumption_kwh, tariff_code.',
  },
  {
    key: 'TRAVEL',
    label: 'Corporate Travel — Concur Export',
    accept: '.json',
    hint: 'JSON array of trip records with segments (air/hotel/ground). Matches Concur itinerary API export format.',
  },
]

function UploadCard({ source }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleUpload = async () => {
    if (!file) return toast.error('Select a file first')
    setLoading(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('source_type', source.key)
      fd.append('file', file)
      const res = await client.post('/ingestion/upload/', fd)
      setResult(res.data)
      toast.success(`${res.data.rows_created} rows ingested`)
    } catch (err) {
      const msg = err.response?.data?.error || 'Upload failed'
      toast.error(msg)
      setResult({ error: msg })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6">
      <h3 className="font-semibold text-gray-800 mb-1">{source.label}</h3>
      <p className="text-xs text-gray-500 mb-4">{source.hint}</p>

      <div className="flex items-center gap-3 mb-4">
        <label className="cursor-pointer flex items-center gap-2 border border-dashed border-gray-300 rounded-lg px-4 py-2 text-sm text-gray-600 hover:border-brand-500 hover:text-brand-600 transition-colors">
          <UploadIcon size={16} />
          {file ? file.name : `Choose ${source.accept} file`}
          <input
            type="file"
            accept={source.accept}
            className="hidden"
            onChange={e => { setFile(e.target.files[0]); setResult(null) }}
          />
        </label>
        <button
          onClick={handleUpload}
          disabled={!file || loading}
          className="bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50 transition-colors"
        >
          {loading ? 'Uploading...' : 'Upload'}
        </button>
      </div>

      {result && !result.error && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm">
          <div className="flex items-center gap-2 text-green-700 font-medium mb-1">
            <CheckCircle size={16} /> Upload complete
          </div>
          <p className="text-green-600">Rows created: {result.rows_created}</p>
          {result.errors?.length > 0 && (
            <p className="text-orange-600 mt-1">Parse errors: {result.errors.length} rows skipped</p>
          )}
          {result.errors?.slice(0, 3).map((e, i) => (
            <p key={i} className="text-xs text-orange-500 mt-1">Row {e.row}: {e.reason}</p>
          ))}
        </div>
      )}

      {result?.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm flex items-center gap-2 text-red-700">
          <XCircle size={16} /> {result.error}
        </div>
      )}
    </div>
  )
}

export default function Upload() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-1">Upload Data</h1>
      <p className="text-sm text-gray-500 mb-6">Ingest emissions data from SAP, utility portals, or corporate travel platforms.</p>
      <div className="grid gap-5 md:grid-cols-1 lg:grid-cols-3">
        {SOURCES.map(s => <UploadCard key={s.key} source={s} />)}
      </div>
    </div>
  )
}