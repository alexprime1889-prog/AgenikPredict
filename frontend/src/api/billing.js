import service, { requestWithRetry } from './index'

export async function getBillingStatus() {
  try {
    return await service.get('/api/billing/status')
  } catch (_err) {
    return { success: false, data: null }
  }
}

export function getBillingPrices() {
  return requestWithRetry(() => service.get('/api/billing/prices'))
}

export function createCheckout(priceId) {
  return requestWithRetry(() =>
    service.post('/api/billing/checkout', { price_id: priceId })
  )
}
