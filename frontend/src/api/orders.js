import api from './client'

export const listOrders = () => api.get('/orders/')
export const createOrder = payload => api.post('/orders/', payload)
export const getOrder = id => api.get(`/orders/${id}/`)
export const validateOffer = payload => api.post('/orders/offers/validate/', payload)
export const cancelOrder = id => api.post(`/orders/${id}/cancel/`)
export const getReorderPreview = id => api.get(`/orders/${id}/reorder/`)
