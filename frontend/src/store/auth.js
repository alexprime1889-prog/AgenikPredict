/**
 * Auth store — reactive authentication state
 * Uses localStorage for JWT persistence
 */

import { reactive, ref, computed } from 'vue'
import service from '../api/index'
import { getBillingStatus } from '../api/billing'

const TOKEN_KEY = 'agenikpredict-token'
const USER_KEY = 'agenikpredict-user'

const state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || null,
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  loading: false,
  error: null,
})

// ── Computed ──
export const isAuthenticated = computed(() => !!state.token)
export const currentUser = computed(() => state.user)
export const userPlan = computed(() => state.user?.plan || 'explorer')
export const userRole = computed(() => state.user?.role || 'user')
export const isAdmin = computed(() => state.user?.role === 'admin')
export const authLoading = computed(() => state.loading)
export const authError = computed(() => state.error)

// ── Billing State ──
const billingStatus = ref(null)

export const isTrialActive = computed(() => billingStatus.value?.is_trial || false)
export const trialDaysLeft = computed(() => billingStatus.value?.trial_days_left || 0)
export const balanceCents = computed(() => billingStatus.value?.balance_cents || 0)
export const canGenerate = computed(() => billingStatus.value?.can_generate !== false)

export async function fetchBillingStatus() {
  try {
    const res = await getBillingStatus()
    if (res.success) {
      billingStatus.value = res.data
    }
  } catch (_e) {
    // Ignore billing errors silently
  }
}

// ── Actions ──

export async function requestMagicLink(email) {
  state.loading = true
  state.error = null
  try {
    const res = await service.post('/api/auth/request', { email })
    return res
  } catch (err) {
    state.error = err.response?.data?.error || err.message || 'Failed to send magic link'
    throw err
  } finally {
    state.loading = false
  }
}

export async function verifyToken(token) {
  state.loading = true
  state.error = null
  try {
    const res = await service.get(`/api/auth/verify?token=${token}`)
    if (res.success && res.token) {
      setAuth(res.token, res.user)
      fetchBillingStatus()
    }
    return res
  } catch (err) {
    state.error = err.response?.data?.error || err.message || 'Invalid or expired link'
    throw err
  } finally {
    state.loading = false
  }
}

export async function demoLogin() {
  state.loading = true
  state.error = null
  try {
    const res = await service.post('/api/auth/demo')
    if (res.success && res.token) {
      setAuth(res.token, res.user)
      fetchBillingStatus()
    }
    return res
  } catch (err) {
    state.error = err.response?.data?.error || err.message || 'Demo login failed'
    throw err
  } finally {
    state.loading = false
  }
}

export async function fetchCurrentUser() {
  if (!state.token) return null
  try {
    const res = await service.get('/api/auth/me')
    if (res.success && res.user) {
      state.user = res.user
      localStorage.setItem(USER_KEY, JSON.stringify(res.user))
      fetchBillingStatus()
    }
    return res.user
  } catch {
    // Token invalid — clear auth
    logout()
    return null
  }
}

export function setAuth(token, user) {
  state.token = token
  state.user = user
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function logout() {
  state.token = null
  state.user = null
  state.error = null
  billingStatus.value = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getToken() {
  return state.token
}

export default state
