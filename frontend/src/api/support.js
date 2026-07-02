import api from './client'

export const listSupportTickets = () => api.get('/support/tickets/')
export const createSupportTicket = payload => api.post('/support/tickets/', payload)
