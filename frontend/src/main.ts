import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import './assets/styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(i18n)
app.use(router)

// Story A11Y-1: keep `<html lang>` in sync with the active i18n
// locale so assistive tech announces content in the right language.
const i18nGlobal = i18n.global
function syncHtmlLang(locale: string) {
  document.documentElement.lang = locale
}
syncHtmlLang(i18nGlobal.locale.value)
watch(i18nGlobal.locale, syncHtmlLang)

// Global error handler to prevent white-screen crashes
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err, '\nComponent:', instance, '\nInfo:', info)
}

app.mount('#app')
