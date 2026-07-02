import { useEffect, useState } from 'react'
import { privateMediaBlob } from '../api/media'

export default function PrivateImage({ src, alt = '', className = '' }) {
  const [objectUrl, setObjectUrl] = useState('')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let nextUrl = ''
    setFailed(false)
    setObjectUrl('')
    if (!src) return undefined
    privateMediaBlob(src)
      .then(blob => {
        if (cancelled) return
        nextUrl = URL.createObjectURL(blob)
        setObjectUrl(nextUrl)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
      if (nextUrl) URL.revokeObjectURL(nextUrl)
    }
  }, [src])

  if (failed) return <span className="text-xs text-gray-500">Preview unavailable</span>
  if (!objectUrl) return <span className="text-xs text-gray-500">Loading preview...</span>
  return <img src={objectUrl} alt={alt} className={className} />
}
