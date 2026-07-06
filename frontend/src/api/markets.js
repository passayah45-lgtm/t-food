import api from './client'

export const listMarkets = params => api.get('/markets/', { params })
export const listCurrencies = params => api.get('/markets/currencies/', { params })
export const createCurrency = payload => api.post('/markets/currencies/', payload)
export const createMarket = payload => api.post('/markets/', payload)
export const listMarketCities = params => api.get('/markets/cities/', { params })
export const listMarketAreas = params => api.get('/markets/areas/', { params })
export const createMarketCity = payload => api.post('/markets/cities/', payload)
export const createMarketArea = payload => api.post('/markets/areas/', payload)
