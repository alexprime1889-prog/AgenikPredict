<template>
  <div class="lang-switcher" ref="switcher">
    <button class="lang-btn" @click="isOpen = !isOpen">
      {{ currentLabel }}
      <span class="chevron" :class="{ open: isOpen }">▾</span>
    </button>
    <div v-if="isOpen" class="lang-dropdown">
      <button
        v-for="lang in languages"
        :key="lang.code"
        class="lang-option"
        :class="{ active: lang.code === currentLocale }"
        @click="selectLanguage(lang.code)"
      >
        {{ lang.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale } from '../i18n'

const { locale } = useI18n()
const isOpen = ref(false)
const switcher = ref(null)

const languages = [
  { code: 'en', label: 'English' },
  { code: 'he', label: 'עברית' },
  { code: 'ru', label: 'Русский' },
  { code: 'es', label: 'Español' },
  { code: 'de', label: 'Deutsch' },
  { code: 'fr', label: 'Français' },
  { code: 'it', label: 'Italiano' },
  { code: 'pt', label: 'Português' },
  { code: 'pl', label: 'Polski' },
  { code: 'nl', label: 'Nederlands' },
  { code: 'tr', label: 'Türkçe' },
  { code: 'ar', label: 'العربية' }
]

const currentLocale = computed(() => locale.value)
const currentLabel = computed(() => {
  const lang = languages.find(l => l.code === locale.value)
  return lang ? lang.label : 'English'
})

const selectLanguage = (code) => {
  setLocale(code)
  isOpen.value = false
}

const handleClickOutside = (e) => {
  if (switcher.value && !switcher.value.contains(e.target)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.lang-switcher {
  position: relative;
}

.lang-btn {
  background: transparent;
  border: 1px solid #DDD;
  padding: 6px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  color: inherit;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.lang-btn:hover {
  border-color: #999;
}

.chevron {
  font-size: 0.7rem;
  transition: transform 0.2s;
}

.chevron.open {
  transform: rotate(180deg);
}

.lang-dropdown {
  position: absolute;
  top: 100%;
  inset-inline-end: 0;
  margin-top: 4px;
  background: #FFF;
  border: 1px solid #DDD;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  min-width: 140px;
}

.lang-option {
  display: block;
  width: 100%;
  padding: 8px 16px;
  border: none;
  background: transparent;
  font-size: 0.85rem;
  text-align: start;
  cursor: pointer;
  transition: background 0.15s;
  color: #333;
}

.lang-option:hover {
  background: #F5F5F5;
}

.lang-option.active {
  font-weight: 700;
  color: #000;
  background: #F0F0F0;
}
</style>
