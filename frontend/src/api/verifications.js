import api from './client'

export const listMerchantVerificationDocuments = () => api.get('/verifications/merchant/documents/')

export const uploadMerchantVerificationDocument = payload => (
  api.post('/verifications/merchant/documents/', payload)
)

export const deleteMerchantVerificationDocument = documentId => (
  api.delete(`/verifications/merchant/documents/${documentId}/`)
)

export const listPartnerVerificationDocuments = () => api.get('/verifications/partner/documents/')

export const uploadPartnerVerificationDocument = payload => (
  api.post('/verifications/partner/documents/', payload)
)

export const deletePartnerVerificationDocument = documentId => (
  api.delete(`/verifications/partner/documents/${documentId}/`)
)
