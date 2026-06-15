import { createI18n } from 'vue-i18n'
import de from './locales/de'
import en from './locales/en'
import fr from './locales/fr'
import es from './locales/es'
import zh from './locales/zh'

const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem('lang') || 'de',
  // zh is deep-merged over en already, but fall back to English (then German)
  // for any residual gap rather than showing German to Chinese users.
  fallbackLocale: { zh: ['en', 'de'], default: ['de'] },
  messages: { de, en, fr, es, zh },
})

export default i18n
