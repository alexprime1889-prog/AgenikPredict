<template>
  <div class="hero-graph-preview" ref="containerRef">
    <svg ref="svgRef" class="hero-graph-svg" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as d3 from 'd3'

const { t, locale } = useI18n()

const containerRef = ref(null)
const svgRef = ref(null)
let simulation = null
let buildTimer = null
let g = null
let linkSelection = null
let nodeSelection = null
let labelSelection = null
let typeLabelSelection = null
let forceLink = null

const COLORS = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#2D3436', '#6C5CE7', '#00B894', '#FD79A8']

const NODE_KEYS = ['n1','n2','n3','n4','n5','n6','n7','n8','n9','n10','n11','n12','n13','n14']
const NODE_TYPES = ['Initiative','Role','Role','Role','Role','Metric','Domain','Initiative','Output','Entity','Actor','Metric','Actor','Domain']

function getDemoNodes() {
  return NODE_KEYS.map((key, i) => ({
    uuid: key,
    name: t(`graph.demo.${key}`),
    labels: [t(`graph.demo.type.${NODE_TYPES[i]}`)]
  }))
}

const BUILD_STEPS = [
  { nodeIndex: 0 },
  { nodeIndex: 1, edges: [{ source: 'n1', target: 'n2' }] },
  { nodeIndex: 2, edges: [{ source: 'n1', target: 'n3' }] },
  { nodeIndex: 3, edges: [{ source: 'n2', target: 'n4' }, { source: 'n3', target: 'n4' }] },
  { nodeIndex: 4, edges: [{ source: 'n4', target: 'n5' }] },
  { nodeIndex: 5, edges: [{ source: 'n4', target: 'n6' }, { source: 'n2', target: 'n6' }] },
  { nodeIndex: 6, edges: [{ source: 'n3', target: 'n7' }, { source: 'n4', target: 'n7' }] },
  { nodeIndex: 7, edges: [{ source: 'n4', target: 'n8' }, { source: 'n1', target: 'n8' }] },
  { nodeIndex: 8, edges: [{ source: 'n2', target: 'n9' }, { source: 'n8', target: 'n9' }] },
  { nodeIndex: 9, edges: [{ source: 'n4', target: 'n10' }, { source: 'n8', target: 'n10' }] },
  { nodeIndex: 10, edges: [{ source: 'n4', target: 'n11' }, { source: 'n8', target: 'n11' }] },
  { nodeIndex: 11, edges: [{ source: 'n6', target: 'n12' }, { source: 'n9', target: 'n12' }] },
  { nodeIndex: 12, edges: [{ source: 'n1', target: 'n13' }, { source: 'n7', target: 'n13' }] },
  { nodeIndex: 13, edges: [{ source: 'n8', target: 'n14' }, { source: 'n7', target: 'n14' }, { source: 'n11', target: 'n14' }] }
]

let currentNodes = []
let currentEdges = []
let buildStepIndex = 0
const STEP_DELAY_MS = 750
const PAUSE_BEFORE_LOOP_MS = 3500

function getWidthHeight() {
  if (!containerRef.value) return { width: 460, height: 400 }
  return { width: containerRef.value.clientWidth || 460, height: containerRef.value.clientHeight || 400 }
}

function initSimulationAndSvg() {
  if (!svgRef.value || !containerRef.value) return
  const { width, height } = getWidthHeight()
  const cx = width / 2, cy = height / 2

  const svg = d3.select(svgRef.value).attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`)
  svg.selectAll('*').remove()
  g = svg.append('g')

  forceLink = d3.forceLink().id(d => d.id).distance(58).strength(0.6)
  simulation = d3.forceSimulation()
    .force('link', forceLink)
    .force('charge', d3.forceManyBody().strength(-160))
    .force('center', d3.forceCenter(cx, cy))
    .force('collide', d3.forceCollide(26))
    .force('x', d3.forceX(cx).strength(0.08))
    .force('y', d3.forceY(cy).strength(0.08))

  linkSelection = g.append('g').attr('class', 'links').selectAll('line')
  nodeSelection = g.append('g').attr('class', 'nodes').selectAll('circle')
  labelSelection = g.append('g').attr('class', 'node-labels').selectAll('text')
  typeLabelSelection = g.append('g').attr('class', 'node-type-labels').selectAll('text')

  simulation.on('tick', () => {
    if (!linkSelection.empty()) {
      linkSelection.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    }
    if (!nodeSelection.empty()) {
      nodeSelection.attr('cx', d => d.x).attr('cy', d => d.y)
    }
    if (!labelSelection.empty()) {
      labelSelection.attr('x', d => d.x + 14).attr('y', d => d.y + 5)
    }
    if (!typeLabelSelection.empty()) {
      typeLabelSelection.attr('x', d => d.x + 14).attr('y', d => d.y + 16)
    }
  })
}

function applyBuildStep() {
  if (buildStepIndex >= BUILD_STEPS.length) { buildStepIndex = 0; return }
  const demoNodes = getDemoNodes()
  const step = BUILD_STEPS[buildStepIndex]
  const raw = demoNodes[step.nodeIndex]
  currentNodes.push({ id: raw.uuid, name: raw.name, type: raw.labels?.[0] || 'Entity' })
  if (step.edges) step.edges.forEach(e => currentEdges.push({ source: e.source, target: e.target }))
  buildStepIndex++

  const { width, height } = getWidthHeight()
  forceLink.links(currentEdges)
  simulation.nodes(currentNodes)
  simulation.alpha(0.45).restart()

  const colorScale = d3.scaleOrdinal().domain([...new Set(currentNodes.map(n => n.type))]).range(COLORS)
  const edgeKey = d => `${typeof d.source === 'object' ? d.source.id : d.source}-${typeof d.target === 'object' ? d.target.id : d.target}`

  linkSelection = g.select('.links').selectAll('line').data(currentEdges, edgeKey)
  linkSelection.join(enter => enter.append('line').attr('stroke', 'rgba(255,255,255,0.5)').attr('stroke-width', 1.6))

  nodeSelection = g.select('.nodes').selectAll('circle').data(currentNodes, d => d.id)
  nodeSelection.join(enter => enter.append('circle').attr('r', 0).attr('fill', d => colorScale(d.type)).attr('stroke', 'rgba(255,255,255,0.9)').attr('stroke-width', 1.5).attr('cx', d => d.x ?? width / 2).attr('cy', d => d.y ?? height / 2).transition().duration(280).attr('r', 9))

  labelSelection = g.select('.node-labels').selectAll('text').data(currentNodes, d => d.id)
  labelSelection.join(enter => enter.append('text').text(d => d.name.length > 11 ? d.name.slice(0, 9) + '…' : d.name).attr('font-size', '11px').attr('fill', 'rgba(255,255,255,0.95)').attr('dx', 14).attr('dy', 5).style('pointer-events', 'none').style('font-family', 'system-ui, sans-serif'))

  typeLabelSelection = g.select('.node-type-labels').selectAll('text').data(currentNodes, d => d.id)
  typeLabelSelection.join(enter => enter.append('text').text(d => d.type).attr('font-size', '9px').attr('fill', 'rgba(255,200,100,0.95)').attr('dx', 14).attr('dy', 16).attr('font-weight', '600').style('pointer-events', 'none').style('font-family', 'system-ui, sans-serif'))
}

function runNextStep() {
  applyBuildStep()
  if (buildStepIndex >= BUILD_STEPS.length) {
    buildTimer = setTimeout(resetAndReplay, PAUSE_BEFORE_LOOP_MS)
  } else {
    buildTimer = setTimeout(runNextStep, STEP_DELAY_MS)
  }
}

function resetAndReplay() {
  currentNodes = []; currentEdges = []; buildStepIndex = 0
  if (simulation) { simulation.stop(); forceLink.links([]); simulation.nodes([]) }
  g.select('.links').selectAll('line').remove()
  g.select('.nodes').selectAll('circle').remove()
  g.select('.node-labels').selectAll('text').remove()
  g.select('.node-type-labels').selectAll('text').remove()
  linkSelection = g.select('.links').selectAll('line')
  nodeSelection = g.select('.nodes').selectAll('circle')
  labelSelection = g.select('.node-labels').selectAll('text')
  typeLabelSelection = g.select('.node-type-labels').selectAll('text')
  runNextStep()
}

function fullRestart() {
  if (buildTimer) clearTimeout(buildTimer)
  if (simulation) simulation.stop()
  initSimulationAndSvg()
  currentNodes = []; currentEdges = []; buildStepIndex = 0
  runNextStep()
}

watch(locale, () => {
  fullRestart()
})

onMounted(() => { initSimulationAndSvg(); runNextStep(); window.addEventListener('resize', fullRestart) })
onUnmounted(() => { if (buildTimer) clearTimeout(buildTimer); window.removeEventListener('resize', fullRestart); if (simulation) simulation.stop() })
</script>

<style scoped>
.hero-graph-preview {
  width: 100%;
  height: 100%;
  min-height: 380px;
}

.hero-graph-svg {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
