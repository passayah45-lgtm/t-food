import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { getPreferences, updatePreferences } from '../api/preferences'
import i18n, { getBrowserLanguage, getLanguageMeta, normalizeLanguage } from '../i18n'
import { useAuth } from './AuthContext'

const PreferencesContext = createContext(null)

const STORAGE_KEY = 'tfood_preferences'

export const DEFAULT_PREFERENCES = {
  language: 'en',
  preferred_country: '',
  preferred_market: null,
  preferred_market_detail: null,
  theme: 'SYSTEM',
  accent_color: 'ORANGE',
  timezone: '',
  date_format: 'AUTO',
  time_format: 'AUTO',
  number_format: 'AUTO',
  preferred_currency: null,
  preferred_currency_detail: null,
  effective_currency: null,
  currency_display: 'SYMBOL',
  large_text: false,
  high_contrast: false,
  reduced_motion: false,
  keyboard_focus_enhanced: false,
  preference_version: 1,
  metadata: {},
}

function readSystemTheme() {
  if (typeof window === 'undefined' || !window.matchMedia) return 'LIGHT'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'DARK' : 'LIGHT'
}

function browserDefaults() {
  const language = getBrowserLanguage()
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  return {
    language,
    timezone,
  }
}

function normalizePreferences(preferences) {
  const language = normalizeLanguage(preferences?.language || browserDefaults().language)
  return {
    ...DEFAULT_PREFERENCES,
    ...browserDefaults(),
    ...(preferences || {}),
    language,
    metadata: {
      ...DEFAULT_PREFERENCES.metadata,
      ...(preferences?.metadata || {}),
    },
  }
}

function readStoredPreferences() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return normalizePreferences()
    return normalizePreferences(JSON.parse(raw))
  } catch {
    return normalizePreferences()
  }
}

function writeStoredPreferences(preferences) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizePreferences(preferences)))
}

export function PreferencesProvider({ children }) {
  const { user, loading: authLoading } = useAuth()
  const [preferences, setPreferencesState] = useState(() => readStoredPreferences())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [systemTheme, setSystemTheme] = useState(readSystemTheme)

  const persist = useCallback((nextPreferences) => {
    const normalized = normalizePreferences(nextPreferences)
    setPreferencesState(normalized)
    writeStoredPreferences(normalized)
    return normalized
  }, [])

  const refreshPreferences = useCallback(async () => {
    setError('')
    if (!user) {
      setLoading(false)
      return persist(readStoredPreferences())
    }

    setLoading(true)
    try {
      const { data } = await getPreferences()
      return persist(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load preferences.')
      return persist(readStoredPreferences())
    } finally {
      setLoading(false)
    }
  }, [persist, user])

  useEffect(() => {
    if (authLoading) {
      setLoading(true)
      return
    }
    refreshPreferences()
  }, [authLoading, refreshPreferences])

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = event => setSystemTheme(event.matches ? 'DARK' : 'LIGHT')
    if (typeof query.addEventListener === 'function') {
      query.addEventListener('change', onChange)
      return () => query.removeEventListener('change', onChange)
    }
    query.addListener(onChange)
    return () => query.removeListener(onChange)
  }, [])

  const resolvedTheme = useMemo(() => {
    return preferences.theme === 'SYSTEM' ? systemTheme : preferences.theme
  }, [preferences.theme, systemTheme])

  useEffect(() => {
    const root = document.documentElement
    const theme = resolvedTheme === 'DARK' ? 'dark' : 'light'
    const accent = String(preferences.accent_color || 'ORANGE').toLowerCase()
    const languageMeta = getLanguageMeta(preferences.language)
    root.dataset.theme = theme
    root.dataset.accent = accent
    root.dataset.preferenceTheme = preferences.theme || 'SYSTEM'
    root.lang = languageMeta.code
    root.dir = languageMeta.direction
    root.classList.toggle('theme-dark', theme === 'dark')
    root.classList.toggle('theme-light', theme === 'light')
    root.classList.toggle('pref-large-text', Boolean(preferences.large_text))
    root.classList.toggle('pref-high-contrast', Boolean(preferences.high_contrast))
    root.classList.toggle('pref-reduced-motion', Boolean(preferences.reduced_motion))
    root.classList.toggle(
      'pref-keyboard-focus',
      Boolean(preferences.keyboard_focus_enhanced),
    )
  }, [
    preferences.accent_color,
    preferences.high_contrast,
    preferences.keyboard_focus_enhanced,
    preferences.language,
    preferences.large_text,
    preferences.reduced_motion,
    preferences.theme,
    resolvedTheme,
  ])

  useEffect(() => {
    const nextLanguage = normalizeLanguage(preferences.language)
    if (i18n.language !== nextLanguage) {
      i18n.changeLanguage(nextLanguage)
    }
  }, [preferences.language])

  const updatePreferenceFields = useCallback(async (patch) => {
    setError('')
    const next = normalizePreferences({ ...preferences, ...patch })
    if (!user) {
      return persist(next)
    }

    try {
      const { data } = await updatePreferences(patch)
      return persist(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to update preferences.')
      throw err
    }
  }, [persist, preferences, user])

  const setLanguage = useCallback(
    language => updatePreferenceFields({ language }),
    [updatePreferenceFields],
  )
  const setTheme = useCallback(
    theme => updatePreferenceFields({ theme }),
    [updatePreferenceFields],
  )
  const setAccentColor = useCallback(
    accent_color => updatePreferenceFields({ accent_color }),
    [updatePreferenceFields],
  )
  const setTimezone = useCallback(
    timezone => updatePreferenceFields({ timezone }),
    [updatePreferenceFields],
  )
  const setDateFormat = useCallback(
    date_format => updatePreferenceFields({ date_format }),
    [updatePreferenceFields],
  )
  const setTimeFormat = useCallback(
    time_format => updatePreferenceFields({ time_format }),
    [updatePreferenceFields],
  )
  const setNumberFormat = useCallback(
    number_format => updatePreferenceFields({ number_format }),
    [updatePreferenceFields],
  )
  const setPreferredCurrency = useCallback(
    preferred_currency => updatePreferenceFields({ preferred_currency }),
    [updatePreferenceFields],
  )
  const setCurrencyDisplay = useCallback(
    currency_display => updatePreferenceFields({ currency_display }),
    [updatePreferenceFields],
  )
  const setAccessibility = useCallback(
    accessibility => updatePreferenceFields({
      large_text: accessibility?.large_text ?? preferences.large_text,
      high_contrast: accessibility?.high_contrast ?? preferences.high_contrast,
      reduced_motion: accessibility?.reduced_motion ?? preferences.reduced_motion,
      keyboard_focus_enhanced: (
        accessibility?.keyboard_focus_enhanced
        ?? preferences.keyboard_focus_enhanced
      ),
    }),
    [preferences, updatePreferenceFields],
  )

  const value = useMemo(() => ({
    preferences,
    resolvedTheme,
    loading,
    error,
    setLanguage,
    setTheme,
    setAccentColor,
    setTimezone,
    setDateFormat,
    setTimeFormat,
    setNumberFormat,
    setPreferredCurrency,
    setCurrencyDisplay,
    setAccessibility,
    refreshPreferences,
  }), [
    preferences,
    resolvedTheme,
    loading,
    error,
    setLanguage,
    setTheme,
    setAccentColor,
    setTimezone,
    setDateFormat,
    setTimeFormat,
    setNumberFormat,
    setPreferredCurrency,
    setCurrencyDisplay,
    setAccessibility,
    refreshPreferences,
  ])

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  )
}

export const usePreferences = () => useContext(PreferencesContext)
