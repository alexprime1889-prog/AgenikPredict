import axios from 'axios'

// Create axios instance
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  timeout: 300000, // 5-minute timeout (ontology generation may take a long time)
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
service.interceptors.request.use(
  config => {
    // Pass the user's selected locale to the backend for LLM language support
    const locale = localStorage.getItem('agenikpredict-locale') || 'en'
    config.headers['Accept-Language'] = locale

    // Attach JWT token if available
    const token = localStorage.getItem('agenikpredict-token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor (fault-tolerant retry mechanism)
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // If the returned status is not success, throw an error
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    console.debug('Response error:', error)

    if (error.response?.status === 401) {
      localStorage.removeItem('agenikpredict-token')
      localStorage.removeItem('agenikpredict-user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
    
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }
    
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }

    // For 402 Payment Required, return structured response instead of rejecting
    // so callers can inspect the error details and show payment UI
    if (error.response && error.response.status === 402) {
      return {
        success: false,
        status: 402,
        data: error.response.data,
        error: error.response.data?.error || 'payment_required'
      }
    }

    return Promise.reject(error)
  }
)

// Request function with retry
// Only retries on 5xx or network errors. 4xx client errors are not retried.
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const result = await requestFn()
      // If the response interceptor returned a structured 402 response (not thrown),
      // return it directly without retrying
      if (result && result.status === 402) {
        return result
      }
      return result
    } catch (error) {
      // Do not retry on 4xx client errors — only retry on 5xx or network failures
      const status = error.response?.status
      if (status && status >= 400 && status < 500) {
        throw error
      }

      if (i === maxRetries - 1) throw error

      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
