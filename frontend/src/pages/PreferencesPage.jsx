import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bell, Palette, Settings, SlidersHorizontal, Sparkles, Type, WalletCards } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { getNotificationPreferences, updateNotificationPreferences } from '../api/notifications'
import { getPreferenceOptions } from '../api/preferences'
import { useAuth } from '../context/AuthContext'
import { usePreferences } from '../context/PreferencesContext'
import { LANGUAGE_OPTIONS } from '../i18n'
import useTitle from '../hooks/useTitle'

const fallbackOptions = {
  themes: [
    { code: 'LIGHT', label: 'Light' },
    { code: 'DARK', label: 'Dark' },
    { code: 'SYSTEM', label: 'System' },
  ],
  accent_colors: [
    { code: 'ORANGE', label: 'Orange' },
    { code: 'BLUE', label: 'Blue' },
    { code: 'GREEN', label: 'Green' },
    { code: 'PURPLE', label: 'Purple' },
    { code: 'RED', label: 'Red' },
    { code: 'PINK', label: 'Pink' },
    { code: 'TEAL', label: 'Teal' },
  ],
  date_formats: [
    { code: 'AUTO', label: 'Automatic' },
    { code: 'DD_MM_YYYY', label: 'DD/MM/YYYY' },
    { code: 'MM_DD_YYYY', label: 'MM/DD/YYYY' },
    { code: 'YYYY_MM_DD', label: 'YYYY-MM-DD' },
  ],
  time_formats: [
    { code: 'AUTO', label: 'Automatic' },
    { code: 'H_12', label: '12-hour' },
    { code: 'H_24', label: '24-hour' },
  ],
  number_formats: [
    { code: 'AUTO', label: 'Automatic' },
    { code: 'EN', label: 'English' },
    { code: 'FR', label: 'French' },
    { code: 'HI', label: 'Hindi' },
    { code: 'AR', label: 'Arabic' },
  ],
  currency_display_styles: [
    { code: 'SYMBOL', label: 'Symbol' },
    { code: 'CODE', label: 'Code' },
    { code: 'NAME', label: 'Name' },
  ],
  supported_currencies: [],
}

const commonTimezones = [
  '',
  'Africa/Conakry',
  'Asia/Kolkata',
  'UTC',
  'Europe/Paris',
  'Africa/Lagos',
  'America/New_York',
]

const notificationChannels = [
  { code: 'IN_APP', labelKey: 'preferences.notifications.channels.inApp' },
  { code: 'REALTIME', labelKey: 'preferences.notifications.channels.realtime' },
  { code: 'EMAIL', labelKey: 'preferences.notifications.channels.email' },
  { code: 'SMS', labelKey: 'preferences.notifications.channels.sms' },
  { code: 'PUSH', labelKey: 'preferences.notifications.channels.push' },
  { code: 'WHATSAPP', labelKey: 'preferences.notifications.channels.whatsapp' },
  { code: 'TELEGRAM', labelKey: 'preferences.notifications.channels.telegram' },
]

const notificationCategories = [
  { code: 'ORDER', labelKey: 'preferences.notifications.categories.orders' },
  { code: 'PAYMENT', labelKey: 'preferences.notifications.categories.payments' },
  { code: 'DELIVERY', labelKey: 'preferences.notifications.categories.delivery' },
  { code: 'MERCHANT', labelKey: 'preferences.notifications.categories.merchant' },
  { code: 'STAFF', labelKey: 'preferences.notifications.categories.staff' },
  { code: 'RIDER', labelKey: 'preferences.notifications.categories.rider' },
  { code: 'SUPPORT', labelKey: 'preferences.notifications.categories.support' },
  { code: 'VERIFICATION', labelKey: 'preferences.notifications.categories.verification' },
  { code: 'DISPATCH', labelKey: 'preferences.notifications.categories.dispatch' },
  { code: 'INTELLIGENCE', labelKey: 'preferences.notifications.categories.intelligence' },
  { code: 'SYSTEM', labelKey: 'preferences.notifications.categories.system' },
]

const accentSwatches = {
  ORANGE: 'bg-orange-500',
  BLUE: 'bg-blue-500',
  GREEN: 'bg-green-500',
  PURPLE: 'bg-purple-500',
  RED: 'bg-red-500',
  PINK: 'bg-pink-500',
  TEAL: 'bg-teal-500',
}

function Section({ icon: Icon, title, description, children }) {
  return (
    <section className="card p-5">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0">
          <Icon size={19} />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-gray-950">{title}</h2>
          {description && <p className="text-sm text-gray-500 mt-1">{description}</p>}
          <div className="mt-4 space-y-4">{children}</div>
        </div>
      </div>
    </section>
  )
}

function SelectField({ label, value, onChange, children }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <select className="input-field mt-1" value={value ?? ''} onChange={event => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  )
}

function ToggleField({ label, description, checked, onChange }) {
  return (
    <label className="flex items-start justify-between gap-4 rounded-lg border border-gray-200 p-3">
      <span>
        <span className="block text-sm font-medium text-gray-800">{label}</span>
        {description && <span className="block text-xs text-gray-500 mt-1">{description}</span>}
      </span>
      <input
        type="checkbox"
        checked={Boolean(checked)}
        onChange={event => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 accent-brand-600"
      />
    </label>
  )
}

export default function PreferencesPage() {
  const { t } = useTranslation()
  useTitle(t('preferences.title'))
  const { user } = useAuth()
  const {
    preferences,
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
  } = usePreferences()

  const optionsQuery = useQuery({
    queryKey: ['preference-options'],
    queryFn: async () => (await getPreferenceOptions()).data,
    retry: false,
    staleTime: 1000 * 60 * 20,
  })

  const notificationPreferencesQuery = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: async () => (await getNotificationPreferences()).data,
    enabled: Boolean(user),
    retry: false,
    staleTime: 1000 * 60 * 5,
  })

  const options = useMemo(() => ({
    ...fallbackOptions,
    ...(optionsQuery.data || {}),
  }), [optionsQuery.data])

  const savePreference = async (label, action) => {
    try {
      await action()
      toast.success(t('preferences.saved', { label }))
    } catch {
      toast.error(t('preferences.saveFailed'))
    }
  }

  const activeLanguages = LANGUAGE_OPTIONS.filter(option => option.is_active)
  const notificationPreferenceMap = useMemo(() => {
    const items = notificationPreferencesQuery.data?.results || []
    return new Map(items.map(item => [`${item.category}:${item.channel}`, item]))
  }, [notificationPreferencesQuery.data])
  const activeChannels = new Set(notificationPreferencesQuery.data?.active_channels || ['IN_APP', 'REALTIME'])
  const futureChannels = new Set(notificationPreferencesQuery.data?.future_channels_inactive || ['EMAIL', 'SMS', 'PUSH', 'WHATSAPP', 'TELEGRAM'])

  const toggleNotificationPreference = async (category, channel, enabled) => {
    try {
      const current = notificationPreferenceMap.get(`${category}:${channel}`)
      await updateNotificationPreferences({
        preferences: [{
          category,
          channel,
          enabled,
          quiet_hours_enabled: current?.quiet_hours_enabled || false,
          quiet_hours_start: current?.quiet_hours_start || null,
          quiet_hours_end: current?.quiet_hours_end || null,
          language: preferences.language,
        }],
      })
      await notificationPreferencesQuery.refetch()
      toast.success(t('preferences.notifications.saved'))
    } catch {
      toast.error(t('preferences.notifications.saveFailed'))
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-950">{t('preferences.title')}</h1>
        <p className="text-gray-500 mt-1">{t('preferences.subtitle')}</p>
        {error && <p className="text-sm text-amber-700 mt-3">{error}</p>}
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <Section icon={Settings} title={t('preferences.language.title')} description={t('preferences.language.description')}>
          <SelectField
            label={t('preferences.language.label')}
            value={preferences.language}
            onChange={value => savePreference(t('preferences.language.label'), () => setLanguage(value))}
          >
            {activeLanguages.map(language => (
              <option key={language.code} value={language.code}>{language.native_name}</option>
            ))}
          </SelectField>
        </Section>

        <Section icon={Palette} title={t('preferences.appearance.title')} description={t('preferences.appearance.description')}>
          <SelectField
            label={t('preferences.appearance.theme')}
            value={preferences.theme}
            onChange={value => savePreference(t('preferences.appearance.theme'), () => setTheme(value))}
          >
            {options.themes.map(option => <option key={option.code} value={option.code}>{option.label}</option>)}
          </SelectField>
        </Section>

        <Section icon={Sparkles} title={t('preferences.accent.title')} description={t('preferences.accent.description')}>
          <p className="text-sm text-gray-600">{t('preferences.accent.help')}</p>
          <div className="grid sm:grid-cols-2 gap-3">
            {options.accent_colors.map(option => (
              <button
                key={option.code}
                type="button"
                onClick={() => savePreference(option.label, () => setAccentColor(option.code))}
                className={`rounded-lg border px-3 py-3 text-left text-sm font-medium transition-all ${preferences.accent_color === option.code ? 'border-brand-600 bg-brand-50 text-brand-900 ring-2 ring-brand-100' : 'border-gray-200 text-gray-700 hover:border-brand-300 hover:bg-gray-50'}`}
                aria-pressed={preferences.accent_color === option.code}
              >
                <span className="flex items-center gap-3">
                  <span className={`h-6 w-6 rounded-full border border-white shadow-sm ${accentSwatches[option.code] || 'bg-brand-500'}`} />
                  <span className="flex-1">{option.label}</span>
                  {preferences.accent_color === option.code && (
                    <span className="text-xs font-semibold text-brand-700">{t('preferences.accent.selected')}</span>
                  )}
                </span>
              </button>
            ))}
          </div>
        </Section>

        <Section icon={SlidersHorizontal} title={t('preferences.regional.title')} description={t('preferences.regional.description')}>
          <div className="grid sm:grid-cols-2 gap-3">
            <SelectField
              label={t('preferences.regional.timezone')}
              value={preferences.timezone}
              onChange={value => savePreference(t('preferences.regional.timezone'), () => setTimezone(value))}
            >
              {commonTimezones.map(zone => (
                <option key={zone || 'auto'} value={zone}>{zone || t('preferences.auto')}</option>
              ))}
            </SelectField>
            <SelectField
              label={t('preferences.regional.dateFormat')}
              value={preferences.date_format}
              onChange={value => savePreference(t('preferences.regional.dateFormat'), () => setDateFormat(value))}
            >
              {options.date_formats.map(option => <option key={option.code} value={option.code}>{option.label}</option>)}
            </SelectField>
            <SelectField
              label={t('preferences.regional.timeFormat')}
              value={preferences.time_format}
              onChange={value => savePreference(t('preferences.regional.timeFormat'), () => setTimeFormat(value))}
            >
              {options.time_formats.map(option => <option key={option.code} value={option.code}>{option.label}</option>)}
            </SelectField>
            <SelectField
              label={t('preferences.regional.numberFormat')}
              value={preferences.number_format}
              onChange={value => savePreference(t('preferences.regional.numberFormat'), () => setNumberFormat(value))}
            >
              {options.number_formats.map(option => <option key={option.code} value={option.code}>{option.label}</option>)}
            </SelectField>
          </div>
        </Section>

        <Section icon={WalletCards} title={t('preferences.currency.title')} description={t('preferences.currency.description')}>
          <div className="grid sm:grid-cols-2 gap-3">
            <SelectField
              label={t('preferences.currency.preferred')}
              value={preferences.preferred_currency || ''}
              onChange={value => savePreference(t('preferences.currency.preferred'), () => setPreferredCurrency(value || null))}
            >
              <option value="">{t('preferences.currency.platformDefault')}</option>
              {options.supported_currencies.map(currency => (
                <option key={currency.id} value={currency.id}>{currency.code} - {currency.name}</option>
              ))}
            </SelectField>
            <SelectField
              label={t('preferences.currency.display')}
              value={preferences.currency_display}
              onChange={value => savePreference(t('preferences.currency.display'), () => setCurrencyDisplay(value))}
            >
              {options.currency_display_styles.map(option => <option key={option.code} value={option.code}>{option.label}</option>)}
            </SelectField>
          </div>
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {t('preferences.currency.note')}
          </p>
        </Section>

        <Section icon={Type} title={t('preferences.accessibility.title')} description={t('preferences.accessibility.description')}>
          <div className="space-y-2">
            <ToggleField
              label={t('preferences.accessibility.largeText')}
              checked={preferences.large_text}
              onChange={value => savePreference(t('preferences.accessibility.largeText'), () => setAccessibility({ large_text: value }))}
            />
            <ToggleField
              label={t('preferences.accessibility.highContrast')}
              checked={preferences.high_contrast}
              onChange={value => savePreference(t('preferences.accessibility.highContrast'), () => setAccessibility({ high_contrast: value }))}
            />
            <ToggleField
              label={t('preferences.accessibility.reducedMotion')}
              checked={preferences.reduced_motion}
              onChange={value => savePreference(t('preferences.accessibility.reducedMotion'), () => setAccessibility({ reduced_motion: value }))}
            />
            <ToggleField
              label={t('preferences.accessibility.keyboardFocus')}
              checked={preferences.keyboard_focus_enhanced}
              onChange={value => savePreference(t('preferences.accessibility.keyboardFocus'), () => setAccessibility({ keyboard_focus_enhanced: value }))}
            />
          </div>
        </Section>

        <section className="card p-5 lg:col-span-2">
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0">
              <Bell size={19} />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold text-gray-950">{t('preferences.notifications.title')}</h2>
              <p className="text-sm text-gray-500 mt-1">{t('preferences.notifications.description')}</p>

              {!user && (
                <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {t('preferences.notifications.signInRequired')}
                </p>
              )}

              {user && notificationPreferencesQuery.isError && (
                <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {t('preferences.notifications.loadFailed')}
                </p>
              )}

              <div className="mt-5 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left">
                      <th className="py-2 pr-3 font-medium text-gray-700">{t('preferences.notifications.category')}</th>
                      {notificationChannels.map(channel => (
                        <th key={channel.code} className="py-2 px-2 font-medium text-gray-700 whitespace-nowrap">
                          <span>{t(channel.labelKey)}</span>
                          {futureChannels.has(channel.code) && (
                            <span className="block text-[11px] font-normal text-gray-400">
                              {t('preferences.notifications.comingSoon')}
                            </span>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {notificationCategories.map(category => (
                      <tr key={category.code}>
                        <td className="py-3 pr-3 font-medium text-gray-800 whitespace-nowrap">{t(category.labelKey)}</td>
                        {notificationChannels.map(channel => {
                          const preference = notificationPreferenceMap.get(`${category.code}:${channel.code}`)
                          const enabled = preference?.enabled ?? activeChannels.has(channel.code)
                          const disabled = !user || notificationPreferencesQuery.isLoading
                          return (
                            <td key={channel.code} className="py-3 px-2 text-center">
                              <label className="inline-flex flex-col items-center gap-1">
                                <input
                                  type="checkbox"
                                  checked={Boolean(enabled)}
                                  disabled={disabled}
                                  onChange={event => toggleNotificationPreference(category.code, channel.code, event.target.checked)}
                                  className="h-4 w-4 accent-brand-600 disabled:opacity-40"
                                  aria-label={`${t(category.labelKey)} ${t(channel.labelKey)}`}
                                />
                                {preference?.quiet_hours_enabled && (
                                  <span className="text-[10px] text-gray-400 whitespace-nowrap">
                                    {preference.quiet_hours_start?.slice(0, 5)}-{preference.quiet_hours_end?.slice(0, 5)}
                                  </span>
                                )}
                              </label>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 grid md:grid-cols-2 gap-3 text-sm">
                <p className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-gray-600">
                  {t('preferences.notifications.activeNote')}
                </p>
                <p className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-gray-600">
                  {t('preferences.notifications.quietHoursNote')}
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
