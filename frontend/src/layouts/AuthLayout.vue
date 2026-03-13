<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import roboscopeLogo from '@/assets/roboscope_white.png'

const { t } = useI18n()
</script>

<template>
  <div class="auth-layout">
    <div class="auth-content">
      <!-- Left side: Hero / Info -->
      <div class="auth-hero">
        <div class="hero-inner">
          <img :src="roboscopeLogo" alt="RoboScope" class="hero-logo" />
          <p class="hero-tagline">{{ t('auth.tagline') }}</p>
          <p class="hero-subtitle">{{ t('auth.subtitle') }}</p>

          <div class="hero-features">
            <div class="feature-item" :style="{ animationDelay: '0.3s' }">
              <span class="feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h7v7H3z"/><path d="M14 3h7v7h-7z"/><path d="M3 14h7v7H3z"/><path d="M14 14h7v7h-7z"/></svg>
              </span>
              <span class="feature-text">{{ t('auth.features.explorer') }}</span>
            </div>
            <div class="feature-item" :style="{ animationDelay: '0.4s' }">
              <span class="feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              </span>
              <span class="feature-text">{{ t('auth.features.execution') }}</span>
            </div>
            <div class="feature-item" :style="{ animationDelay: '0.5s' }">
              <span class="feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
              </span>
              <span class="feature-text">{{ t('auth.features.reports') }}</span>
            </div>
            <div class="feature-item" :style="{ animationDelay: '0.6s' }">
              <span class="feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 7h-3a2 2 0 0 1-2-2V2"/><path d="M9 18a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h7l4 4v10a2 2 0 0 1-2 2Z"/><path d="M3 7.6v12.8A1.6 1.6 0 0 0 4.6 22h9.8"/></svg>
              </span>
              <span class="feature-text">{{ t('auth.features.environments') }}</span>
            </div>
            <div class="feature-item" :style="{ animationDelay: '0.7s' }">
              <span class="feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2a4 4 0 0 1 4 4c0 1.95-1.4 3.58-3.25 3.93"/><path d="M8.24 9.93A4 4 0 0 1 12 2"/><circle cx="12" cy="17" r="5"/><path d="m14.5 15.5-5 3"/><path d="m9.5 15.5 5 3"/></svg>
              </span>
              <span class="feature-text">{{ t('auth.features.ai') }}</span>
            </div>
            <div class="feature-item" :style="{ animationDelay: '0.8s' }">
              <span class="feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </span>
              <span class="feature-text">{{ t('auth.features.rbac') }}</span>
            </div>
          </div>

          <div class="hero-install">
            <p class="install-title">{{ t('auth.install.title') }}</p>
            <div class="install-tabs">
              <div class="install-block">
                <span class="install-label">macOS / Linux</span>
                <code class="install-cmd">./install-mac-and-linux.sh && ./start-mac-and-linux.sh</code>
              </div>
              <div class="install-block">
                <span class="install-label">Windows</span>
                <code class="install-cmd">install-windows.bat &amp;&amp; start-windows.bat</code>
              </div>
            </div>
            <p class="install-hint">{{ t('auth.install.hint') }}</p>
          </div>
        </div>
      </div>

      <!-- Right side: Login form -->
      <div class="auth-form-container">
        <slot />
      </div>
    </div>

    <!-- Animated background -->
    <div class="bg-decoration bg-circle-1"></div>
    <div class="bg-decoration bg-circle-2"></div>
    <div class="bg-decoration bg-circle-3"></div>
    <div class="bg-grid"></div>
  </div>
</template>

<style scoped>
.auth-layout {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0F1A30 0%, #1A2D50 40%, #1B3258 70%, #122240 100%);
  position: relative;
  overflow: hidden;
}

/* Subtle grid pattern */
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(59, 125, 216, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(59, 125, 216, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  z-index: 0;
}

.auth-content {
  display: flex;
  align-items: center;
  gap: 60px;
  max-width: 960px;
  width: 100%;
  padding: 32px 24px;
  position: relative;
  z-index: 2;
}

/* Hero (left side) */
.auth-hero {
  flex: 1;
  min-width: 0;
}

.hero-inner {
  animation: fadeSlideUp 0.6s ease-out both;
}

.hero-logo {
  height: 56px;
  width: auto;
  margin-bottom: 16px;
  filter: drop-shadow(0 2px 8px rgba(59, 125, 216, 0.3));
}

.hero-tagline {
  color: #ffffff;
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 8px;
  letter-spacing: -0.3px;
}

.hero-subtitle {
  color: rgba(255, 255, 255, 0.55);
  font-size: 14px;
  line-height: 1.5;
  margin: 0 0 28px;
  max-width: 360px;
}

/* Feature list */
.hero-features {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 20px;
  margin-bottom: 28px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  animation: fadeSlideUp 0.5s ease-out both;
}

.feature-icon {
  color: var(--color-primary, #3B7DD8);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 125, 216, 0.1);
  border-radius: 8px;
  flex-shrink: 0;
}

.feature-text {
  color: rgba(255, 255, 255, 0.8);
  font-size: 13px;
  font-weight: 500;
}

/* Install section */
.hero-install {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 20px;
  animation: fadeSlideUp 0.6s ease-out 0.8s both;
}

.install-title {
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  margin: 0 0 10px;
}

.install-tabs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.install-block {
  display: flex;
  align-items: center;
  gap: 10px;
}

.install-label {
  color: rgba(255, 255, 255, 0.45);
  font-size: 11px;
  font-weight: 600;
  min-width: 90px;
  flex-shrink: 0;
}

.install-cmd {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 6px 10px;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.7);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.install-hint {
  color: rgba(255, 255, 255, 0.35);
  font-size: 11px;
  margin: 8px 0 0;
}

/* Form container (right side) */
.auth-form-container {
  width: 380px;
  flex-shrink: 0;
  animation: fadeSlideUp 0.6s ease-out 0.15s both;
}

/* Background decorations */
.bg-decoration {
  position: absolute;
  border-radius: 50%;
  z-index: 1;
}

.bg-circle-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(59, 125, 216, 0.07) 0%, transparent 70%);
  top: -200px;
  right: -150px;
  animation: floatSlow 20s ease-in-out infinite;
}

.bg-circle-2 {
  width: 450px;
  height: 450px;
  background: radial-gradient(circle, rgba(212, 136, 62, 0.05) 0%, transparent 70%);
  bottom: -120px;
  left: -120px;
  animation: floatSlow 25s ease-in-out infinite reverse;
}

.bg-circle-3 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(59, 125, 216, 0.04) 0%, transparent 70%);
  top: 50%;
  left: 40%;
  transform: translate(-50%, -50%);
  animation: pulse 8s ease-in-out infinite;
}

/* Animations */
@keyframes fadeSlideUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes floatSlow {
  0%, 100% { transform: translate(0, 0); }
  25% { transform: translate(15px, -20px); }
  50% { transform: translate(-10px, 15px); }
  75% { transform: translate(20px, 10px); }
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.7; transform: translate(-50%, -50%) scale(1.15); }
}

/* Responsive: stack vertically on smaller screens */
@media (max-width: 768px) {
  .auth-content {
    flex-direction: column;
    gap: 32px;
    padding: 40px 20px;
  }

  .auth-hero {
    text-align: center;
  }

  .hero-subtitle {
    margin-left: auto;
    margin-right: auto;
  }

  .hero-features {
    grid-template-columns: 1fr;
    max-width: 260px;
    margin-left: auto;
    margin-right: auto;
  }

  .auth-form-container {
    width: 100%;
    max-width: 380px;
  }

  .install-block {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .install-cmd {
    width: 100%;
  }
}
</style>
