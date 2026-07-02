import api from './client'

export const getCustomerRecommendations = params => (
  api.get('/intelligence/customer/recommendations/', { params })
)

export const trackRecommendationEvent = payload => (
  api.post('/intelligence/events/', payload)
)

export const trackSearchEvent = payload => (
  api.post('/intelligence/search-events/', payload)
)

export const visualProductSearch = payload => (
  api.post('/intelligence/visual-product-search/', payload)
)

export const getMerchantInsights = () => (
  api.get('/intelligence/merchant/insights/')
)

export const getOperationsInsights = params => (
  api.get('/intelligence/operations/insights/', { params })
)
