import { useEffect, useMemo, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { Bot, Mic, MicOff, Send, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { askAssistant } from '../../api/intelligence'
import { usePreferences } from '../../context/PreferencesContext'

const speechLanguageFor = language => {
  if ((language || '').toLowerCase().startsWith('fr')) return 'fr-FR'
  return 'en-US'
}

export default function TfoodAssistantPanel({
  surface,
  title,
  subtitle,
  placeholder,
  compact = false,
}) {
  const { t } = useTranslation()
  const { preferences } = usePreferences() || {}
  const [message, setMessage] = useState('')
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(false)
  const recognitionRef = useRef(null)
  const speechBaseMessageRef = useRef('')
  const language = preferences?.language || 'en'

  const speechLanguage = useMemo(() => speechLanguageFor(language), [language])

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setSpeechSupported(Boolean(SpeechRecognition))

    if (!SpeechRecognition) return undefined

    const recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = speechLanguage

    recognition.onresult = event => {
      let transcript = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index][0]?.transcript || ''
      }
      const base = speechBaseMessageRef.current.trim()
      const spoken = transcript.trim()
      setMessage([base, spoken].filter(Boolean).join(' '))
    }

    recognition.onerror = () => {
      setListening(false)
      toast.error(t('assistant.voiceError'))
    }

    recognition.onend = () => {
      setListening(false)
    }

    recognitionRef.current = recognition

    return () => {
      try {
        recognition.stop()
      } catch (error) {
        // Some browsers throw if stop is called after recognition already ended.
      }
      recognitionRef.current = null
    }
  }, [speechLanguage, t])

  const submit = async event => {
    event.preventDefault()
    const trimmed = message.trim()
    if (!trimmed || loading) return
    setLoading(true)
    setAnswer('')
    try {
      const { data } = await askAssistant({
        surface,
        message: trimmed,
        language: preferences?.language || 'en',
      })
      setAnswer(data.answer || t('assistant.emptyAnswer'))
    } catch (error) {
      const detail = error.response?.data?.detail || error.response?.data?.message?.[0]
      toast.error(detail || t('assistant.error'))
    } finally {
      setLoading(false)
    }
  }

  const toggleVoiceInput = () => {
    if (!speechSupported || !recognitionRef.current) {
      toast.error(t('assistant.voiceUnsupported'))
      return
    }

    if (listening) {
      recognitionRef.current.stop()
      setListening(false)
      return
    }

    speechBaseMessageRef.current = message
    recognitionRef.current.lang = speechLanguage
    try {
      recognitionRef.current.start()
      setListening(true)
    } catch (error) {
      setListening(false)
      toast.error(t('assistant.voiceError'))
    }
  }

  return (
    <section className={`card ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="h-10 w-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
            <Bot size={20} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-950">{title || t(`assistant.${surface}Title`)}</h2>
            <p className="text-sm text-gray-500 mt-1">{subtitle || t(`assistant.${surface}Subtitle`)}</p>
          </div>
        </div>
        {(message || answer) && (
          <button
            type="button"
            className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"
            onClick={() => {
              setMessage('')
              setAnswer('')
            }}
          >
            <Trash2 size={15} />
            {t('assistant.clearChat')}
          </button>
        )}
      </div>

      <form onSubmit={submit} className="mt-4 space-y-3">
        <textarea
          value={message}
          onChange={event => setMessage(event.target.value)}
          maxLength={2000}
          rows={compact ? 3 : 4}
          className="input-field resize-none"
          placeholder={placeholder || t('assistant.placeholder')}
        />
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p className="text-xs text-gray-500">{t('assistant.guidanceOnly')}</p>
          <div className="flex flex-col sm:flex-row gap-2">
            <button
              type="button"
              disabled={!speechSupported}
              className="btn-secondary inline-flex items-center justify-center gap-2"
              onClick={toggleVoiceInput}
              title={speechSupported ? t('assistant.voiceInput') : t('assistant.voiceUnsupported')}
            >
              {listening ? <MicOff size={15} /> : <Mic size={15} />}
              {listening ? t('assistant.stopVoice') : t('assistant.voiceInput')}
            </button>
            <button type="submit" disabled={loading || !message.trim()} className="btn-primary inline-flex items-center justify-center gap-2">
              <Send size={15} />
              {loading ? t('assistant.asking') : t('assistant.ask')}
            </button>
          </div>
        </div>
      </form>

      {answer && (
        <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700 whitespace-pre-wrap">
          {answer}
        </div>
      )}
    </section>
  )
}
