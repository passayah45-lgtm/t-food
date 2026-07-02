import api from './client'

export const getPreferences = () => api.get('/preferences/')
export const updatePreferences = data => api.patch('/preferences/', data)
export const getPreferenceOptions = () => api.get('/preferences/options/')
