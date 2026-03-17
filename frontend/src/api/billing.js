import service from './index'

export async function getBillingStatus() {
  try {
    const res = await service.get('/api/billing/status')
    return { success: true, data: res.data }
  } catch (err) {
    return { success: false, data: null }
  }
}
