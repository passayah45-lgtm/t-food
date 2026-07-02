import api from './client'

export const listPartnerDeliveries = () => api.get('/delivery/partner/')
export const getPartnerEarnings = () => api.get('/delivery/partner/earnings/')
export const updateDeliveryStatus = (deliveryId, status, confirmationCode = '') => (
  api.patch(`/delivery/partner/${deliveryId}/status/`, {
    status,
    ...(confirmationCode ? { confirmation_code: confirmationCode } : {}),
  })
)
export const updateDeliveryLocation = (deliveryId, location) => (
  api.patch(`/delivery/partner/${deliveryId}/location/`, location)
)
export const listAvailableDeliveries = () => api.get('/delivery/available/')
export const claimAvailableDelivery = deliveryId => api.post(`/delivery/available/${deliveryId}/claim/`)
export const updateAvailabilityLocation = location => api.patch('/delivery/availability/location/', location)
