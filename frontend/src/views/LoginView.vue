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
      <p class="login-tagline">{{ $t('auth.loginTagline') }}</p>
      <p class="footer-text">
        &copy; {{ new Date().getFullYear() }} Manogrand Inc
      </p>
    </div>

    <!-- Right: Full 3D graph playground -->
    <div class="login-right">
      <div ref="graphMount" class="login-3d-graph"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { requestMagicLink, demoLogin } from '../store/auth'
import BorderBeam from '../components/magicui/BorderBeam.vue'
import ForceGraph3D from '3d-force-graph'
import SpriteText from 'three-spritetext'
import * as THREE from 'three'

const router = useRouter()
const email = ref('')
const graphMount = ref(null)
let graphInstance = null

const COLORS = {
  Person: '#FF6B35', Investor: '#004E89', Company: '#7B2D8E',
  Founder: '#1A936F', FinancialInstitution: '#C5283D',
  GovernmentAgency: '#E9724C', Entity: '#3498db'
}

onMounted(async () => {
  if (!graphMount.value) return

  let graphData, translations = {}
  try {
    let graphRes = await fetch('/production-graph.json')
    if (!graphRes.ok) graphRes = await fetch('/demo-graph.json')
    graphData = await graphRes.json()
    try {
      const transRes = await fetch('/graph-translations.json')
      if (transRes.ok) {
        const allTrans = await transRes.json()
        const currentLocale = localStorage.getItem('agenikpredict-locale') || 'en'
        translations = allTrans[currentLocale] || allTrans.en || {}
      }
    } catch {}
  } catch (e) {
    console.error('Graph load failed:', e)
    return
  }

  const data = graphData.data || graphData
  const nodesRaw = data.nodes || []
  const edgesRaw = data.edges || []

  const nodes = []
  const links = []
  const nodeMap = new Map()

  for (const n of nodesRaw) {
    const type = n.labels?.find(l => l !== 'Entity') || 'Entity'
    const originalName = n.name || 'Unnamed'
    const node = { id: n.uuid, name: translations[originalName] || originalName, type, val: 1 }
    nodeMap.set(n.uuid, node)
    nodes.push(node)
  }

  const nodeIds = new Set(nodes.map(n => n.id))

  for (const e of edgesRaw) {
    if (nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid)) {
      links.push({ source: e.source_node_uuid, target: e.target_node_uuid, name: e.name || '' })
      const src = nodeMap.get(e.source_node_uuid)
      const tgt = nodeMap.get(e.target_node_uuid)
      if (src) src.val += 0.5
      if (tgt) tgt.val += 0.5
    }
  }

  const el = graphMount.value
  const width = el.clientWidth
  const height = el.clientHeight

  graphInstance = ForceGraph3D()(el)
    .width(width)
    .height(height)
    .graphData({ nodes, links })
    .backgroundColor('rgba(0,0,0,0)')
    .showNavInfo(false)
    .nodeThreeObject(node => {
      const color = COLORS[node.type] || '#999'
      const radius = Math.max(3, Math.sqrt(node.val) * 2.5)
      const group = new THREE.Group()
      group.add(new THREE.Mesh(
        new THREE.SphereGeometry(radius, 20, 20),
        new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0.9 })
      ))
      group.add(new THREE.Mesh(
        new THREE.SphereGeometry(radius * 1.5, 16, 16),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.12 })
      ))
      const label = new SpriteText(node.name.length > 12 ? node.name.slice(0, 10) + '…' : node.name)
      label.color = '#E0E0E0'
      label.textHeight = 3
      label.position.set(0, -(radius + 5), 0)
      label.backgroundColor = false
      group.add(label)
      return group
    })
    .nodeLabel(() => '')
    .linkColor(() => 'rgba(255,255,255,0.15)')
    .linkWidth(0.5)
    .linkOpacity(0.5)
    .onNodeClick(() => {})
    .enableNodeDrag(false)
    .d3AlphaDecay(0.03)
    .d3VelocityDecay(0.25)
    .warmupTicks(100)
    .cooldownTicks(0)

  graphInstance.controls().autoRotate = true
  graphInstance.controls().autoRotateSpeed = 0.6
  graphInstance.controls().enableZoom = true
  graphInstance.controls().enablePan = false

  setTimeout(() => {
    if (graphInstance) graphInstance.cameraPosition({ x: 0, y: 0, z: 280 })
  }, 500)
})

onUnmounted(() => {
  if (graphInstance) {
    graphInstance._destructor?.()
    graphInstance = null
  }
})
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

.login-3d-graph {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
}

.login-slogan {
  position: absolute;
  bottom: 40px;
  left: 0;
  right: 0;
  font-size: 24px;
  font-weight: 600;
  color: #fff;
  text-align: center;
  line-height: 1.3;
  letter-spacing: -0.5px;
  white-space: pre-line;
  z-index: 2;
  text-shadow: 0 2px 20px rgba(0,0,0,0.8);
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

.login-tagline {
  margin-top: 20px;
  font-size: 13px;
  color: #555;
  text-align: center;
  max-width: 300px;
  line-height: 1.5;
  font-style: italic;
}

.footer-text {
  font-size: 12px;
  color: #444;
  margin-top: 16px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
