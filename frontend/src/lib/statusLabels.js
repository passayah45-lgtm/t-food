const humanize = value => (
  String(value || '')
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, letter => letter.toUpperCase())
)

export function statusLabel(status, t, namespace = 'common') {
  if (!status) return t('statuses.notAvailable')
  const key = String(status).toUpperCase()
  const translated = t(`statuses.${namespace}.${key}`, { defaultValue: '' })
  return translated || t(`statuses.common.${key}`, { defaultValue: humanize(status) })
}

export function statusLabelForAny(status, t) {
  return statusLabel(status, t, 'common')
}
