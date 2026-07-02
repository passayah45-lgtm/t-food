import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import fr from './locales/fr.json'

export const DEFAULT_LANGUAGE = 'en'

export const LANGUAGE_OPTIONS = [
  { code: 'en', name: 'English', native_name: 'English', direction: 'ltr', is_active: true },
  { code: 'fr', name: 'French', native_name: 'Français', direction: 'ltr', is_active: true },
  { code: 'ar', name: 'Arabic', native_name: 'العربية', direction: 'rtl', is_active: false },
  { code: 'hi', name: 'Hindi', native_name: 'हिन्दी', direction: 'ltr', is_active: false },
  { code: 'es', name: 'Spanish', native_name: 'Español', direction: 'ltr', is_active: false },
  { code: 'pt', name: 'Portuguese', native_name: 'Português', direction: 'ltr', is_active: false },
  { code: 'zh', name: 'Chinese', native_name: '中文', direction: 'ltr', is_active: false },
  { code: 'de', name: 'German', native_name: 'Deutsch', direction: 'ltr', is_active: false },
  { code: 'ru', name: 'Russian', native_name: 'Русский', direction: 'ltr', is_active: false },
  { code: 'ja', name: 'Japanese', native_name: '日本語', direction: 'ltr', is_active: false },
  { code: 'ko', name: 'Korean', native_name: '한국어', direction: 'ltr', is_active: false },
]

export function normalizeLanguage(language) {
  const code = String(language || '').split('-')[0].toLowerCase()
  return LANGUAGE_OPTIONS.some(option => option.code === code && option.is_active)
    ? code
    : DEFAULT_LANGUAGE
}

export function getLanguageMeta(language) {
  const normalized = normalizeLanguage(language)
  return LANGUAGE_OPTIONS.find(option => option.code === normalized)
    || LANGUAGE_OPTIONS[0]
}

export function getBrowserLanguage() {
  if (typeof navigator === 'undefined') return DEFAULT_LANGUAGE
  return normalizeLanguage(navigator.language || DEFAULT_LANGUAGE)
}

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      fr: { translation: fr },
    },
    lng: getBrowserLanguage(),
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: LANGUAGE_OPTIONS.filter(option => option.is_active).map(option => option.code),
    interpolation: {
      escapeValue: false,
    },
    returnEmptyString: false,
  })

export default i18n
