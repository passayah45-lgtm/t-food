import api from './client'

export const getOperationsSummary = params => api.get('/operations/summary/', { params })
export const listOperationsCustomers = params => api.get('/operations/customers/', { params })
export const listOperationsBranches = params => api.get('/operations/branches/', { params })
export const updateOperationsBranchStatus = (branchId, payload) => (
  api.patch(`/operations/branches/${branchId}/status/`, payload)
)
export const listOperationsRestaurants = params => api.get('/operations/restaurants/', { params })
export const listOperationsOrders = params => api.get('/operations/orders/', { params })
export const getOperationsRevenue = params => api.get('/operations/revenue/', { params })
export const getOperationsLedger = params => api.get('/operations/ledger/', { params })
export const listOperationsNotifications = params => api.get('/operations/notifications/', { params })
export const markOperationsNotificationRead = notificationId => (
  api.patch(`/operations/notifications/${notificationId}/read/`)
)
export const archiveOperationsNotification = notificationId => (
  api.patch(`/operations/notifications/${notificationId}/archive/`)
)
export const dismissOperationsNotification = notificationId => (
  api.patch(`/operations/notifications/${notificationId}/dismiss/`)
)
export const markAllOperationsNotificationsRead = () => api.post('/operations/notifications/read-all/')
export const listOperationsOffers = params => api.get('/operations/offers/', { params })
export const createOperationsOffer = payload => api.post('/operations/offers/', payload)
export const updateOperationsOffer = (offerId, payload) => (
  api.patch(`/operations/offers/${offerId}/`, payload)
)
export const listPaymentProviderConfigs = params => api.get('/operations/payment-providers/', { params })
export const createPaymentProviderConfig = payload => api.post('/operations/payment-providers/', payload)
export const updatePaymentProviderConfig = (configId, payload) => (
  api.patch(`/operations/payment-providers/${configId}/`, payload)
)
export const listOperationsMerchants = params => api.get('/operations/merchants/', { params })
const verificationPayload = value => (
  typeof value === 'boolean' ? { is_verified: value } : value
)
export const updateMerchantVerification = (merchantId, payload) => (
  api.patch(`/operations/merchants/${merchantId}/status/`, verificationPayload(payload))
)
export const listOperationsPartners = params => api.get('/operations/partners/', { params })
export const updatePartnerVerification = (partnerId, payload) => (
  api.patch(`/operations/partners/${partnerId}/status/`, verificationPayload(payload))
)
export const listOperationsMerchantDocuments = merchantId => api.get(`/operations/merchants/${merchantId}/documents/`)
export const listOperationsPartnerDocuments = partnerId => api.get(`/operations/partners/${partnerId}/documents/`)
export const listOperationsStaff = params => api.get('/operations/staff/', { params })
export const listOperationsStaffDocuments = staffId => api.get(`/operations/staff/${staffId}/documents/`)
export const updateOperationsStaffVerification = (staffId, payload) => (
  api.patch(`/operations/staff/${staffId}/verification/`, payload)
)
export const reviewOperationsStaffDocument = (documentId, payload) => (
  api.patch(`/operations/staff/documents/${documentId}/review/`, payload)
)
export const reviewOperationsVerificationDocument = (documentId, payload) => (
  api.patch(`/operations/verification-documents/${documentId}/review/`, payload)
)
export const listOperationsSupportTickets = params => api.get('/operations/support/', { params })
export const updateSupportTicket = (ticketId, payload) => (
  api.patch(`/operations/support/${ticketId}/status/`, payload)
)
export const listOperationsReviewPhotos = params => api.get('/operations/review-photos/', { params })
export const moderateOperationsReviewPhoto = (photoId, payload) => (
  api.patch(`/operations/review-photos/${photoId}/`, payload)
)
export const listOperationsDispatch = params => api.get('/operations/dispatch/', { params })
export const assignOperationsDelivery = (deliveryId, partnerId) => (
  api.patch(`/operations/dispatch/${deliveryId}/assign/`, { partner_id: partnerId })
)
export const listOperationsFulfillmentRequests = params => api.get('/operations/fulfillment-requests/', { params })
export const updateOperationsFulfillmentRequest = (requestId, payload) => (
  api.patch(`/operations/fulfillment-requests/${requestId}/`, payload)
)
export const listPartnerPayouts = params => api.get('/operations/payouts/partners/', { params })
export const markPartnerPayoutPaid = deliveryId => api.post(`/operations/payouts/partners/${deliveryId}/pay/`)
export const listMerchantPayouts = params => api.get('/operations/payouts/merchants/', { params })
export const markMerchantPayoutPaid = orderId => api.post(`/operations/payouts/merchants/${orderId}/pay/`)
export const getOperationsAccessMe = () => api.get('/operations/access/me/')
export const listOperationsAccessStaff = () => api.get('/operations/access/staff/')
export const createOperationsAccessStaff = payload => api.post('/operations/access/staff/', payload)
export const updateOperationsAccessStaff = (profileId, payload) => (
  api.patch(`/operations/access/staff/${profileId}/`, payload)
)
export const assignOperationsAccessMarket = (profileId, marketId) => (
  api.post(`/operations/access/staff/${profileId}/markets/`, { market_id: Number(marketId) })
)
export const assignOperationsAccessCity = (profileId, cityId) => (
  api.post(`/operations/access/staff/${profileId}/cities/`, { city_id: Number(cityId) })
)
export const assignOperationsAccessArea = (profileId, areaId) => (
  api.post(`/operations/access/staff/${profileId}/areas/`, { area_id: Number(areaId) })
)
export const removeOperationsAccessMarket = (profileId, marketId) => (
  api.delete(`/operations/access/staff/${profileId}/markets/${marketId}/`)
)
export const removeOperationsAccessCity = (profileId, cityId) => (
  api.delete(`/operations/access/staff/${profileId}/cities/${cityId}/`)
)
export const removeOperationsAccessArea = (profileId, areaId) => (
  api.delete(`/operations/access/staff/${profileId}/areas/${areaId}/`)
)
