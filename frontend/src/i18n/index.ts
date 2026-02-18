import { createI18n } from 'vue-i18n'
import de from './locales/de'
import en from './locales/en'
import fr from './locales/fr'
import es from './locales/es'

const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem('lang') || 'de',
  fallbackLocale: 'de',
  messages: { de, en, fr, es },
})

export default i18n
