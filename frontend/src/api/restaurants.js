import api from './client'

export const listRestaurants = params => api.get('/restaurants/', { params })
export const getRestaurant = (id, params) => api.get(`/restaurants/${id}/`, { params })
export const listRestaurantReviews = id => api.get(`/restaurants/${id}/reviews/`)
export const createRestaurantReview = (id, payload) => (
  api.post(`/restaurants/${id}/reviews/`, payload)
)
export const listReviewPhotos = (restaurantId, reviewId) => (
  api.get(`/restaurants/${restaurantId}/reviews/${reviewId}/photos/`)
)
export const uploadReviewPhoto = (restaurantId, reviewId, file, caption = '', config = {}) => {
  const formData = new FormData()
  formData.append('image', file)
  if (caption) formData.append('caption', caption)
  return api.post(`/restaurants/${restaurantId}/reviews/${reviewId}/photos/`, formData, config)
}
export const deleteReviewPhoto = (restaurantId, reviewId, photoId) => (
  api.delete(`/restaurants/${restaurantId}/reviews/${reviewId}/photos/${photoId}/`)
)
export const listFavoriteRestaurants = () => api.get('/restaurants/favorites/')
export const toggleFavoriteRestaurant = id => api.post(`/restaurants/${id}/favorite/`)
