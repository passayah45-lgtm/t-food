import api from './client'

export const listNotifications = params => api.get('/notifications/', { params })
export const getUnreadNotifications = () => api.get('/notifications/unread/')
export const markNotificationRead = id => api.post(`/notifications/${id}/read/`)
export const patchNotificationRead = id => api.patch(`/notifications/${id}/read/`)
export const markAllNotificationsRead = () => api.post('/notifications/read-all/')
export const archiveNotification = id => api.patch(`/notifications/${id}/archive/`)
export const dismissNotification = id => api.patch(`/notifications/${id}/dismiss/`)
export const archiveReadNotifications = () => api.post('/notifications/archive-read/')
export const markNotificationsByFilter = data => api.post('/notifications/mark-by-filter/', data)
export const getNotificationPreferences = () => api.get('/notifications/preferences/')
export const updateNotificationPreferences = data => api.patch('/notifications/preferences/', data)
