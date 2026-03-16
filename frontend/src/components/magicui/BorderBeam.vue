<template>
  <div class="border-beam" :style="beamStyle" />
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: Number, default: 200 },
  duration: { type: Number, default: 12 },
  delay: { type: Number, default: 11 },
  colorFrom: { type: String, default: '#ffaa40' },
  colorTo: { type: String, default: '#9c40ff' },
  borderWidth: { type: Number, default: 1.5 },
})

const beamStyle = computed(() => ({
  '--beam-size': `${props.size}px`,
  '--beam-duration': `${props.duration}s`,
  '--beam-delay': `${props.delay}s`,
  '--beam-color-from': props.colorFrom,
  '--beam-color-to': props.colorTo,
  '--beam-border-width': `${props.borderWidth}px`,
}))
</script>

<style scoped>
.border-beam {
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  border: transparent solid var(--beam-border-width);
  mask-clip: padding-box, border-box;
  mask-composite: intersect;
  mask-image: linear-gradient(transparent, transparent), linear-gradient(#000, #000);
}

.border-beam::after {
  content: '';
  position: absolute;
  width: var(--beam-size);
  aspect-ratio: 1;
  background: linear-gradient(
    to left,
    var(--beam-color-from),
    var(--beam-color-to),
    transparent
  );
  offset-path: rect(0 auto auto 0 round var(--beam-size));
  animation: border-beam-move var(--beam-duration) linear infinite;
  animation-delay: calc(var(--beam-delay) * -1);
}

@keyframes border-beam-move {
  0% { offset-distance: 0%; }
  100% { offset-distance: 100%; }
}
</style>
