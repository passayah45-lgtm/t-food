import api from './client'

export const payForOrder = (orderId, method) => (
  api.post(`/payments/orders/${orderId}/`, { method })
)
export const getPaymentConfig = () => api.get('/payments/config/')
export const verifyPayment = (orderId, payload) => (
  api.post(`/payments/orders/${orderId}/verify/`, payload)
)
