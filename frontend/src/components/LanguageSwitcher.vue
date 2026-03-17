<template>
  <div class="lang-switcher" ref="switcher">
    <button ref="btnRef" class="lang-btn" @click="toggleDropdown">
      <svg class="lang-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
      <span class="lang-label">{{ currentLabel }}</span>
      <svg class="lang-chevron" :class="{ open: isOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>

    <Teleport to="body">
      <Transition name="dropdown">
        <div v-if="isOpen" class="lang-dropdown" :style="dropdownStyle">
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
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale } from '../i18n'

const { locale } = useI18n()
const isOpen = ref(false)
const switcher = ref(null)
const btnRef = ref(null)

const dropdownPos = reactive({ top: 0, right: 0 })
const dropdownStyle = computed(() => ({
  position: 'fixed',
  top: dropdownPos.top + 'px',
  right: dropdownPos.right + 'px',
}))

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

function toggleDropdown() {
  if (!isOpen.value && btnRef.value) {
    const rect = btnRef.value.getBoundingClientRect()
    dropdownPos.top = rect.bottom + 6
    dropdownPos.right = window.innerWidth - rect.right
  }
  isOpen.value = !isOpen.value
}

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
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.8);
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.lang-btn:hover {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.05);
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
</style>

<style>
.lang-dropdown {
  min-width: 180px;
  max-height: 360px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(24px);
  z-index: 99999;
  padding: 4px;
}

.lang-dropdown::-webkit-scrollbar {
  width: 4px;
}

.lang-dropdown::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}

.lang-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 9px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: 0.85rem;
  text-align: start;
  cursor: pointer;
  transition: all 0.15s ease;
  color: rgba(255, 255, 255, 0.6);
}

.lang-option:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.lang-option.active {
  color: #ff4500;
  font-weight: 600;
}

.check-icon {
  width: 14px;
  height: 14px;
  color: #ff4500;
  flex-shrink: 0;
}

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
