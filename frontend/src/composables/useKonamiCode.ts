import { onMounted, onUnmounted } from 'vue'

const KONAMI_SEQUENCE = [
  'ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown',
  'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight',
  'KeyB', 'KeyA',
] as const

const REQUIRED_LEN = KONAMI_SEQUENCE.length

function isTextEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target instanceof HTMLInputElement) return true
  if (target instanceof HTMLTextAreaElement) return true
  // `isContentEditable` is the canonical check, but JSDOM's implementation is
  // unreliable — fall back to the attribute it would otherwise reflect.
  if (target.isContentEditable) return true
  const ce = target.getAttribute('contenteditable')
  return ce === '' || ce === 'true' || ce === 'plaintext-only'
}

export function useKonamiCode(onTrigger: () => void): void {
  const buffer: string[] = []
  let reducedMotion = false
  let mq: MediaQueryList | null = null
  const onMqChange = (e: MediaQueryListEvent) => { reducedMotion = e.matches }

  const handleKeydown = (event: KeyboardEvent) => {
    if (isTextEntryTarget(event.target)) return

    const expected = KONAMI_SEQUENCE[buffer.length]
    if (event.code === expected) {
      buffer.push(event.code)
      if (buffer.length === REQUIRED_LEN) {
        buffer.length = 0
        if (!reducedMotion) onTrigger()
      }
    } else {
      // Mismatched key: silently reset. If the new key starts a fresh
      // sequence (Arrow Up), seed the buffer with it.
      buffer.length = 0
      if (event.code === KONAMI_SEQUENCE[0]) buffer.push(event.code)
    }
  }

  onMounted(() => {
    if (typeof window === 'undefined') return
    if (typeof window.matchMedia === 'function') {
      mq = window.matchMedia('(prefers-reduced-motion: reduce)')
      reducedMotion = mq.matches
      mq.addEventListener('change', onMqChange)
    }
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('keydown', handleKeydown)
    }
    if (mq) mq.removeEventListener('change', onMqChange)
  })
}
