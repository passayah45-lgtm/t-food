export default function InsightList({ items = [], emptyLabel, renderItem }) {
  if (!items.length) {
    return <p className="text-sm text-gray-500 border border-dashed border-gray-300 rounded-lg p-4">{emptyLabel}</p>
  }
  return <div className="divide-y divide-gray-200 border-y border-gray-200">{items.map(renderItem)}</div>
}
