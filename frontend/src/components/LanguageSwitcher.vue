<template>
  <div class="lang-switcher" ref="switcher">
    <button class="lang-btn" @click="isOpen = !isOpen">
      <svg class="lang-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
      <span class="lang-label">{{ currentLabel }}</span>
      <svg class="lang-chevron" :class="{ open: isOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>

    <Transition name="dropdown">
      <div v-if="isOpen" class="lang-dropdown">
        <button
          v-for="lang in languages"
          :key="lang.code"
          class="lang-option"
          :class="{ active: lang.code === currentLocale }"
          @click="selectLanguage(lang.code)"
        >
          <span class="option-label">{{ lang.label }}</span>
          <svg v-if="lang.code === currentLocale" class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        </button>
      </div>
    </Transition>
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
  { code: 'fr', label: 'Français' },
  { code: 'it', label: 'Italiano' },
  { code: 'he', label: 'עברית' },
  { code: 'es', label: 'Español' },
  { code: 'ar', label: 'العربية' },
  { code: 'de', label: 'Deutsch' },
  { code: 'pt', label: 'Português' },
  { code: 'pl', label: 'Polski' },
  { code: 'nl', label: 'Nederlands' },
  { code: 'tr', label: 'Türkçe' },
  { code: 'ru', label: 'Русский' }
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
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  background: var(--card-bg, transparent);
  border: 1px solid var(--card-border, rgba(255, 255, 255, 0.15));
  border-radius: 8px;
  color: var(--text-primary, inherit);
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.lang-btn:hover {
  border-color: var(--card-border-hover, rgba(255, 255, 255, 0.3));
  background: var(--accent-subtle, rgba(255, 255, 255, 0.05));
}

.lang-icon {
  width: 15px;
  height: 15px;
  opacity: 0.6;
}

.lang-label {
  min-width: 50px;
}

.lang-chevron {
  width: 14px;
  height: 14px;
  opacity: 0.5;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.lang-chevron.open {
  transform: rotate(180deg);
}

.lang-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  inset-inline-end: 0;
  min-width: 180px;
  max-height: 360px;
  overflow-y: auto;
  background: var(--card-bg, #18181b);
  border: 1px solid var(--card-border, #27272a);
  border-radius: 10px;
  box-shadow: var(--card-shadow-hover, 0 8px 30px rgba(0, 0, 0, 0.35));
  backdrop-filter: blur(12px);
  z-index: 1000;
  padding: 4px;
}

.lang-dropdown::-webkit-scrollbar {
  width: 4px;
}

.lang-dropdown::-webkit-scrollbar-thumb {
  background: var(--card-border, #3f3f46);
  border-radius: 2px;
}

.lang-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 9px 14px;
  border: none;
  border-radius: 6px;
  background: transparent;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: 0.85rem;
  text-align: start;
  cursor: pointer;
  transition: all 0.15s ease;
  color: var(--text-secondary, #a1a1aa);
}

.lang-option:hover {
  background: var(--accent-subtle, rgba(255, 69, 0, 0.1));
  color: var(--text-primary, #fafafa);
}

.lang-option.active {
  color: var(--accent, #ff4500);
  font-weight: 600;
}

.check-icon {
  width: 14px;
  height: 14px;
  color: var(--accent, #ff4500);
  flex-shrink: 0;
}

/* Dropdown animation */
.dropdown-enter-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.dropdown-leave-active {
  transition: all 0.15s ease-in;
}

.dropdown-enter-from {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}

.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
</style>
