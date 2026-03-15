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
  offset-path: rect(0 auto auto 0 round var(--beam-size));
  animation: border-beam-move var(--beam-duration) var(--beam-delay) infinite linear;
  width: var(--beam-size);
  height: var(--beam-border-width);
  background: linear-gradient(
    to left,
    var(--beam-color-from),
    var(--beam-color-to),
    transparent
  );
  opacity: 0.75;
}
</style>
