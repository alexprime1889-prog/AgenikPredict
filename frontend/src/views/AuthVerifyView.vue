<template>
  <div class="verify-container">
    <div class="verify-card">
      <div v-if="verifying" class="verify-state">
        <div class="spinner"></div>
        <p class="verify-text">{{ $t('auth.verifying') }}</p>
      </div>

      <div v-else-if="error" class="verify-state">
        <div class="error-icon">!</div>
        <h2 class="verify-title">{{ $t('auth.linkExpired') }}</h2>
        <p class="verify-text">{{ error }}</p>
        <button class="primary-btn" @click="$router.push('/login')">
          {{ $t('auth.requestNewLink') }}
        </button>
      </div>

      <div v-else class="verify-state">
        <div class="success-icon">&#10003;</div>
        <h2 class="verify-title">{{ $t('auth.signedIn') }}</h2>
        <p class="verify-text">{{ $t('auth.redirecting') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { verifyToken } from '../store/auth'

const router = useRouter()
const route = useRoute()
const verifying = ref(true)
const error = ref(null)

onMounted(async () => {
  const token = route.query.token
  if (!token) {
    error.value = 'No token provided'
    verifying.value = false
    return
  }

  try {
    await verifyToken(token)
    verifying.value = false
    // Redirect to home after brief success message
    setTimeout(() => router.push('/'), 1200)
  } catch (err) {
    error.value = err.response?.data?.error || err.message || 'Verification failed'
    verifying.value = false
  }
})
</script>

<style scoped>
.verify-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a0a;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.verify-card {
  width: 100%;
  max-width: 400px;
  padding: 48px 32px;
  background: #111111;
  border: 1px solid #222;
  border-radius: 16px;
  text-align: center;
}

.verify-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #222;
  border-top-color: #2E75B6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.verify-title {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin: 0;
}

.verify-text {
  font-size: 14px;
  color: #888;
  margin: 0;
}

.error-icon {
  width: 48px;
  height: 48px;
  background: rgba(231, 76, 60, 0.15);
  color: #e74c3c;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
}

.success-icon {
  width: 48px;
  height: 48px;
  background: rgba(46, 204, 113, 0.15);
  color: #2ecc71;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
}

.primary-btn {
  padding: 12px 32px;
  background: #2E75B6;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
}

.primary-btn:hover {
  background: #245d94;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
