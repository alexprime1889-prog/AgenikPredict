<template>
  <div class="graph-panel">
    <div class="panel-header">
      <span class="panel-title">{{ $t('graph.title') }}</span>
      <!-- Top toolbar (Internal Top Right) -->
      <div class="header-tools">
        <button class="tool-btn" @click="$emit('refresh')" :disabled="loading" :title="$t('graph.refresh')">
          <span class="icon-refresh" :class="{ 'spinning': loading }">↻</span>
          <span class="btn-text">{{ $t('graph.refresh') }}</span>
        </button>
        <button class="tool-btn" @click="$emit('toggle-maximize')" :title="$t('graph.fullscreen')">
          <span class="icon-maximize">⛶</span>
        </button>
      </div>
    </div>

    <div class="graph-container" ref="graphContainer">
      <!-- 3D Graph mounts here -->
      <div v-if="graphData" ref="graphMount" class="graph-mount"></div>

      <!-- Building/simulating hint -->
      <div v-if="currentPhase === 1 || isSimulating" class="graph-building-hint">
        <div class="memory-icon-wrapper">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
          </svg>
        </div>
        {{ isSimulating ? $t('graph.memoryUpdating') : $t('graph.liveUpdating') }}
      </div>

      <!-- Simulation finished hint -->
      <div v-if="showSimulationFinishedHint" class="graph-building-hint finished-hint">
        <div class="hint-icon-wrapper">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="hint-icon">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
          </svg>
        </div>
        <span class="hint-text">{{ $t('graph.processingHint') }}</span>
        <button class="hint-close-btn" @click="dismissFinishedHint" :title="$t('graph.closeHint')">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <!-- Node/edge detail panel -->
      <div v-if="selectedItem" class="detail-panel">
        <div class="detail-panel-header">
          <span class="detail-title">{{ selectedItem.type === 'node' ? $t('graph.detailNode') : $t('graph.detailRelationship') }}</span>
          <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
            {{ selectedItem.entityType }}
          </span>
          <button class="detail-close" @click="closeDetailPanel">×</button>
        </div>

        <!-- Node details -->
        <div v-if="selectedItem.type === 'node'" class="detail-content">
          <div class="detail-row">
            <span class="detail-label">{{ $t('graph.fieldName') }}:</span>
            <span class="detail-value">{{ selectedItem.data.name }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">{{ $t('graph.fieldUuid') }}:</span>
            <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
          </div>
          <div class="detail-row" v-if="selectedItem.data.created_at">
            <span class="detail-label">{{ $t('graph.fieldCreated') }}:</span>
            <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
          </div>

          <!-- Properties -->
          <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
            <div class="section-title">{{ $t('graph.properties') }}:</div>
            <div class="properties-list">
              <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                <span class="property-key">{{ key }}:</span>
                <span class="property-value">{{ value || $t('graph.noneValue') }}</span>
              </div>
            </div>
          </div>

          <!-- Summary -->
          <div class="detail-section" v-if="selectedItem.data.summary">
            <div class="section-title">{{ $t('graph.summary') }}:</div>
            <div class="summary-text">{{ selectedItem.data.summary }}</div>
          </div>

          <!-- Labels -->
          <div class="detail-section" v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0">
            <div class="section-title">{{ $t('graph.labels') }}:</div>
            <div class="labels-list">
              <span v-for="label in selectedItem.data.labels" :key="label" class="label-tag">
                {{ label }}
              </span>
            </div>
          </div>
        </div>

        <!-- Edge details -->
        <div v-else class="detail-content">
          <!-- Self-loop group details -->
          <template v-if="selectedItem.data.isSelfLoopGroup">
            <div class="edge-relation-header self-loop-header">
              {{ selectedItem.data.source_name }} - {{ $t('graph.selfRelations') }}
              <span class="self-loop-count">{{ $t('graph.itemsCount', { count: selectedItem.data.selfLoopCount }) }}</span>
            </div>

            <div class="self-loop-list">
              <div
                v-for="(loop, idx) in selectedItem.data.selfLoopEdges"
                :key="loop.uuid || idx"
                class="self-loop-item"
                :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
              >
                <div
                  class="self-loop-item-header"
                  @click="toggleSelfLoop(loop.uuid || idx)"
                >
                  <span class="self-loop-index">#{{ idx + 1 }}</span>
                  <span class="self-loop-name">{{ loop.name || loop.fact_type || $t('graph.related') }}</span>
                  <span class="self-loop-toggle">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                </div>

                <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                  <div class="detail-row" v-if="loop.uuid">
                    <span class="detail-label">{{ $t('graph.fieldUuid') }}:</span>
                    <span class="detail-value uuid-text">{{ loop.uuid }}</span>
                  </div>
                  <div class="detail-row" v-if="loop.fact">
                    <span class="detail-label">{{ $t('graph.fieldFact') }}:</span>
                    <span class="detail-value fact-text">{{ loop.fact }}</span>
                  </div>
                  <div class="detail-row" v-if="loop.fact_type">
                    <span class="detail-label">{{ $t('graph.fieldType') }}:</span>
                    <span class="detail-value">{{ loop.fact_type }}</span>
                  </div>
                  <div class="detail-row" v-if="loop.created_at">
                    <span class="detail-label">{{ $t('graph.fieldCreated') }}:</span>
                    <span class="detail-value">{{ formatDateTime(loop.created_at) }}</span>
                  </div>
                  <div v-if="loop.episodes && loop.episodes.length > 0" class="self-loop-episodes">
                    <span class="detail-label">{{ $t('graph.episodes') }}:</span>
                    <div class="episodes-list compact">
                      <span v-for="ep in loop.episodes" :key="ep" class="episode-tag small">{{ ep }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- Normal edge details -->
          <template v-else>
            <div class="edge-relation-header">
              {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || $t('graph.relatedTo') }} → {{ selectedItem.data.target_name }}
            </div>

            <div class="detail-row">
              <span class="detail-label">{{ $t('graph.fieldUuid') }}:</span>
              <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">{{ $t('graph.fieldLabel') }}:</span>
              <span class="detail-value">{{ selectedItem.data.name || $t('graph.relatedTo') }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">{{ $t('graph.fieldType') }}:</span>
              <span class="detail-value">{{ selectedItem.data.fact_type || $t('graph.unknown') }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.fact">
              <span class="detail-label">{{ $t('graph.fieldFact') }}:</span>
              <span class="detail-value fact-text">{{ selectedItem.data.fact }}</span>
            </div>

            <!-- Episodes -->
            <div class="detail-section" v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0">
              <div class="section-title">{{ $t('graph.episodes') }}:</div>
              <div class="episodes-list">
                <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">
                  {{ ep }}
                </span>
              </div>
            </div>

            <div class="detail-row" v-if="selectedItem.data.created_at">
              <span class="detail-label">{{ $t('graph.fieldCreated') }}:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.valid_at">
              <span class="detail-label">{{ $t('graph.fieldValidFrom') }}:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.valid_at) }}</span>
            </div>
          </template>
        </div>

        <!-- Report Configuration Section -->
        <div class="report-config-section">
          <div class="config-section-header" @click="showReportConfig = !showReportConfig">
            <span class="config-title">{{ $t('graph.reportSettings') }}</span>
            <span class="config-toggle">{{ showReportConfig ? '\u2212' : '+' }}</span>
          </div>

          <div v-show="showReportConfig" class="config-content">
            <div class="config-group">
              <label class="config-label">{{ $t('graph.analysisMode') }}</label>
              <select v-model="reportConfig.analysis_mode" @change="emitReportConfig" class="config-select">
                <option value="global">{{ $t('graph.analysisModeGlobal') }}</option>
                <option value="quick">{{ $t('graph.analysisModeQuick') }}</option>
              </select>
            </div>

            <!-- Language selector -->
            <div class="config-group">
              <label class="config-label">{{ $t('graph.reportLanguage') }}</label>
              <select v-model="reportConfig.language" @change="handleReportLanguageChange" class="config-select">
                <option v-for="lang in languageOptions" :key="lang.code" :value="lang.code">
                  {{ lang.name }}
                </option>
              </select>
            </div>

            <!-- Persona editor -->
            <div class="config-group">
              <label class="config-label">{{ $t('graph.agentPersona') }}</label>
              <textarea
                v-model="reportConfig.persona"
                @blur="emitReportConfig"
                class="config-textarea"
                rows="3"
                :placeholder="$t('graph.personaPlaceholder')"
              ></textarea>
            </div>

            <!-- Variables -->
            <div class="config-group">
              <div class="config-label-row">
                <label class="config-label">{{ $t('graph.variables') }}</label>
                <button class="config-add-btn" @click="addVariable">+ {{ $t('graph.addVariable') }}</button>
              </div>
              <div v-for="(v, idx) in reportConfig.variables" :key="idx" class="variable-row">
                <input v-model="v.key" @blur="emitReportConfig" class="var-input var-key" :placeholder="$t('graph.variableKey')" />
                <input v-model="v.value" @blur="emitReportConfig" class="var-input var-value" :placeholder="$t('graph.variableValue')" />
                <button class="var-remove-btn" @click="removeVariable(idx)">\u00D7</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="!graphData && loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>{{ $t('graph.loading') }}</p>
      </div>

      <!-- Waiting/empty state -->
      <div v-if="!graphData && !loading" class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">{{ $t('graph.waitingOntology') }}</p>
      </div>
    </div>

    <!-- Legend (Bottom Left) -->
    <div v-if="graphData && entityTypes.length" class="graph-legend">
      <span class="legend-title">{{ $t('graph.entityTypes') }}</span>
      <div class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ type.name }}</span>
        </div>
      </div>
    </div>

    <!-- Edge labels toggle -->
    <div v-if="graphData" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">{{ $t('graph.showEdgeLabels') }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ForceGraph3D from '3d-force-graph'
import SpriteText from 'three-spritetext'
import * as THREE from 'three'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean
})

const emit = defineEmits(['refresh', 'toggle-maximize', 'update-report-config'])
const { locale, t } = useI18n()

const graphContainer = ref(null)
const graphMount = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true)
const expandedSelfLoops = ref(new Set())
const showSimulationFinishedHint = ref(false)
const wasSimulating = ref(false)
const showReportConfig = ref(false)
const reportLanguageManuallySelected = ref(false)

const reportConfig = ref({
  persona: '',
  variables: [],
  analysis_mode: 'global',
  language: locale.value || localStorage.getItem('agenikpredict-locale') || 'en'
})

const languageOptions = [
  { code: 'en', name: 'English' },
  { code: 'he', name: 'עברית' },
  { code: 'ru', name: 'Русский' },
  { code: 'es', name: 'Español' },
  { code: 'de', name: 'Deutsch' },
  { code: 'fr', name: 'Français' },
  { code: 'it', name: 'Italiano' },
  { code: 'pt', name: 'Português' },
  { code: 'pl', name: 'Polski' },
  { code: 'nl', name: 'Nederlands' },
  { code: 'tr', name: 'Türkçe' },
  { code: 'ar', name: 'العربية' }
]

const addVariable = () => {
  reportConfig.value.variables.push({ key: '', value: '' })
}

const removeVariable = (index) => {
  reportConfig.value.variables.splice(index, 1)
  emitReportConfig()
}

const emitReportConfig = () => {
  const vars = {}
  reportConfig.value.variables.forEach(v => {
    if (v.key.trim()) vars[v.key.trim()] = v.value
  })
  emit('update-report-config', {
    persona: reportConfig.value.persona,
    variables: vars,
    analysis_mode: reportConfig.value.analysis_mode || 'global',
    language: reportConfig.value.language
  })
}

const handleReportLanguageChange = () => {
  reportLanguageManuallySelected.value = reportConfig.value.language !== locale.value
  emitReportConfig()
}

watch(locale, (newLocale, oldLocale) => {
  if (!newLocale) return
  if (!reportLanguageManuallySelected.value || reportConfig.value.language === oldLocale) {
    if (reportConfig.value.language !== newLocale) {
      reportConfig.value.language = newLocale
      emitReportConfig()
    }
    reportLanguageManuallySelected.value = false
  }
  nextTick(renderGraph)
})

let graphInstance = null
let highlightNodes = new Set()
let highlightLinks = new Set()
let hoveredNode = null

// --- Entity type → Tabler icon mapping ---
const ENTITY_ICON_MAP = {
  Person: 'user',
  Country: 'flag',
  Keyphrase: 'tag',
  Username: 'at',
  MilitaryEquipment: 'tank',
  Continent: 'world',
  GovernmentBody: 'building-bank',
  Incident: 'alert-triangle',
  Domain: 'world-www',
  Place: 'map-pin',
  Product: 'box',
  Province: 'map-pin-2',
  Entity: 'circle-dot',
}

// Color palette (same as before)
const COLORS = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']

// Cache for SVG textures
const textureCache = new Map()

// Load SVG from Tabler icons and create a Three.js texture
const createIconTexture = (iconName, color) => {
  const cacheKey = `${iconName}_${color}`
  if (textureCache.has(cacheKey)) return textureCache.get(cacheKey)

  // Build SVG with icon embedded
  const size = 128
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <defs>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="${color}" stop-opacity="0.3"/>
          <stop offset="70%" stop-color="${color}" stop-opacity="0.1"/>
          <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <circle cx="64" cy="64" r="62" fill="url(#glow)"/>
      <circle cx="64" cy="64" r="28" fill="${color}" opacity="0.9" stroke="rgba(255,255,255,0.6)" stroke-width="2"/>
    </svg>`

  const blob = new Blob([svg], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const texture = new THREE.TextureLoader().load(url, () => {
    URL.revokeObjectURL(url)
  })
  texture.colorSpace = THREE.SRGBColorSpace
  textureCache.set(cacheKey, texture)
  return texture
}

// Load actual Tabler SVG icon and create texture with it
const createDetailedIconTexture = async (iconName, color) => {
  const cacheKey = `detailed_${iconName}_${color}`
  if (textureCache.has(cacheKey)) return textureCache.get(cacheKey)

  try {
    const iconModule = await import(/* @vite-ignore */ `@tabler/icons/icons/outline/${iconName}.svg?raw`)
    const iconSvg = iconModule.default
    // Extract the inner paths from the Tabler SVG
    const pathMatch = iconSvg.match(/<svg[^>]*>([\s\S]*)<\/svg>/)
    const innerPaths = pathMatch ? pathMatch[1] : ''

    const size = 128
    const svg = `
      <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <defs>
          <radialGradient id="glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="${color}" stop-opacity="0.25"/>
            <stop offset="80%" stop-color="${color}" stop-opacity="0.05"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <circle cx="64" cy="64" r="62" fill="url(#glow)"/>
        <circle cx="64" cy="64" r="30" fill="${color}" opacity="0.15" stroke="${color}" stroke-width="1.5" stroke-opacity="0.6"/>
        <g transform="translate(52, 52) scale(1)" stroke="${color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
          ${innerPaths}
        </g>
      </svg>`

    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)

    return new Promise((resolve) => {
      const texture = new THREE.TextureLoader().load(url, () => {
        URL.revokeObjectURL(url)
        texture.colorSpace = THREE.SRGBColorSpace
        textureCache.set(cacheKey, texture)
        resolve(texture)
      })
    })
  } catch {
    // Fallback to simple circle
    return createIconTexture(iconName, color)
  }
}

// Dismiss simulation finished hint
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// Watch isSimulating changes to detect simulation end
watch(() => props.isSimulating, (newValue) => {
  if (wasSimulating.value && !newValue) {
    showSimulationFinishedHint.value = true
  }
  wasSimulating.value = newValue
}, { immediate: true })

// Toggle self-loop item expand/collapse state
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

// Compute entity types for legend
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}

  props.graphData.nodes.forEach(node => {
    const type = node.labels?.find(l => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: COLORS[Object.keys(typeMap).length % COLORS.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

// Format date/time
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString(locale.value || 'en', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  expandedSelfLoops.value = new Set()
  highlightNodes.clear()
  highlightLinks.clear()
  if (graphInstance) graphInstance.refresh()
}

const getColor = (type) => {
  const found = entityTypes.value.find(t => t.name === type)
  return found ? found.color : '#999'
}

const renderGraph = () => {
  if (!graphMount.value || !props.graphData) return

  // Destroy previous instance
  if (graphInstance) {
    graphInstance._destructor()
    graphInstance = null
  }

  // Clear container
  graphMount.value.innerHTML = ''

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []

  if (nodesData.length === 0) return

  // Prep data
  const nodeMap = {}
  nodesData.forEach(n => nodeMap[n.uuid] = n)

  const nodes = nodesData.map(n => ({
    id: n.uuid,
    name: n.name || t('graph.unknown'),
    type: n.labels?.find(l => l !== 'Entity') || 'Entity',
    rawData: n
  }))

  const nodeIds = new Set(nodes.map(n => n.id))

  // Process edges — same logic as before
  const edgePairCount = {}
  const selfLoopEdges = {}
  const tempEdges = edgesData
    .filter(e => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))

  tempEdges.forEach(e => {
    if (e.source_node_uuid === e.target_node_uuid) {
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })

  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set()
  const links = []

  tempEdges.forEach(e => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid

    if (isSelfLoop) {
      if (processedSelfLoopNodes.has(e.source_node_uuid)) return
      processedSelfLoopNodes.add(e.source_node_uuid)

      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || t('graph.unknown')

      links.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        name: t('graph.selfRelationsCount', { count: allSelfLoops.length }),
        curvature: 0.4,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops
        }
      })
      return
    }

    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1

    let curvature = 0
    if (totalCount > 1) {
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      if (e.source_node_uuid > e.target_node_uuid) {
        curvature = -curvature
      }
    }

    links.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      name: e.name || e.fact_type || t('graph.related'),
      curvature,
      isSelfLoop: false,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })

  // Build color map
  const colorMap = {}
  entityTypes.value.forEach(t => colorMap[t.name] = t.color)

  // Preload icon textures
  const iconTextureMap = {}
  const uniqueTypes = [...new Set(nodes.map(n => n.type))]
  uniqueTypes.forEach(type => {
    const iconName = ENTITY_ICON_MAP[type] || 'circle-dot'
    const color = colorMap[type] || '#999'
    iconTextureMap[type] = createIconTexture(iconName, color)
    // Also start loading detailed textures in background
    createDetailedIconTexture(iconName, color).then(tex => {
      iconTextureMap[type] = tex
      if (graphInstance) graphInstance.refresh()
    })
  })

  // Create 3D Force Graph
  graphInstance = ForceGraph3D()(graphMount.value)
    .width(width)
    .height(height)
    .graphData({ nodes, links })
    .backgroundColor('#000000')
    // Node rendering with icon sprites
    .nodeThreeObject(node => {
      const color = colorMap[node.type] || '#999'
      const texture = iconTextureMap[node.type]

      const group = new THREE.Group()

      // Icon sprite
      const spriteMaterial = new THREE.SpriteMaterial({
        map: texture || createIconTexture('circle-dot', color),
        transparent: true,
        opacity: highlightNodes.size > 0 ? (highlightNodes.has(node.id) ? 1 : 0.2) : 0.9,
        depthWrite: false,
      })
      const sprite = new THREE.Sprite(spriteMaterial)
      sprite.scale.set(16, 16, 1)
      group.add(sprite)

      // Text label below node
      const label = new SpriteText(
        node.name.length > 12 ? node.name.substring(0, 12) + '…' : node.name
      )
      label.color = highlightNodes.size > 0 ? (highlightNodes.has(node.id) ? '#fff' : 'rgba(255,255,255,0.15)') : '#E0E0E0'
      label.textHeight = 3
      label.position.set(0, -12, 0)
      label.fontFace = 'system-ui, sans-serif'
      label.fontWeight = '500'
      label.backgroundColor = false
      group.add(label)

      return group
    })
    .nodeLabel(() => '') // We render our own labels
    // Link styling
    .linkColor(link => {
      if (highlightLinks.has(link)) return '#E91E63'
      return 'rgba(255,255,255,0.2)'
    })
    .linkWidth(link => highlightLinks.has(link) ? 2 : 0.5)
    .linkOpacity(0.6)
    .linkCurvature(link => link.curvature || 0)
    .linkCurveRotation(link => link.isSelfLoop ? Math.PI * 0.5 : 0)
    .linkDirectionalParticles(link => highlightLinks.has(link) ? 4 : 0)
    .linkDirectionalParticleWidth(2)
    .linkDirectionalParticleColor(() => '#E91E63')
    // Link labels
    .linkThreeObjectExtend(true)
    .linkThreeObject(link => {
      if (!showEdgeLabels.value) return null
      const label = new SpriteText(link.name || '')
      label.color = 'rgba(255,255,255,0.5)'
      label.textHeight = 2
      label.fontFace = 'system-ui, sans-serif'
      label.backgroundColor = 'rgba(0,0,0,0.6)'
      label.padding = [1, 2]
      label.borderRadius = 2
      return label
    })
    .linkPositionUpdate((sprite, { start, end }) => {
      if (!sprite) return
      const mid = Object.assign(
        ...['x', 'y', 'z'].map(c => ({
          [c]: start[c] + (end[c] - start[c]) / 2
        }))
      )
      Object.assign(sprite.position, mid)
    })
    // Interactions
    .onNodeClick((node) => {
      highlightNodes.clear()
      highlightLinks.clear()

      // Highlight this node and connected links
      highlightNodes.add(node.id)
      links.forEach(link => {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target
        if (srcId === node.id || tgtId === node.id) {
          highlightLinks.add(link)
          highlightNodes.add(srcId)
          highlightNodes.add(tgtId)
        }
      })

      selectedItem.value = {
        type: 'node',
        data: node.rawData,
        entityType: node.type,
        color: getColor(node.type)
      }

      graphInstance.refresh()
    })
    .onNodeHover(node => {
      graphMount.value.style.cursor = node ? 'pointer' : 'default'
      hoveredNode = node
    })
    .onLinkClick(link => {
      highlightNodes.clear()
      highlightLinks.clear()
      highlightLinks.add(link)

      selectedItem.value = {
        type: 'edge',
        data: link.rawData
      }

      graphInstance.refresh()
    })
    .onBackgroundClick(() => {
      highlightNodes.clear()
      highlightLinks.clear()
      selectedItem.value = null
      graphInstance.refresh()
    })
    // Force engine config
    .d3AlphaDecay(0.02)
    .d3VelocityDecay(0.3)
    .warmupTicks(80)
    .cooldownTime(3000)

  // Configure forces
  graphInstance.d3Force('charge').strength(-120)
  graphInstance.d3Force('link').distance(60)

  // Set camera position
  setTimeout(() => {
    if (graphInstance) {
      graphInstance.cameraPosition({ z: 300 })
    }
  }, 500)
}

watch(() => props.graphData, () => {
  nextTick(renderGraph)
}, { deep: true })

// Watch edge labels toggle — re-render link objects
watch(showEdgeLabels, () => {
  if (graphInstance) {
    graphInstance.refresh()
  }
})

const handleResize = () => {
  if (graphInstance && graphContainer.value) {
    graphInstance.width(graphContainer.value.clientWidth)
    graphInstance.height(graphContainer.value.clientHeight)
  }
}

let resizeObserver = null

onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (graphContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      handleResize()
    })
    resizeObserver.observe(graphContainer.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (graphInstance) {
    graphInstance._destructor()
    graphInstance = null
  }
  textureCache.forEach((tex) => tex.dispose?.())
  textureCache.clear()
})
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #000000;
  overflow: hidden;
}

.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(0,0,0,0.8), rgba(0,0,0,0));
  pointer-events: none;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #FFFFFF;
  pointer-events: auto;
}

.header-tools {
  pointer-events: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: #999;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  font-size: 13px;
}

.tool-btn:hover {
  background: rgba(255,255,255,0.1);
  color: #FFF;
  border-color: rgba(255,255,255,0.25);
}

.tool-btn .btn-text {
  font-size: 12px;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-mount {
  width: 100%;
  height: 100%;
}

.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #888;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.2;
}

/* Entity Types Legend - Bottom Left */
.graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(17,17,17,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  z-index: 10;
}

.legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #E91E63;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  max-width: 320px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #AAA;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  white-space: nowrap;
}

/* Edge Labels Toggle - Top Right */
.edge-labels-toggle {
  position: absolute;
  top: 60px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(17,17,17,0.9);
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  z-index: 10;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255,255,255,0.15);
  border-radius: 22px;
  transition: 0.3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

input:checked + .slider {
  background-color: #7B2D8E;
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.toggle-label {
  font-size: 12px;
  color: #999;
}

/* Detail Panel - Right Side */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: #111111;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  overflow: hidden;
  font-family: 'Noto Sans Hebrew', system-ui, sans-serif;
  font-size: 13px;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.detail-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #1A1A1A;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  flex-shrink: 0;
}

.detail-title {
  font-weight: 600;
  color: #FFFFFF;
  font-size: 14px;
}

.detail-type-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  margin-left: auto;
  margin-right: 12px;
}

.detail-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #999;
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.detail-close:hover {
  color: #FFF;
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-row {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-label {
  color: #777;
  font-size: 12px;
  font-weight: 500;
  min-width: 80px;
}

.detail-value {
  color: #DDD;
  flex: 1;
  word-break: break-word;
}

.detail-value.uuid-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #888;
}

.detail-value.fact-text {
  line-height: 1.5;
  color: #CCC;
}

.detail-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #999;
  margin-bottom: 10px;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
}

.property-key {
  color: #777;
  font-weight: 500;
  min-width: 90px;
}

.property-value {
  color: #DDD;
  flex: 1;
}

.summary-text {
  line-height: 1.6;
  color: #CCC;
  font-size: 12px;
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.label-tag {
  display: inline-block;
  padding: 4px 12px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 16px;
  font-size: 11px;
  color: #AAA;
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.episode-tag {
  display: inline-block;
  padding: 6px 10px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #999;
  word-break: break-all;
}

/* Edge relation header */
.edge-relation-header {
  background: rgba(255,255,255,0.05);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 500;
  color: #DDD;
  line-height: 1.5;
  word-break: break-word;
}

/* Building hint */
.graph-building-hint {
  position: absolute;
  bottom: 160px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  color: #fff;
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-weight: 500;
  letter-spacing: 0.5px;
  z-index: 100;
}

.memory-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
}

.memory-icon {
  width: 18px;
  height: 18px;
  color: #4CAF50;
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); filter: drop-shadow(0 0 2px rgba(76, 175, 80, 0.3)); }
  50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 8px rgba(76, 175, 80, 0.6)); }
}

/* Simulation finished hint styles */
.graph-building-hint.finished-hint {
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.finished-hint .hint-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.finished-hint .hint-icon {
  width: 18px;
  height: 18px;
  color: #FFF;
}

.finished-hint .hint-text {
  flex: 1;
  white-space: nowrap;
}

.hint-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  color: #FFF;
  transition: all 0.2s;
  margin-left: 8px;
  flex-shrink: 0;
}

.hint-close-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  transform: scale(1.1);
}

/* Loading spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255,255,255,0.15);
  border-top-color: #7B2D8E;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

/* Self-loop styles */
.self-loop-header {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(76,175,80,0.15) 0%, rgba(139,195,74,0.1) 100%);
  border: 1px solid rgba(76,175,80,0.3);
}

.self-loop-count {
  margin-left: auto;
  font-size: 11px;
  color: #666;
  background: rgba(255,255,255,0.1);
  padding: 2px 8px;
  border-radius: 10px;
}

.self-loop-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-loop-item {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
}

.self-loop-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.05);
  cursor: pointer;
  transition: background 0.2s;
}

.self-loop-item-header:hover {
  background: rgba(255,255,255,0.08);
}

.self-loop-item.expanded .self-loop-item-header {
  background: rgba(255,255,255,0.1);
}

.self-loop-index {
  font-size: 10px;
  font-weight: 600;
  color: #888;
  background: rgba(255,255,255,0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

.self-loop-name {
  font-size: 12px;
  font-weight: 500;
  color: #DDD;
  flex: 1;
}

.self-loop-toggle {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #888;
  background: rgba(255,255,255,0.1);
  border-radius: 4px;
  transition: all 0.2s;
}

.self-loop-item.expanded .self-loop-toggle {
  background: rgba(255,255,255,0.15);
  color: #AAA;
}

.self-loop-item-content {
  padding: 12px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.self-loop-item-content .detail-row {
  margin-bottom: 8px;
}

.self-loop-item-content .detail-label {
  font-size: 11px;
  min-width: 60px;
}

.self-loop-item-content .detail-value {
  font-size: 12px;
}

.self-loop-episodes {
  margin-top: 8px;
}

.episodes-list.compact {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
}

.episode-tag.small {
  padding: 3px 6px;
  font-size: 9px;
}

/* Report Config Section */
.report-config-section {
  border-top: 1px solid rgba(255,255,255,0.1);
  flex-shrink: 0;
}

.config-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  background: rgba(123,45,142,0.1);
  transition: background 0.2s;
}

.config-section-header:hover {
  background: rgba(123,45,142,0.2);
}

.config-title {
  font-size: 12px;
  font-weight: 600;
  color: #7B2D8E;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-toggle {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #7B2D8E;
  background: rgba(123,45,142,0.15);
  border-radius: 4px;
}

.config-content {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.config-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-label {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.config-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-select {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  padding: 8px 10px;
  color: #DDD;
  font-size: 12px;
  outline: none;
  cursor: pointer;
}

.config-select:focus {
  border-color: #7B2D8E;
}

.config-select option {
  background: #1A1A1A;
  color: #DDD;
}

.config-textarea {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  padding: 8px 10px;
  color: #DDD;
  font-size: 12px;
  font-family: system-ui, sans-serif;
  resize: vertical;
  outline: none;
  min-height: 60px;
}

.config-textarea:focus {
  border-color: #7B2D8E;
}

.config-textarea::placeholder {
  color: #555;
}

.config-add-btn {
  background: rgba(123,45,142,0.2);
  border: 1px solid rgba(123,45,142,0.3);
  border-radius: 4px;
  padding: 2px 8px;
  color: #7B2D8E;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.config-add-btn:hover {
  background: rgba(123,45,142,0.3);
}

.variable-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.var-input {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px;
  padding: 6px 8px;
  color: #DDD;
  font-size: 11px;
  outline: none;
}

.var-input:focus {
  border-color: #7B2D8E;
}

.var-input::placeholder {
  color: #555;
}

.var-key {
  width: 80px;
  flex-shrink: 0;
}

.var-value {
  flex: 1;
}

.var-remove-btn {
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  transition: color 0.2s;
  flex-shrink: 0;
}

.var-remove-btn:hover {
  color: #E91E63;
}
</style>
