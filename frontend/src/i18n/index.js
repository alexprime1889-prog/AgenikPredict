import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import he from './locales/he.json'
import ru from './locales/ru.json'
import es from './locales/es.json'
import de from './locales/de.json'

const RTL_LOCALES = ['he']

function detectLocale() {
  const saved = localStorage.getItem('agenikpredict-locale')
  if (saved) return saved

  const browserLang = navigator.language?.split('-')[0]
  const supported = ['en', 'he', 'ru', 'es', 'de']
  return supported.includes(browserLang) ? browserLang : 'en'
}

function applyDirection(locale) {
  const dir = RTL_LOCALES.includes(locale) ? 'rtl' : 'ltr'
  document.documentElement.setAttribute('dir', dir)
  document.documentElement.setAttribute('lang', locale)
}

const locale = detectLocale()
applyDirection(locale)

const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: 'en',
  messages: { en, he, ru, es, de }
})

export function setLocale(newLocale) {
  i18n.global.locale.value = newLocale
  localStorage.setItem('agenikpredict-locale', newLocale)
  applyDirection(newLocale)
}

export { RTL_LOCALES }
export default i18n
