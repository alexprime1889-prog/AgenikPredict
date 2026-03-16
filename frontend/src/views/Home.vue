<template>
  <div class="home-container">
    <ParticlesBackground class="particles-bg" :quantity="50" color="#ffffff" :size="0.05" :staticity="40" :ease="70" />

    <!-- Top navigation bar -->
    <nav class="navbar">
      <div class="nav-brand">{{ $t('brand') }}</div>
      <div class="nav-links">
        <span v-if="userEmail" class="nav-user">{{ userEmail }}</span>
        <BillingBadge />
        <LanguageSwitcher />
        <button v-if="isLoggedIn" class="nav-logout" @click="handleLogout">{{ $t('auth.logout') }}</button>
      </div>
    </nav>

    <div class="main-content">
      <!-- Upper section: Hero area -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row animate-fade-in" style="--animation-delay: 0ms">
            <span class="orange-tag animate-shimmer">{{ $t('hero.tagline') }}</span>
          </div>

          <h1 class="main-title animate-fade-in" style="--animation-delay: 200ms">
            {{ $t('hero.title.line1') }}<br>
            <span class="gradient-text">{{ $t('hero.title.line2') }}</span>
          </h1>

          <div class="hero-desc animate-fade-in" style="--animation-delay: 400ms">
            <p v-html="$t('hero.desc', { brand: 'AgenikPredict', agentCount: $t('hero.agentCount'), optimalSolution: $t('hero.optimalSolution') })"></p>
            <p class="slogan-text">
              {{ $t('hero.slogan') }}<span class="blinking-cursor">_</span>
            </p>
          </div>

          <div class="decoration-square animate-fade-in" style="--animation-delay: 600ms"></div>
        </div>

        <div class="hero-right">
          <HeroGraphPreview />

          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- Lower section: Two-column layout -->
      <section class="dashboard-section">
        <!-- Left column: Status and steps -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> {{ $t('status.systemStatus') }}
          </div>

          <h2 class="section-title">{{ $t('status.ready') }}</h2>
          <p class="section-desc">
            {{ $t('status.readyDesc') }}
          </p>

          <!-- Metrics cards -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">{{ $t('metrics.lowCost') }}</div>
              <div class="metric-label">{{ $t('metrics.lowCostDesc') }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">{{ $t('metrics.highAvail') }}</div>
              <div class="metric-label">{{ $t('metrics.highAvailDesc') }}</div>
            </div>
          </div>

          <!-- Workflow steps -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> {{ $t('workflow.title') }}
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('steps.graphBuild') }}</div>
                  <div class="step-desc">{{ $t('steps.graphBuildDesc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('steps.envSetup') }}</div>
                  <div class="step-desc">{{ $t('steps.envSetupDesc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('steps.simulation') }}</div>
                  <div class="step-desc">{{ $t('steps.simulationDesc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('steps.report') }}</div>
                  <div class="step-desc">{{ $t('steps.reportDesc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('steps.interaction') }}</div>
                  <div class="step-desc">{{ $t('steps.interactionDesc') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right column: Interactive console -->
        <div class="right-panel">
          <div class="console-box">
            <BorderBeam :size="200" :duration="12" :delay="11" />

            <!-- Upload area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('console.realitySeed') }}</span>
                <span class="console-meta">{{ $t('console.supportedFormatsLong') }}</span>
              </div>

              <div
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt,.jpg,.jpeg,.png,.webp,.gif,.bmp,.mp4,.mov,.avi,.webm,.mkv"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />

                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">{{ $t('upload.dragFiles') }}</div>
                  <div class="upload-hint">{{ $t('upload.browseFiles') }}</div>
                  <div class="upload-accepts">{{ $t('upload.acceptsLabel') }}</div>
                </div>

                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">{{ getFileIcon(file.name) }}</span>
                    <span class="file-name">{{ file.name }}</span>
                    <span class="file-type-badge">{{ getFileTypeBadge(file.name) }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>

              <div class="url-input-row">
                <svg class="url-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                <input
                  v-model="urlInput"
                  type="url"
                  class="url-field"
                  :placeholder="$t('upload.urlPlaceholder')"
                  :disabled="loading"
                  @keydown.enter.prevent="addUrl"
                />
                <button class="url-add-btn" @click="addUrl" :disabled="!urlInput.trim() || loading">+</button>
              </div>

              <div v-if="urls.length > 0" class="url-list">
                <div v-for="(url, index) in urls" :key="url" class="file-item">
                  <span class="file-icon">{{ isYouTubeUrl(url) ? '▶' : '🔗' }}</span>
                  <span class="file-name">{{ url }}</span>
                  <span class="file-type-badge">{{ isYouTubeUrl(url) ? 'YT' : 'URL' }}</span>
                  <button @click.stop="removeUrl(index)" class="remove-btn">×</button>
                </div>
              </div>
            </div>

            <!-- Divider -->
            <div class="console-divider">
              <span>{{ $t('console.inputParams') }}</span>
            </div>

            <!-- Input area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('console.simulationPrompt') }}</span>
              </div>
              <div class="template-chips">
                <button
                  v-for="tmpl in promptTemplates"
                  :key="tmpl.label"
                  class="template-chip"
                  :class="{ active: formData.simulationRequirement === tmpl.prompt }"
                  @click="applyTemplate(tmpl)"
                  :disabled="loading"
                >
                  <svg v-if="tmpl.label === 'Investment'" class="chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                  <svg v-else-if="tmpl.label === 'Marketing'" class="chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 11 18-5v12L3 13v-2z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/></svg>
                  <svg v-else-if="tmpl.label === 'Hiring'" class="chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/></svg>
                  <svg v-else-if="tmpl.label === 'Political'" class="chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
                  <svg v-else-if="tmpl.label === 'Risk'" class="chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>
                  <svg v-else-if="tmpl.label === 'Product'" class="chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
                  <span class="chip-label">{{ tmpl.label }}</span>
                </button>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  :placeholder="$t('console.placeholder')"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">{{ $t('console.engineBadge') }}</div>
              </div>
            </div>

            <!-- Start button -->
            <div class="console-section btn-section">
              <label class="market-data-toggle">
                <input type="checkbox" v-model="enrichWithMarketData" :disabled="loading" />
                <span class="toggle-text">{{ $t('console.enrichMarketData') }}</span>
              </label>
              <button
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">{{ $t('console.startEngine') }}</span>
                <span v-else>{{ $t('console.initializing') }}</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- History database -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import BillingBadge from '../components/BillingBadge.vue'
import ParticlesBackground from '../components/magicui/ParticlesBackground.vue'
import BorderBeam from '../components/magicui/BorderBeam.vue'
import HeroGraphPreview from '../components/HeroGraphPreview.vue'
import { isAuthenticated, currentUser, logout } from '../store/auth'

const router = useRouter()

// Auth
const isLoggedIn = isAuthenticated
const userEmail = computed(() => currentUser.value?.email || '')
function handleLogout() {
  logout()
  router.push('/login')
}

// Form data
const formData = ref({
  simulationRequirement: ''
})

// File list
const files = ref([])

// URL list
const urls = ref([])
const urlInput = ref('')

// State
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)
const enrichWithMarketData = ref(false)

// File input ref
const fileInput = ref(null)

const canSubmit = computed(() => {
  const hasPrompt = formData.value.simulationRequirement.trim() !== ''
  const hasSources = files.value.length > 0 || urls.value.length > 0
  return hasPrompt && hasSources
})

const addUrl = () => {
  const raw = urlInput.value.trim()
  if (!raw) return
  try {
    const u = new URL(raw.startsWith('http') ? raw : `https://${raw}`)
    if (!urls.value.includes(u.href)) {
      urls.value.push(u.href)
    }
    urlInput.value = ''
  } catch {
    // invalid URL, ignore
  }
}

const removeUrl = (index) => {
  urls.value.splice(index, 1)
}

const isYouTubeUrl = (url) => {
  return /youtube\.com\/watch|youtu\.be\/|youtube\.com\/shorts|youtube\.com\/live/.test(url)
}

// Trigger file selection dialog
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// Handle file selection
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// Handle drag events
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return

  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// Add validated files to the list
const ALLOWED_EXTENSIONS = [
  'pdf', 'md', 'txt',
  'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp',
  'mp4', 'mov', 'avi', 'webm', 'mkv'
]

const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ALLOWED_EXTENSIONS.includes(ext)
  })
  files.value.push(...validFiles)
}

const getFileIcon = (name) => {
  const ext = name.split('.').pop().toLowerCase()
  if (['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(ext)) return '🖼️'
  if (['mp4', 'mov', 'avi', 'webm', 'mkv'].includes(ext)) return '🎬'
  if (ext === 'pdf') return '📕'
  return '📄'
}

const getFileTypeBadge = (name) => {
  const ext = name.split('.').pop().toLowerCase()
  if (['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(ext)) return 'IMG'
  if (['mp4', 'mov', 'avi', 'webm', 'mkv'].includes(ext)) return 'VID'
  if (ext === 'pdf') return 'PDF'
  if (ext === 'md') return 'MD'
  return 'TXT'
}

const removeFile = (index) => {
  files.value.splice(index, 1)
}

const promptTemplates = [
  { label: 'Investment', prompt: 'Analyze the uploaded company report and simulate how the stock market, institutional investors, and retail traders would react to the disclosed financial results over the next quarter.' },
  { label: 'Marketing', prompt: 'Simulate public reaction to the product launch described in the uploaded press release. How would different demographics respond on social media over 7 days?' },
  { label: 'Hiring', prompt: 'Based on the uploaded candidate profile and team structure, simulate how this hire would affect team dynamics, communication patterns, and productivity over 6 months.' },
  { label: 'Political', prompt: 'Model public opinion shifts if the policy change described in the uploaded document were announced. How would different political groups and media outlets react?' },
  { label: 'Risk', prompt: 'Conduct due diligence on the entity described in the uploaded materials. Surface potential risks, conflicts of interest, and second-order effects that manual review might miss.' },
  { label: 'Product', prompt: 'Simulate market response to the pricing change / feature announcement described in the uploaded document. How would competitors, customers, and analysts react?' },
]

const applyTemplate = (template) => {
  formData.value.simulationRequirement = template.prompt
}

// Scroll to bottom of page
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// Start simulation - navigate immediately, API calls happen on the Process page
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement, urls.value, enrichWithMarketData.value)

    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* Global variables and reset */
:root {
  --black: #000000;
  --white: #FAFAFA;
  --orange: #FF4500;
  --gray-light: #111111;
  --gray-text: #999999;
  --border: rgba(255, 255, 255, 0.1);
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans Hebrew', system-ui, sans-serif;
  --font-cn: 'Noto Sans Hebrew', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: #000000;
  font-family: var(--font-sans);
  color: #E0E0E0;
}

/* Particles background */
.particles-bg {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
}

/* Top navigation */
.navbar {
  height: 60px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
  color: #FFFFFF;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 20px;
}

.nav-user {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #888;
}

.nav-logout {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
  background: none;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 4px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-logout:hover {
  color: #fff;
  border-color: #555;
}

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}

.github-link:hover {
  opacity: 0.8;
}

.arrow {
  font-family: sans-serif;
}

/* Main content area */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Hero section */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 80px;
  position: relative;
}

.hero-left {
  flex: 1;
  padding-right: 60px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: #FFFFFF;
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}

.version-text {
  color: #666666;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.main-title {
  font-size: 4.5rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: #FFFFFF;
}

.gradient-text {
  background: linear-gradient(90deg, #FFFFFF 0%, #999999 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.highlight-bold {
  color: #FFFFFF;
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.highlight-code {
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: #FFFFFF;
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: #E0E0E0;
  letter-spacing: 1px;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: var(--orange);
}

.hero-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: stretch;
}

.logo-container {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  padding-right: 40px;
}

.hero-logo {
  max-width: 500px;
  width: 100%;
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--orange);
  font-size: 1.2rem;
  transition: all 0.2s;
}

.scroll-down-btn:hover {
  border-color: var(--orange);
}

/* Dashboard two-column layout */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* Left panel */
.left-panel {
  flex: 0.8;
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #666666;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
  color: #FFFFFF;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
}

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.metric-card {
  border: 1px solid var(--border);
  padding: 20px 30px;
  min-width: 150px;
  background: rgba(255, 255, 255, 0.03);
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
  color: #FFFFFF;
}

.metric-label {
  font-size: 0.85rem;
  color: #666666;
}

/* Workflow steps */
.steps-container {
  border: 1px solid var(--border);
  padding: 30px;
  position: relative;
  background: rgba(255, 255, 255, 0.03);
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #666666;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: #FFFFFF;
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
  color: #E0E0E0;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
}

/* Right interactive console */
.right-panel {
  flex: 1.2;
}

.console-box {
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 8px;
  background: rgba(255, 255, 255, 0.03);
  position: relative;
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666666;
}

.upload-zone {
  border: 1px dashed rgba(255, 255, 255, 0.15);
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: rgba(255, 255, 255, 0.02);
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.3);
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #666666;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
  color: #E0E0E0;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666666;
}

.upload-accepts {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #888888;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  letter-spacing: 0.02em;
}

.url-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  padding: 4px;
  background: rgba(255, 255, 255, 0.02);
}

.url-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin-left: 8px;
  color: #888;
}

.url-field {
  flex: 1;
  border: none;
  background: transparent;
  color: #E0E0E0;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  outline: none;
  padding: 8px 4px;
}

.url-field::placeholder {
  color: #555;
}

.url-add-btn {
  width: 32px;
  height: 32px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
  color: #CCC;
  font-size: 1.1rem;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.url-add-btn:hover:not(:disabled) {
  border-color: var(--orange);
  color: var(--orange);
}

.url-add-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.url-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.file-type-badge {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  padding: 2px 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #AAA;
  letter-spacing: 0.5px;
}

.template-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.template-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.03);
  color: #CCC;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.template-chip:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.06);
  color: #FFF;
}

.template-chip.active {
  border-color: var(--orange);
  color: var(--orange);
  background: rgba(255, 69, 0, 0.08);
}

.template-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.chip-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.chip-label {
  font-weight: 500;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.05);
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: #E0E0E0;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #666666;
}

.remove-btn:hover {
  color: var(--orange);
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #555555;
  letter-spacing: 1px;
}

.input-wrapper {
  position: relative;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
  color: #E0E0E0;
}

.code-input::placeholder {
  color: #555555;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #555555;
}

.start-engine-btn {
  width: 100%;
  background: #FFFFFF;
  color: #000000;
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  position: relative;
  overflow: hidden;
}

/* Enabled state (not disabled) */
.start-engine-btn:not(:disabled) {
  background: #FFFFFF;
  border: 1px solid #FFFFFF;
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
  color: #FFFFFF;
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: rgba(255, 255, 255, 0.08);
  color: #555555;
  cursor: not-allowed;
  transform: none;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Subtle border pulse animation */
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(255, 255, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }
}

/* Fade-in animation with staggered delays */
.animate-fade-in {
  opacity: 0;
  animation: fadeIn 0.8s ease forwards;
  animation-delay: var(--animation-delay, 0ms);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Shimmer animation for orange tag */
.animate-shimmer {
  background-size: 200% 100%;
  background-image: linear-gradient(
    90deg,
    var(--orange) 0%,
    #FF6B35 25%,
    var(--orange) 50%,
    #FF6B35 75%,
    var(--orange) 100%
  );
  animation: shimmer 3s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Market data toggle */
.market-data-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  transition: color 0.2s;
}

.market-data-toggle:hover {
  color: #CCC;
}

.market-data-toggle input[type="checkbox"] {
  appearance: none;
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  position: relative;
  flex-shrink: 0;
  transition: all 0.2s;
}

.market-data-toggle input[type="checkbox"]:checked {
  border-color: var(--orange);
  background: rgba(255, 69, 0, 0.15);
}

.market-data-toggle input[type="checkbox"]:checked::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 5px;
  width: 4px;
  height: 8px;
  border: solid var(--orange);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.market-data-toggle input[type="checkbox"]:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toggle-text {
  user-select: none;
}

/* Responsive layout */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }

  .hero-section {
    flex-direction: column;
  }

  .hero-left {
    padding-right: 0;
    margin-bottom: 40px;
  }

  .hero-logo {
    max-width: 200px;
    margin-bottom: 20px;
  }
}
</style>
