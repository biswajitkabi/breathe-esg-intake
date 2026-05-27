const map = {
  1: 'bg-red-100 text-red-700',
  2: 'bg-blue-100 text-blue-700',
  3: 'bg-purple-100 text-purple-700',
}

export default function ScopeBadge({ scope }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${map[scope] || 'bg-gray-100 text-gray-700'}`}>
      Scope {scope}
    </span>
  )
}