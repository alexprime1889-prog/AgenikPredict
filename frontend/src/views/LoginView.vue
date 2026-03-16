<template>
  <div class="login-split">
    <!-- Left: Login form -->
    <div class="login-left">
      <div class="login-card">
        <BorderBeam :size="200" :duration="12" :delay="3" />
        <div class="login-header">
          <div class="brand-row">
            <img src="../assets/logo/agenikpredict_logo_white.png" alt="AgenikAI" class="brand-logo" />
          </div>
          <p class="tagline">{{ $t('hero.tagline') }}</p>
        </div>

      <!-- Step 1: Email input -->
      <div v-if="step === 'email'" class="login-form">
        <h2 class="form-title">{{ $t('auth.signIn') }}</h2>
        <p class="form-desc">{{ $t('auth.enterEmail') }}</p>

        <div class="input-group">
          <input
            v-model="email"
            type="email"
            class="email-input"
            :placeholder="$t('auth.emailPlaceholder')"
            @keydown.enter="sendMagicLink"
            :disabled="loading"
            autofocus
          />
        </div>

        <button
          class="primary-btn"
          @click="sendMagicLink"
          :disabled="!email.trim() || loading"
        >
          <span v-if="!loading">{{ $t('auth.sendLink') }}</span>
          <span v-else class="loading-dots">{{ $t('auth.sending') }}</span>
        </button>

        <div class="divider">
          <span>{{ $t('auth.or') }}</span>
        </div>

        <button class="demo-btn" @click="loginAsDemo" :disabled="loading">
          {{ $t('auth.tryDemo') }}
        </button>

        <p v-if="error" class="error-msg">{{ error }}</p>
      </div>

      <!-- Step 2: Check inbox -->
      <div v-if="step === 'sent'" class="login-form">
        <div class="sent-icon">✉</div>
        <h2 class="form-title">{{ $t('auth.checkInbox') }}</h2>
        <p class="form-desc">
          {{ $t('auth.linkSentTo') }} <strong>{{ email }}</strong>
        </p>
        <p class="form-hint">{{ $t('auth.linkExpiry') }}</p>

        <button class="secondary-btn" @click="step = 'email'">
          {{ $t('auth.useDifferentEmail') }}
        </button>
      </div>
      </div>
      <p class="footer-text">
        &copy; {{ new Date().getFullYear() }} Manogrand Inc
      </p>
    </div>

    <!-- Right: Graph + slogan -->
    <div class="login-right">
      <div class="login-sphere-mask"></div>
      <HeroGraphPreview class="login-graph" />
      <p class="login-slogan">{{ $t('auth.loginSlogan') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { requestMagicLink, demoLogin } from '../store/auth'
import BorderBeam from '../components/magicui/BorderBeam.vue'
import HeroGraphPreview from '../components/HeroGraphPreview.vue'

const router = useRouter()
const email = ref('')
const step = ref('email')
const loading = ref(false)
const error = ref(null)

async function sendMagicLink() {
  if (!email.value.trim()) return
  loading.value = true
  error.value = null
  try {
    await requestMagicLink(email.value.trim())
    step.value = 'sent'
  } catch (err) {
    error.value = err.response?.data?.error || err.message || 'Something went wrong'
  } finally {
    loading.value = false
  }
}

async function loginAsDemo() {
  loading.value = true
  error.value = null
  try {
    await demoLogin()
    router.push('/')
  } catch (err) {
    error.value = err.response?.data?.error || err.message || 'Demo login failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-split {
  min-height: 100vh;
  display: flex;
  background: #0a0a0a;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.login-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  position: relative;
  z-index: 1;
}

.login-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  border-left: 1px solid #1a1a1a;
}

.login-sphere-mask {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  mask-image: radial-gradient(ellipse at center center, #000, transparent 60%);
  -webkit-mask-image: radial-gradient(ellipse at center center, #000, transparent 60%);
}

.login-sphere-mask::before {
  content: '';
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.4;
  background-image: radial-gradient(circle at center 60%, #ffbd7a, transparent 60%);
}

.login-graph {
  width: 90%;
  max-width: 500px;
  height: 400px;
  z-index: 1;
}

.login-slogan {
  margin-top: 40px;
  font-size: 28px;
  font-weight: 600;
  color: #fff;
  text-align: center;
  line-height: 1.3;
  letter-spacing: -0.5px;
  white-space: pre-line;
  z-index: 1;
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 40px 32px;
  background: #111111;
  border: 1px solid #222;
  border-radius: 16px;
  position: relative;
}

@media (max-width: 768px) {
  .login-split {
    flex-direction: column;
  }

  .login-right {
    border-left: none;
    border-top: 1px solid #1a1a1a;
    min-height: 400px;
    padding: 40px 20px;
  }
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.brand-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 8px;
}

.brand-logo {
  height: 36px;
  width: auto;
}

.brand-text-img {
  height: 18px;
  width: auto;
}

.brand {
  font-size: 18px;
  font-weight: 700;
  color: #2E75B6;
  letter-spacing: 3px;
  margin: 0;
}

.tagline {
  font-size: 13px;
  color: #666;
  margin: 4px 0 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-title {
  font-size: 22px;
  font-weight: 600;
  color: #fff;
  margin: 0;
  text-align: center;
}

.form-desc {
  font-size: 14px;
  color: #888;
  margin: 0;
  text-align: center;
  line-height: 1.5;
}

.form-hint {
  font-size: 12px;
  color: #666;
  margin: 0;
  text-align: center;
}

.input-group {
  margin-top: 8px;
}

.email-input {
  width: 100%;
  padding: 14px 16px;
  background: #0a0a0a;
  border: 1px solid #333;
  border-radius: 10px;
  color: #fff;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.email-input:focus {
  border-color: #2E75B6;
}

.email-input::placeholder {
  color: #555;
}

.primary-btn {
  width: 100%;
  padding: 14px;
  background: #2E75B6;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.primary-btn:hover:not(:disabled) {
  background: #245d94;
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 4px 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #222;
}

.divider span {
  font-size: 12px;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.demo-btn {
  width: 100%;
  padding: 12px;
  background: transparent;
  color: #888;
  border: 1px solid #333;
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.demo-btn:hover:not(:disabled) {
  color: #fff;
  border-color: #555;
}

.secondary-btn {
  width: 100%;
  padding: 12px;
  background: transparent;
  color: #2E75B6;
  border: 1px solid #2E75B6;
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 8px;
}

.secondary-btn:hover {
  background: rgba(46, 117, 182, 0.1);
}

.sent-icon {
  text-align: center;
  font-size: 48px;
  margin-bottom: 8px;
}

.error-msg {
  font-size: 13px;
  color: #e74c3c;
  text-align: center;
  margin: 0;
  padding: 10px;
  background: rgba(231, 76, 60, 0.1);
  border-radius: 8px;
}

.loading-dots {
  display: inline-block;
  animation: pulse 1.5s infinite;
}

.footer-text {
  font-size: 12px;
  color: #444;
  margin-top: 24px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
