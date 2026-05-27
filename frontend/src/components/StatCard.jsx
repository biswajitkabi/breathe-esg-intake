export default function StatCard({ label, value, sub, color = 'gray' }) {
  const colors = {
    gray:   'bg-white border-gray-200',
    green:  'bg-green-50 border-green-200',
    yellow: 'bg-yellow-50 border-yellow-200',
    red:    'bg-red-50 border-red-200',
    blue:   'bg-blue-50 border-blue-200',
  }
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-3xl font-bold text-gray-800">{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-500">{sub}</p>}
    </div>
  )
}