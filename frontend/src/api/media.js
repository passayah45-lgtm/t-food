import api from './client'

function normalizeApiUrl(url) {
  if (!url) return ''
  try {
    const parsed = new URL(url, window.location.origin)
    url = parsed.pathname + parsed.search
  } catch {
    // Keep the original relative URL.
  }
  return url.startsWith('/api/v1') ? url.slice('/api/v1'.length) || '/' : url
}

export async function privateMediaBlob(url) {
  const { data } = await api.get(normalizeApiUrl(url), { responseType: 'blob' })
  return data
}

export async function openPrivateMedia(url) {
  const blob = await privateMediaBlob(url)
  const objectUrl = URL.createObjectURL(blob)
  window.open(objectUrl, '_blank', 'noopener,noreferrer')
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
}
