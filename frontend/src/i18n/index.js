import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import he from './locales/he.json'
import ru from './locales/ru.json'
import es from './locales/es.json'
import de from './locales/de.json'
import fr from './locales/fr.json'
import it from './locales/it.json'
import pt from './locales/pt.json'
import pl from './locales/pl.json'
import nl from './locales/nl.json'
import tr from './locales/tr.json'
import ar from './locales/ar.json'

const RTL_LOCALES = ['he', 'ar']

function detectLocale() {
  const saved = localStorage.getItem('agenikpredict-locale')
  if (saved) return saved

  const browserLang = navigator.language?.split('-')[0]
  const supported = ['en', 'he', 'ru', 'es', 'de', 'fr', 'it', 'pt', 'pl', 'nl', 'tr', 'ar']
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
  messages: { en, he, ru, es, de, fr, it, pt, pl, nl, tr, ar }
})

export function setLocale(newLocale) {
  i18n.global.locale.value = newLocale
  localStorage.setItem('agenikpredict-locale', newLocale)
  applyDirection(newLocale)
}

export { RTL_LOCALES }
export default i18n
