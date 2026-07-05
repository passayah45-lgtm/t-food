import api from './client'

const asFormData = payload => {
  const form = new FormData()
  Object.entries(payload).forEach(([key, value]) => {
    if (value !== null && value !== undefined) form.append(key, value)
  })
  return form
}
const multipartConfig = { headers: { 'Content-Type': 'multipart/form-data' } }

export const getMerchantProfile = () => api.get('/merchants/profile/')
export const updateMerchantProfile = payload => api.patch('/merchants/profile/', payload)
export const getMerchantSummary = () => api.get('/merchants/summary/')
export const getMerchantAnalytics = (range, branchId) => api.get('/merchants/analytics/', {
  params: {
    range,
    branch_id: branchId || undefined,
  },
})
export const getMerchantPayouts = status => api.get('/merchants/payouts/', { params: status ? { status } : {} })
export const getMerchantNotifications = limit => api.get('/merchants/notifications/', { params: { limit } })
export const listMerchantRestaurants = () => api.get('/merchants/restaurants/')
export const createMerchantRestaurant = payload => api.post('/merchants/restaurants/', asFormData(payload), multipartConfig)
export const updateMerchantRestaurant = (id, payload) => api.patch(`/merchants/restaurants/${id}/`, asFormData(payload), multipartConfig)
export const updateMerchantOperatingHours = (id, hours) => api.put(`/merchants/restaurants/${id}/hours/`, hours)
export const createMerchantItem = (restaurantId, payload) => api.post(`/merchants/restaurants/${restaurantId}/items/`, asFormData(payload), multipartConfig)
export const updateMerchantItem = (restaurantId, itemId, payload) => api.patch(`/merchants/restaurants/${restaurantId}/items/${itemId}/`, asFormData(payload), multipartConfig)
export const deleteMerchantItem = (restaurantId, itemId) => api.delete(`/merchants/restaurants/${restaurantId}/items/${itemId}/`)
export const updateMerchantItemOptions = (restaurantId, itemId, groups) => api.put(`/merchants/restaurants/${restaurantId}/items/${itemId}/options/`, groups)
export const listMerchantOrders = () => api.get('/merchants/orders/')
export const updateMerchantOrderStatus = (orderId, status) => api.patch(`/merchants/orders/${orderId}/status/`, { status })
export const listMerchantRiders = params => api.get('/merchants/riders/', { params })
export const inviteMerchantRider = payload => api.post('/merchants/riders/invite/', payload)
export const updateMerchantRiderStatus = (riderId, status) => api.patch(`/merchants/riders/${riderId}/status/`, { status })
export const assignMerchantRiderRestaurant = (riderId, homeRestaurant) => (
  api.post(`/merchants/riders/${riderId}/assign-restaurant/`, { home_restaurant: homeRestaurant || null })
)
export const listNearbyMerchants = params => api.get('/merchants/network/nearby/', { params })
export const listMerchantNetwork = () => api.get('/merchants/network/')
export const createMerchantNetworkRequest = payload => api.post('/merchants/network/requests/', payload)
export const updateMerchantNetworkRelationship = (relationshipId, action) => (
  api.patch(`/merchants/network/${relationshipId}/`, { action })
)
export const listMerchantFulfillmentRequests = () => api.get('/merchants/network/fulfillment-requests/')
export const createMerchantFulfillmentRequest = payload => api.post('/merchants/network/fulfillment-requests/', payload)
export const updateMerchantFulfillmentRequest = (requestId, action) => (
  api.patch(
    `/merchants/network/fulfillment-requests/${requestId}/`,
    typeof action === 'string' ? { action } : action,
  )
)
export const listMerchantStaff = () => api.get('/merchants/staff/')
export const inviteMerchantStaff = payload => api.post('/merchants/staff/invite/', payload)
export const updateMerchantStaff = (staffId, payload) => api.patch(`/merchants/staff/${staffId}/`, payload)
export const assignMerchantStaffBranches = (staffId, branchIds) => (
  api.post(`/merchants/staff/${staffId}/branches/`, { branch_ids: branchIds })
)
export const removeMerchantStaffBranch = (staffId, branchId) => (
  api.delete(`/merchants/staff/${staffId}/branches/${branchId}/`)
)
