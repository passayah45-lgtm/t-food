import { useState } from 'react'
import toast from 'react-hot-toast'
import { Bot, Send } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { askAssistant } from '../../api/intelligence'

export default function TfoodAssistantPanel({
  surface,
  title,
  subtitle,
  placeholder,
  compact = false,
}) {
  const { t } = useTranslation()
  const [message, setMessage] = useState('')
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async event => {
    event.preventDefault()
    const trimmed = message.trim()
    if (!trimmed || loading) return
    setLoading(true)
    setAnswer('')
    try {
      const { data } = await askAssistant({ surface, message: trimmed })
      setAnswer(data.answer || t('assistant.emptyAnswer'))
    } catch (error) {
      const detail = error.response?.data?.detail || error.response?.data?.message?.[0]
      toast.error(detail || t('assistant.error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className={`card ${compact ? 'p-4' : 'p-5'}`}>
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
          <Bot size={20} />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-950">{title || t(`assistant.${surface}Title`)}</h2>
          <p className="text-sm text-gray-500 mt-1">{subtitle || t(`assistant.${surface}Subtitle`)}</p>
        </div>
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
          <button type="submit" disabled={loading || !message.trim()} className="btn-primary inline-flex items-center justify-center gap-2">
            <Send size={15} />
            {loading ? t('assistant.asking') : t('assistant.ask')}
          </button>
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
