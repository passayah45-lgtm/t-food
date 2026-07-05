const DEFAULT_LOCALE = 'en'
const DEFAULT_CURRENCY = 'GNF'

const DATE_FORMAT_OPTIONS = {
  DD_MM_YYYY: { day: '2-digit', month: '2-digit', year: 'numeric' },
  MM_DD_YYYY: { month: '2-digit', day: '2-digit', year: 'numeric' },
  YYYY_MM_DD: { year: 'numeric', month: '2-digit', day: '2-digit' },
}

const TIME_FORMAT_OPTIONS = {
  short: { hour: 'numeric', minute: '2-digit' },
  medium: { hour: 'numeric', minute: '2-digit', second: '2-digit' },
}

function safeLocale(preferences) {
  const language = String(preferences?.language || '').split('-')[0].toLowerCase()
  return language || DEFAULT_LOCALE
}

function safeTimezone(preferences) {
  return preferences?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

function toDate(value) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function safeFormat(formatter, fallback = '-') {
  try {
    return formatter()
  } catch {
    return fallback
  }
}

function normalizeCurrencyCode(currencyCode, preferences, fallbackCurrency = DEFAULT_CURRENCY) {
  const detailCode = preferences?.preferred_currency_detail?.code
  return String(
    currencyCode
    || preferences?.effective_currency
    || preferences?.preferred_currency
    || detailCode
    || fallbackCurrency
    || DEFAULT_CURRENCY,
  ).toUpperCase()
}

function currencyDisplayOptions(preferences) {
  const display = preferences?.currency_display || 'SYMBOL'
  if (display === 'CODE') return { currencyDisplay: 'code' }
  if (display === 'NAME') return { currencyDisplay: 'name' }
  return { currencyDisplay: 'narrowSymbol' }
}

export function getEffectiveCurrency(currencyCode, preferences, fallbackCurrency = DEFAULT_CURRENCY) {
  return normalizeCurrencyCode(currencyCode, preferences, fallbackCurrency)
}

export function formatDate(value, preferences, options = {}) {
  const date = toDate(value)
  if (!date) return options.fallback || '-'
  const dateFormat = options.dateFormat || preferences?.date_format || 'AUTO'
  const intlOptions = {
    ...(DATE_FORMAT_OPTIONS[dateFormat] || { dateStyle: options.dateStyle || 'medium' }),
    timeZone: options.timeZone || safeTimezone(preferences),
    ...options.intlOptions,
  }
  return safeFormat(
    () => new Intl.DateTimeFormat(safeLocale(preferences), intlOptions).format(date),
    options.fallback || date.toISOString().slice(0, 10),
  )
}

export function formatTime(value, preferences, options = {}) {
  const date = toDate(value)
  if (!date) return options.fallback || '-'
  const timeFormat = options.timeFormat || preferences?.time_format || 'AUTO'
  const hour12 = ['12h', 'H_12'].includes(timeFormat)
    ? true
    : ['24h', 'H_24'].includes(timeFormat) ? false : undefined
  const intlOptions = {
    timeStyle: options.timeStyle || 'short',
    timeZone: options.timeZone || safeTimezone(preferences),
    ...(hour12 === undefined ? {} : { hour12 }),
    ...options.intlOptions,
  }
  return safeFormat(
    () => new Intl.DateTimeFormat(safeLocale(preferences), intlOptions).format(date),
    options.fallback || date.toISOString(),
  )
}

export function formatDateTime(value, preferences, options = {}) {
  const date = toDate(value)
  if (!date) return options.fallback || '-'
  const dateFormat = options.dateFormat || preferences?.date_format || 'AUTO'
  const timeFormat = options.timeFormat || preferences?.time_format || 'AUTO'
  const hour12 = ['12h', 'H_12'].includes(timeFormat)
    ? true
    : ['24h', 'H_24'].includes(timeFormat) ? false : undefined
  const customDateOptions = DATE_FORMAT_OPTIONS[dateFormat]
  const intlOptions = customDateOptions ? {
    ...customDateOptions,
    ...(TIME_FORMAT_OPTIONS[options.timeStyle || 'short'] || TIME_FORMAT_OPTIONS.short),
    timeZone: options.timeZone || safeTimezone(preferences),
    ...(hour12 === undefined ? {} : { hour12 }),
    ...options.intlOptions,
  } : {
    dateStyle: options.dateStyle || 'medium',
    timeStyle: options.timeStyle || 'short',
    timeZone: options.timeZone || safeTimezone(preferences),
    ...(hour12 === undefined ? {} : { hour12 }),
    ...options.intlOptions,
  }
  return safeFormat(
    () => new Intl.DateTimeFormat(safeLocale(preferences), intlOptions).format(date),
    options.fallback || date.toISOString(),
  )
}

export function formatNumber(value, preferences, options = {}) {
  if (value === null || value === undefined || value === '') return options.fallback || '-'
  const number = Number(value)
  if (Number.isNaN(number)) return options.fallback || '-'
  const intlOptions = {
    maximumFractionDigits: options.maximumFractionDigits ?? 2,
    minimumFractionDigits: options.minimumFractionDigits,
    ...options.intlOptions,
  }
  return safeFormat(
    () => new Intl.NumberFormat(safeLocale(preferences), intlOptions).format(number),
    String(number),
  )
}

export function formatCurrency(amount, currencyCode, preferences, options = {}) {
  if (amount === null || amount === undefined || amount === '') return options.fallback || '-'
  const value = Number(amount)
  if (Number.isNaN(value)) return options.fallback || '-'
  const currency = normalizeCurrencyCode(currencyCode, preferences, options.fallbackCurrency)
  const locale = safeLocale(preferences)
  const intlOptions = {
    style: 'currency',
    currency,
    minimumFractionDigits: options.minimumFractionDigits ?? 2,
    maximumFractionDigits: options.maximumFractionDigits ?? 2,
    ...currencyDisplayOptions(preferences),
    ...options.intlOptions,
  }
  return safeFormat(
    () => new Intl.NumberFormat(locale, intlOptions).format(value),
    `${currency} ${formatNumber(value, preferences, { maximumFractionDigits: 2 })}`,
  )
}
