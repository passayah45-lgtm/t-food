import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck, PackageCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../api/notifications'
import { useAuth } from '../context/AuthContext'
import { usePreferences } from '../context/PreferencesContext'
import { formatDateTime } from '../lib/formatters'
import useTitle from '../hooks/useTitle'

export default function NotificationsPage() {
  const { t } = useTranslation()
  useTitle(t('notifications.title'))
  const { preferences } = usePreferences()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { role } = useAuth()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => (await listNotifications()).data,
  })
  const notifications = data?.results || data || []

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['notifications'] }),
      queryClient.invalidateQueries({ queryKey: ['notifications-unread'] }),
    ])
  }

  const markAll = async () => {
    await markAllNotificationsRead()
    await refresh()
  }

  const openNotification = async notification => {
    if (!notification.is_read) {
      await markNotificationRead(notification.id)
      await refresh()
    }
    if (role === 'merchant') navigate('/merchant/dashboard')
    else if (role === 'partner') navigate('/partner/dashboard')
    else if (notification.order_id) navigate(`/orders/${notification.order_id}`)
  }

  if (isLoading) {
    return <div className="max-w-3xl mx-auto px-4 py-10 text-gray-500">{t('notifications.loading')}</div>
  }
  if (isError) {
    return <div className="max-w-3xl mx-auto px-4 py-10 text-red-500">{t('notifications.loadError')}</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-950">{t('notifications.title')}</h1>
          <p className="text-gray-500 mt-1">{t('notifications.subtitle')}</p>
        </div>
        {!!notifications.length && (
          <button onClick={markAll} className="btn-secondary inline-flex items-center gap-2 text-sm">
            <CheckCheck size={16} /> {t('notifications.markAllRead')}
          </button>
        )}
      </div>

      {!notifications.length ? (
        <div className="text-center py-16">
          <Bell size={38} className="text-gray-300 mx-auto mb-4" />
          <p className="font-medium text-gray-900">{t('notifications.empty')}</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-200 border-y border-gray-200">
          {notifications.map(notification => (
            <button
              key={notification.id}
              onClick={() => openNotification(notification)}
              className={`w-full py-4 flex items-start gap-4 text-left hover:bg-gray-50 px-2 ${notification.is_read ? '' : 'bg-brand-50/50'}`}
            >
              <div className="h-9 w-9 rounded-lg bg-brand-100 text-brand-700 flex items-center justify-center flex-shrink-0">
                <PackageCheck size={18} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-gray-950">{notification.title}</p>
                  {!notification.is_read && <span className="h-2 w-2 rounded-full bg-brand-500 mt-2 flex-shrink-0" />}
                </div>
                <p className="text-sm text-gray-600 mt-1">{notification.message}</p>
                <p className="text-xs text-gray-400 mt-2">{formatDateTime(notification.created_at, preferences)}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
