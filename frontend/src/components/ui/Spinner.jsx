export default function Spinner({ size = 'md', className = '' }) {
  const s = size === 'sm' ? 'h-4 w-4' : size === 'lg' ? 'h-10 w-10' : 'h-6 w-6'
  return (
    <div className={`${s} ${className} animate-spin rounded-full border-2 border-brand-200 border-t-brand-500`} />
  )
}
