import api from './client'

export const listMarketCities = params => api.get('/markets/cities/', { params })
export const listMarketAreas = params => api.get('/markets/areas/', { params })
