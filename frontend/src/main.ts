import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import './assets/styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(i18n)
app.use(router)

// Global error handler to prevent white-screen crashes
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err, '\nComponent:', instance, '\nInfo:', info)
}

app.mount('#app')
