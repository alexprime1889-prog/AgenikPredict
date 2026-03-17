<template>
  <div class="home-page">
    <!-- 3D Graph Background -->
    <div ref="graphMount" class="graph-bg"></div>

    <!-- Navbar -->
    <nav class="home-nav">
      <img class="nav-brand-logo" src="../assets/logo/icon_white.png" alt="AgenikPredict" />
      <div class="nav-actions">
        <LanguageSwitcher />
        <span v-if="userEmail" class="nav-user">{{ userEmail }}</span>
        <button v-if="isLoggedIn" class="nav-logout" @click="handleLogout">{{ $t('auth.logout') }}</button>
      </div>
    </nav>

    <!-- Floating Upload Card -->
    <div class="card-wrap">
      <div class="upload-card">
        <BorderBeam :size="200" :duration="12" :delay="3" colorFrom="#ffaa40" colorTo="#9c40ff" />

        <p class="welcome" v-if="currentUser?.name">{{ $t('home.welcome', { name: currentUser.name }) }}</p>
        <p class="welcome" v-else-if="userEmail">{{ $t('home.welcome', { name: userEmail.split('@')[0] }) }}</p>

        <!-- Upload Zone -->
        <div
          class="drop-zone"
          :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
          @dragover.prevent="handleDragOver"
          @dragleave.prevent="handleDragLeave"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <input ref="fileInput" type="file" multiple accept=".pdf,.md,.txt,.jpg,.jpeg,.png,.webp,.gif,.bmp,.mp4,.mov,.avi,.webm,.mkv" style="display:none" :disabled="loading" @change="handleFileSelect" />
          <input ref="cameraInput" type="file" accept="image/*" capture="environment" style="display:none" :disabled="loading" @change="handleFileSelect" />

          <div v-if="files.length === 0" class="drop-placeholder">
            <svg class="drop-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span class="drop-text">{{ $t('home.dropFiles') }}</span>
          </div>

          <div v-else class="file-list">
            <div v-for="(file, index) in files" :key="`${file.name}-${index}`" class="file-chip">
              <span class="file-badge">{{ getFileTypeBadge(file.name) }}</span>
              <span class="file-name">{{ file.name }}</span>
              <button class="file-remove" @click.stop="removeFile(index)">×</button>
            </div>
          </div>
        </div>

        <p class="formats">{{ $t('home.formats') }}</p>

        <!-- Action buttons -->
        <div class="action-row">
          <button class="action-btn" @click="triggerCamera" :disabled="loading">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="btn-icon"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            {{ $t('home.takePhoto') }}
          </button>
          <button class="action-btn" @click="triggerFileInput" :disabled="loading">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="btn-icon"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            {{ $t('home.browseFiles') }}
          </button>
        </div>

        <!-- URL Input -->
        <div class="url-row">
          <svg class="url-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
          <input v-model="urlInput" type="url" class="url-input" placeholder="Paste URL or YouTube link" :disabled="loading" @keydown.enter.prevent="addUrl" />
          <button class="url-add" @click="addUrl" :disabled="!urlInput.trim() || loading">+</button>
        </div>

        <div v-if="urls.length > 0" class="url-chips">
          <div v-for="(url, index) in urls" :key="url" class="file-chip">
            <span class="file-badge">{{ isYouTubeUrl(url) ? 'YT' : 'URL' }}</span>
            <span class="file-name">{{ url }}</span>
            <button class="file-remove" @click.stop="removeUrl(index)">×</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Prompt Bar -->
    <div class="prompt-bar">
      <div class="prompt-inner">
        <div class="chips-row">
          <button v-for="tmpl in promptTemplates" :key="tmpl.label" class="chip" :class="{ active: formData.simulationRequirement === tmpl.prompt }" @click="applyTemplate(tmpl)" :disabled="loading">
            {{ tmpl.label }}
          </button>
        </div>
        <div class="prompt-input-row">
          <textarea v-model="formData.simulationRequirement" class="prompt-textarea" :placeholder="$t('home.promptPlaceholder')" rows="1" :disabled="loading" @input="autoResize" ref="promptRef"></textarea>
          <button class="start-btn" :disabled="!canSubmit || loading" @click="startSimulation">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="start-icon"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- History (compact) -->
    <div class="history-section" v-if="isLoggedIn">
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import BorderBeam from '../components/magicui/BorderBeam.vue'
import ForceGraph3D from '3d-force-graph'
import SpriteText from 'three-spritetext'
import * as THREE from 'three'
import { isAuthenticated, currentUser, logout } from '../store/auth'

const { locale } = useI18n()
const router = useRouter()
const promptRef = ref(null)

const isLoggedIn = isAuthenticated
const userEmail = computed(() => currentUser.value?.email || '')
function handleLogout() {
  logout()
  router.push('/login')
}

const formData = ref({ simulationRequirement: '' })
const files = ref([])
const urls = ref([])
const urlInput = ref('')
const loading = ref(false)
const isDragOver = ref(false)
const fileInput = ref(null)
const cameraInput = ref(null)
const graphMount = ref(null)
let graphInstance = null

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
    if (!urls.value.includes(u.href)) urls.value.push(u.href)
    urlInput.value = ''
  } catch {}
}

const removeUrl = (index) => { urls.value.splice(index, 1) }

const isYouTubeUrl = (url) => /youtube\.com\/watch|youtu\.be\/|youtube\.com\/shorts|youtube\.com\/live/.test(url)

const triggerFileInput = () => { if (!loading.value) fileInput.value?.click() }
const triggerCamera = () => { if (!loading.value) cameraInput.value?.click() }

const handleFileSelect = (event) => { addFiles(Array.from(event.target.files || [])) }
const handleDragOver = () => { if (!loading.value) isDragOver.value = true }
const handleDragLeave = () => { isDragOver.value = false }
const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  addFiles(Array.from(e.dataTransfer?.files || []))
}

const ALLOWED_EXTENSIONS = ['pdf','md','txt','jpg','jpeg','png','webp','gif','bmp','mp4','mov','avi','webm','mkv']
const addFiles = (newFiles) => {
  files.value.push(...newFiles.filter(f => ALLOWED_EXTENSIONS.includes(f.name.split('.').pop().toLowerCase())))
}

const getFileTypeBadge = (name) => {
  const ext = name.split('.').pop().toLowerCase()
  if (['jpg','jpeg','png','webp','gif','bmp'].includes(ext)) return 'IMG'
  if (['mp4','mov','avi','webm','mkv'].includes(ext)) return 'VID'
  if (ext === 'pdf') return 'PDF'
  return 'TXT'
}

const removeFile = (index) => { files.value.splice(index, 1) }

const promptTemplates = [
  { label: 'Investment', prompt: 'Analyze the uploaded company report and simulate how the stock market, institutional investors, and retail traders would react to the disclosed financial results over the next quarter.' },
  { label: 'Marketing', prompt: 'Simulate public reaction to the product launch described in the uploaded press release. How would different demographics respond on social media over 7 days?' },
  { label: 'Hiring', prompt: 'Based on the uploaded candidate profile and team structure, simulate how this hire would affect team dynamics, communication patterns, and productivity over 6 months.' },
  { label: 'Political', prompt: 'Model public opinion shifts if the policy change described in the uploaded document were announced. How would different political groups and media outlets react?' },
  { label: 'Risk', prompt: 'Conduct due diligence on the entity described in the uploaded materials. Surface potential risks, conflicts of interest, and second-order effects that manual review might miss.' },
  { label: 'Product', prompt: 'Simulate market response to the pricing change / feature announcement described in the uploaded document. How would competitors, customers, and analysts react?' },
]

const applyTemplate = (t) => { formData.value.simulationRequirement = t.prompt }

const autoResize = () => {
  if (promptRef.value) {
    promptRef.value.style.height = 'auto'
    promptRef.value.style.height = Math.min(promptRef.value.scrollHeight, 120) + 'px'
  }
}

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement, urls.value)
    router.push({ name: 'Process', params: { projectId: 'new' } })
  })
}

const COLORS = {
  Person: '#FF6B35', Investor: '#004E89', Company: '#7B2D8E',
  Founder: '#1A936F', FinancialInstitution: '#C5283D',
  GovernmentAgency: '#E9724C', Entity: '#3498db'
}

onMounted(async () => {
  if (!graphMount.value) return
  let graphData, translations = {}
  try {
    let gRes = await fetch('/production-graph.json')
    if (!gRes.ok) gRes = await fetch('/demo-graph.json')
    graphData = await gRes.json()
    try {
      const tRes = await fetch('/graph-translations.json')
      if (tRes.ok) { const allT = await tRes.json(); translations = allT[locale.value] || allT.en || {} }
    } catch {}
  } catch (e) { console.error('Graph data load failed:', e); return }

  const data = graphData.data || graphData
  const nodes = [], links = [], nodeMap = new Map()
  for (const n of (data.nodes || [])) {
    const type = n.labels?.find(l => l !== 'Entity') || 'Entity'
    const orig = n.name || 'Unnamed'
    const node = { id: n.uuid, name: translations[orig] || orig, type, val: 1 }
    nodeMap.set(n.uuid, node)
    nodes.push(node)
  }
  const nodeIds = new Set(nodes.map(n => n.id))
  for (const e of (data.edges || [])) {
    if (nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid)) {
      links.push({ source: e.source_node_uuid, target: e.target_node_uuid })
      const s = nodeMap.get(e.source_node_uuid); if (s) s.val += 0.5
      const t = nodeMap.get(e.target_node_uuid); if (t) t.val += 0.5
    }
  }

  const el = graphMount.value
  graphInstance = ForceGraph3D()(el)
    .width(el.clientWidth).height(el.clientHeight)
    .graphData({ nodes, links })
    .backgroundColor('rgba(0,0,0,0)')
    .showNavInfo(false)
    .nodeThreeObject(node => {
      const color = COLORS[node.type] || '#999'
      const r = Math.max(2.5, Math.sqrt(node.val) * 2)
      const g = new THREE.Group()
      g.add(new THREE.Mesh(new THREE.SphereGeometry(r, 16, 16), new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0.85 })))
      g.add(new THREE.Mesh(new THREE.SphereGeometry(r * 1.4, 12, 12), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.1 })))
      const lbl = new SpriteText(node.name.length > 12 ? node.name.slice(0, 10) + '…' : node.name)
      lbl.color = '#ccc'; lbl.textHeight = 2.5; lbl.position.set(0, -(r + 4), 0); lbl.backgroundColor = false
      g.add(lbl)
      return g
    })
    .nodeLabel(() => '')
    .linkColor(() => 'rgba(255,255,255,0.15)')
    .linkWidth(0.5).linkOpacity(0.5)
    .enableNodeDrag(false)
    .d3AlphaDecay(0.03).d3VelocityDecay(0.25)
    .warmupTicks(100).cooldownTicks(0)

  graphInstance.controls().autoRotate = true
  graphInstance.controls().autoRotateSpeed = 0.8
  graphInstance.controls().enableZoom = true
  graphInstance.controls().enablePan = false

  setTimeout(() => { if (graphInstance) graphInstance.cameraPosition({ x: 0, y: 0, z: 300 }) }, 500)

  const onResize = () => { if (graphInstance && el) graphInstance.width(el.clientWidth).height(el.clientHeight) }
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  if (graphInstance) { graphInstance._destructor?.(); graphInstance = null }
})
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  background: #0a0a0a;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  color: #e0e0e0;
  position: relative;
  overflow: hidden;
}

.graph-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  opacity: 0.6;
}

.home-nav {
  position: relative;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
}

.nav-brand-logo {
  height: 22px;
  width: auto;
  opacity: 0.9;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-user {
  font-size: 12px;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
}

.nav-logout {
  font-size: 12px;
  color: #666;
  background: none;
  border: 1px solid #333;
  padding: 4px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-logout:hover {
  color: #fff;
  border-color: #555;
}

.card-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 200px);
  padding: 20px;
}

.upload-card {
  width: 100%;
  max-width: 480px;
  padding: 32px 28px;
  background: rgba(17, 17, 17, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.welcome {
  font-size: 16px;
  font-weight: 500;
  color: #fff;
  margin: 0;
}

.drop-zone {
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  min-height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.02);
}

.drop-zone:hover, .drop-zone.drag-over {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.04);
}

.drop-zone.has-files {
  align-items: flex-start;
  padding: 12px;
}

.drop-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #888;
}

.drop-icon {
  width: 28px;
  height: 28px;
  opacity: 0.5;
}

.drop-text {
  font-size: 13px;
}

.formats {
  font-size: 11px;
  color: #555;
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
  margin: -8px 0 0;
}

.action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: #ccc;
  font-size: 12px;
  font-family: 'Space Grotesk', sans-serif;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.url-row {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 4px 4px 4px 12px;
  background: rgba(255, 255, 255, 0.02);
}

.url-icon {
  width: 14px;
  height: 14px;
  color: #666;
  flex-shrink: 0;
}

.url-input {
  flex: 1;
  border: none;
  background: transparent;
  color: #e0e0e0;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  outline: none;
  padding: 8px 0;
}

.url-input::placeholder { color: #444; }

.url-add {
  width: 28px;
  height: 28px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  background: transparent;
  color: #999;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.url-add:hover:not(:disabled) { border-color: #ff4500; color: #ff4500; }
.url-add:disabled { opacity: 0.3; cursor: not-allowed; }

.url-chips, .file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  font-size: 12px;
}

.file-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  padding: 2px 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  color: #aaa;
  letter-spacing: 0.5px;
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #ccc;
}

.file-remove {
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  font-size: 14px;
}

/* Bottom Prompt Bar */
.prompt-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 10;
  background: rgba(10, 10, 10, 0.92);
  backdrop-filter: blur(16px);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding: 12px 20px 16px;
}

.prompt-inner {
  max-width: 680px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chips-row {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.chip {
  white-space: nowrap;
  padding: 5px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 100px;
  background: transparent;
  color: #888;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  transition: all 0.2s;
}

.chip:hover:not(:disabled) { border-color: rgba(255, 255, 255, 0.25); color: #fff; }
.chip.active { border-color: #ff4500; color: #ff4500; }

.prompt-input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 4px 4px 4px 16px;
  background: rgba(255, 255, 255, 0.03);
}

.prompt-textarea {
  flex: 1;
  border: none;
  background: transparent;
  color: #e0e0e0;
  font-size: 14px;
  font-family: 'Space Grotesk', sans-serif;
  outline: none;
  resize: none;
  padding: 10px 0;
  max-height: 120px;
  line-height: 1.5;
}

.prompt-textarea::placeholder { color: #555; }

.start-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 10px;
  background: #ff4500;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}

.start-btn:hover:not(:disabled) { filter: brightness(1.15); transform: scale(1.05); }
.start-btn:disabled { background: #333; color: #666; cursor: not-allowed; transform: none; }

.start-icon {
  width: 20px;
  height: 20px;
}

.history-section {
  position: relative;
  z-index: 5;
  padding-bottom: 100px;
}

@media (max-width: 640px) {
  .upload-card { max-width: 100%; padding: 24px 20px; }
  .card-wrap { min-height: calc(100vh - 160px); }
  .prompt-bar { padding: 10px 12px 14px; }
}
</style>
