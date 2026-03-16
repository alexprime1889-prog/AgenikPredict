import service from './index'

export const getBillingStatus = () => {
  return service.get('/api/auth/billing-status')
}

export const getUsageHistory = () => {
  return service.get('/api/auth/usage')
}

export const getBillingPrices = () => {
  return service.get('/api/billing/prices')
}

export const createCheckout = (priceId) => {
  return service.post('/api/billing/checkout', { price_id: priceId })
}
