# Story EE-1: Konami Code Robot Parade (Easter Egg)

Status: planned

## Story

As a RoboScope user with good taste in retro gaming,
I want a hidden Konami-code easter egg that sends a little robot marching across the screen,
so that the team has a playful moment of joy when they stumble on it.

## Acceptance Criteria

1. **AC1 — Trigger sequence.** When the user presses the Konami code (`↑ ↑ ↓ ↓ ← → ← → B A`) anywhere in the app while focus is NOT inside an `<input>`, `<textarea>`, or `contenteditable` element, a robot sprite marches from the left edge of the viewport to the right edge along the bottom of the screen.

2. **AC2 — One-shot, non-blocking.** The animation plays exactly once per trigger, runs in ~4 seconds, and never blocks UI interaction (no modal, no overlay that captures clicks — only `pointer-events: none`).

3. **AC3 — Retriggerable.** After the animation finishes and the sprite leaves the viewport, the next Konami sequence triggers it again. Partial/incorrect sequences reset the buffer silently.

4. **AC4 — No asset bloat, offline-only.** The robot is rendered as an inline SVG or CSS (no network requests, no new bundled image > 5 KB). No Google Fonts, no CDN. Adheres to the offline-only rule in `CLAUDE.md`.

5. **AC5 — Accessibility.** The sprite has `aria-hidden="true"`. If the user has `prefers-reduced-motion: reduce` set, the easter egg is fully disabled (no sprite, no animation) — the key sequence becomes a no-op.

6. **AC6 — Global scope, single mount.** The listener is attached once at the app-shell level (e.g., `App.vue`) and removed on unmount. Switching routes does not duplicate listeners or sprites.

7. **AC7 — Smoke test.** A Vitest unit test verifies that dispatching the 10-key sequence to the composable/component toggles the "parade active" state to `true`, and that dispatching a wrong sequence leaves it `false`.

8. **AC8 — No i18n strings, no docs.** Because it's an easter egg, it introduces no user-facing translatable text (would spoil the surprise) and is NOT documented in the in-app docs or README.

## Tasks / Subtasks

- [ ] **Task 1: Composable for key sequence detection** (AC 1, 3, 6)
  - [ ] Create `frontend/src/composables/useKonamiCode.ts` exporting `useKonamiCode(onTrigger: () => void)`.
  - [ ] Internal buffer of the last 10 keydown `event.code` values. Compare against `["ArrowUp","ArrowUp","ArrowDown","ArrowDown","ArrowLeft","ArrowRight","ArrowLeft","ArrowRight","KeyB","KeyA"]`.
  - [ ] Skip when `event.target` is `<input>`, `<textarea>`, or `[contenteditable]` — use `instanceof HTMLInputElement` etc.
  - [ ] Attach listener in `onMounted`, remove in `onUnmounted`.

- [ ] **Task 2: Robot parade component** (AC 1, 2, 4, 5)
  - [ ] Create `frontend/src/components/ui/RobotParade.vue`.
  - [ ] Inline SVG robot (simple — head, body, two legs, antenna — ~30 lines of SVG, under 2 KB).
  - [ ] Fixed position at `bottom: 8px`, `left: -80px`, `z-index: 9999`, `pointer-events: none`, `aria-hidden="true"`.
  - [ ] CSS animation: `translateX(calc(100vw + 80px))` over 4s linear, with a small vertical `translateY` bob and leg shuffle using a second keyframe on child elements.
  - [ ] Emits `@done` after the `animationend` event so the parent can unmount the sprite.

- [ ] **Task 3: Mount at app shell** (AC 6)
  - [ ] In `frontend/src/App.vue` (or the existing top-level layout if that's where global listeners live), import `useKonamiCode` and `RobotParade`.
  - [ ] Maintain a `paradeActive = ref(false)` flag. Konami trigger sets it `true`; `@done` sets it back to `false`.
  - [ ] Conditionally render `<RobotParade v-if="paradeActive" @done="paradeActive = false" />`.

- [ ] **Task 4: Reduced-motion guard** (AC 5)
  - [ ] In `useKonamiCode`, early-return from the trigger if `window.matchMedia('(prefers-reduced-motion: reduce)').matches`.
  - [ ] Update the `matchMedia` listener live so toggling the OS setting takes effect without a reload.

- [ ] **Task 5: Unit test** (AC 7)
  - [ ] `frontend/src/composables/__tests__/useKonamiCode.spec.ts`.
  - [ ] Mount a dummy component that uses the composable; dispatch the 10-key sequence via `window.dispatchEvent(new KeyboardEvent('keydown', { code: '...' }))` and assert `onTrigger` was called once.
  - [ ] Dispatch an incorrect sequence and assert `onTrigger` was NOT called.
  - [ ] Dispatch the sequence while a focused `<input>` is in the DOM and assert it is ignored.

- [ ] **Task 6: Lint + build** (AC 4)
  - [ ] `make lint` — clean.
  - [ ] `make test-frontend` — green.
  - [ ] `cd frontend && npm run build` — production build succeeds, bundle increase < 5 KB gzipped.

## Dev Notes

### Scope & philosophy

- Frontend-only. No backend, no DB, no API, no RBAC concerns. This is pure UI garnish.
- Zero new dependencies. Vue 3 + the existing Vite/Vitest toolchain are enough.
- Do NOT add an i18n entry, README bullet, or in-app docs mention. The point is that someone discovers it.
- Do NOT add telemetry or analytics. It's a joke, not a KPI.

### Why `event.code` instead of `event.key`

`event.code` is layout-independent — `KeyB` is the physical B key regardless of QWERTY/QWERTZ/AZERTY. This matters because the team has German (QWERTZ) keyboards and we want the code to work the same everywhere. Arrow keys are physical and layout-stable too.

### SVG robot sketch

Keep it tiny. Suggested structure:

```xml
<svg viewBox="0 0 40 48" width="40" height="48">
  <!-- antenna -->
  <line x1="20" y1="2" x2="20" y2="8" stroke="currentColor" stroke-width="2"/>
  <circle cx="20" cy="2" r="2" fill="currentColor"/>
  <!-- head -->
  <rect x="10" y="8"  width="20" height="14" rx="2" fill="currentColor"/>
  <circle cx="16" cy="15" r="1.5" fill="white"/>
  <circle cx="24" cy="15" r="1.5" fill="white"/>
  <!-- body -->
  <rect x="8"  y="22" width="24" height="14" rx="1" fill="currentColor"/>
  <!-- legs (animate these) -->
  <rect class="leg leg-l" x="12" y="36" width="5" height="10" fill="currentColor"/>
  <rect class="leg leg-r" x="23" y="36" width="5" height="10" fill="currentColor"/>
</svg>
```

Color with `color: var(--color-primary)` (`#3B7DD8`) so it matches the brand.

### File layout

```
frontend/src/
├── App.vue                                       [MOD — mount listener + conditional sprite]
├── composables/
│   ├── useKonamiCode.ts                          [NEW]
│   └── __tests__/useKonamiCode.spec.ts           [NEW]
└── components/ui/
    └── RobotParade.vue                           [NEW]
```

### Testing standards

- Vitest + `@vue/test-utils` (already in the project).
- No E2E test needed — Playwright coverage for an easter egg is overkill and would document it in the spec file (spoiling the surprise for anyone browsing `e2e/tests/`).

### Out of scope

- Sound effects (would fight with the user's audio context and needs a bundled audio file).
- Multiple robots, leaderboards, or persistence of "you found the easter egg" state.
- Mobile / touch trigger. Konami is a keyboard joke; on touch devices the sequence is simply unreachable, which is fine.

### References

- `CLAUDE.md` — offline-only, brand color `--color-primary: #3B7DD8`.
- `frontend/src/App.vue` — current app shell mount point for global listeners.
