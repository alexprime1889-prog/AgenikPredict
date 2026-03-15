<template>
  <canvas ref="canvasRef" class="particles-canvas" />
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  quantity: { type: Number, default: 50 },
  color: { type: String, default: '#ffffff' },
  size: { type: Number, default: 0.4 },
  staticity: { type: Number, default: 50 },
  ease: { type: Number, default: 70 },
})

const canvasRef = ref(null)
let ctx = null
let particles = []
let animationId = null
let mouse = { x: 0, y: 0 }
let canvasSize = { w: 0, h: 0 }
let dpr = 1

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : { r: 255, g: 255, b: 255 }
}

function createParticle() {
  const rgb = hexToRgb(props.color)
  return {
    x: Math.random() * canvasSize.w,
    y: Math.random() * canvasSize.h,
    translateX: 0,
    translateY: 0,
    size: Math.random() * 2 + props.size,
    alpha: 0,
    targetAlpha: parseFloat((Math.random() * 0.6 + 0.1).toFixed(1)),
    dx: (Math.random() - 0.5) * 0.2,
    dy: (Math.random() - 0.5) * 0.2,
    magnetism: 0.1 + Math.random() * 4,
    color: `${rgb.r} ${rgb.g} ${rgb.b}`,
  }
}

function initParticles() {
  particles = []
  for (let i = 0; i < props.quantity; i++) {
    particles.push(createParticle())
  }
}

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const parent = canvas.parentElement || document.body
  dpr = window.devicePixelRatio || 1
  canvasSize.w = parent.offsetWidth
  canvasSize.h = parent.offsetHeight
  canvas.width = canvasSize.w * dpr
  canvas.height = canvasSize.h * dpr
  canvas.style.width = `${canvasSize.w}px`
  canvas.style.height = `${canvasSize.h}px`
  ctx.scale(dpr, dpr)
}

function drawParticle(p) {
  if (!ctx) return
  const { x, y, translateX, translateY, size, alpha, color } = p
  ctx.beginPath()
  ctx.arc(x + translateX, y + translateY, size, 0, Math.PI * 2)
  ctx.fillStyle = `rgba(${color} / ${alpha})`
  ctx.fill()
}

function animate() {
  if (!ctx) return
  ctx.clearRect(0, 0, canvasSize.w, canvasSize.h)

  particles.forEach((p, i) => {
    // Movement
    p.x += p.dx
    p.y += p.dy

    // Mouse interaction
    const dx = mouse.x - (p.x + p.translateX)
    const dy = mouse.y - (p.y + p.translateY)
    const distance = Math.sqrt(dx * dx + dy * dy)
    if (distance > 0) {
      const force = Math.min(p.magnetism / (distance / props.staticity), p.magnetism)
      p.translateX += (dx / distance) * force * (1 / props.ease)
      p.translateY += (dy / distance) * force * (1 / props.ease)
    }

    // Fade in
    if (p.alpha < p.targetAlpha) {
      p.alpha = Math.min(p.alpha + 0.02, p.targetAlpha)
    }

    // Boundary wrapping
    if (
      p.x + p.translateX < -p.size ||
      p.x + p.translateX > canvasSize.w + p.size ||
      p.y + p.translateY < -p.size ||
      p.y + p.translateY > canvasSize.h + p.size
    ) {
      // Reset particle
      p.x = Math.random() * canvasSize.w
      p.y = Math.random() * canvasSize.h
      p.translateX = 0
      p.translateY = 0
      p.alpha = 0
    }

    drawParticle(p)
  })

  animationId = requestAnimationFrame(animate)
}

function onMouseMove(e) {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  mouse.x = e.clientX - rect.left
  mouse.y = e.clientY - rect.top
}

function onResize() {
  resizeCanvas()
  initParticles()
}

onMounted(() => {
  const canvas = canvasRef.value
  if (!canvas) return
  ctx = canvas.getContext('2d')
  resizeCanvas()
  initParticles()
  animate()
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  if (animationId) cancelAnimationFrame(animationId)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.particles-canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
