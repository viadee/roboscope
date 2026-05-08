# Story A11Y-1: Baseline accessibility pass on top-level chrome

Status: done

Epic: POLISH — backlog from CLAUDE.md "Known open issues"
Story Key: `a11y-1-baseline-pass`

## Reported

CLAUDE.md "Known open issues":

> a11y gaps

The whole app surface is too big to fix in one story. This pass
targets the **top-level chrome** that *every* logged-in screen
shares, plus the login screen — the highest-leverage areas where
a fix lifts the floor for the entire app:

1. `<html lang="en">` is hardcoded — assistive tech announces every
   language as English.
2. `AppHeader` icon-only buttons (notification toggle, tour
   trigger) carry only `:title=` — fine on hover, invisible to
   screen readers.
3. Decorative emoji glyphs in those buttons aren't marked
   `aria-hidden="true"` — readers double-announce them.
4. Language-switcher buttons don't expose their pressed state via
   `aria-pressed` — only visual `.active` class.
5. No "skip to main content" landmark — keyboard users have to tab
   through every sidebar entry on every page.

## The fix

### A1 — Live `<html lang>` updates from i18n

Watch `useI18n().locale` at app startup; on change set
`document.documentElement.lang = locale`. Initial value mirrors the
locale read from `localStorage`. Done in `main.ts` after
`createApp(...).use(i18n)`.

### A2 — `aria-label` on icon-only buttons in AppHeader

Notification toggle and tour-start buttons get an explicit
`:aria-label` populated from the same i18n key the `:title` already
uses (so screen reader and tooltip stay in sync). Decorative emoji
glyphs get `aria-hidden="true"` so the readable name comes from the
button label, not the bell.

### A3 — `aria-pressed` on language switcher

Each language button gets `:aria-pressed="locale === lang"`. The
existing visual highlight stays, but assistive tech now announces
"German, pressed" / "English, not pressed".

### A4 — Skip-to-main link

`DefaultLayout` gains a visually-hidden-until-focused `<a>` at the
top of the page that targets `#main`. The existing `<main>`
element gets `id="main"`. Keyboard users tabbing in see the link
on first focus and can jump past the sidebar.

## Acceptance Criteria

1. **AC1** — `document.documentElement.lang` reflects the active
   i18n locale on initial load *and* after a switch.
2. **AC2** — Notification + tour buttons have non-empty
   `aria-label` attributes; their emoji spans have
   `aria-hidden="true"`.
3. **AC3** — `aria-pressed="true"` on the active language button,
   `"false"` on the others.
4. **AC4** — Tabbing into the page surfaces a "Skip to main
   content" link that focuses `#main` when activated.
5. **AC5** — Production build clean; existing 358/358 Vitest still
   green.

## Out of scope

- **Color contrast** — needs a designer review against WCAG ratios,
  not a code change.
- **Form-label associations across every form in the app** — bigger
  pass; do per view in follow-up A11Y stories.
- **Live regions** for toast notifications — toasts are visible-only
  ephemeral status; adding `aria-live="polite"` to the toast container
  is right but interacts with the existing TransitionGroup. Defer.
- **Keyboard navigation** within the sidebar's collapsible "More"
  group — already tab-reachable; arrow-key navigation is a future
  refinement.

## Verification

- Frontend test suite: 358/358 green.
- Production build: clean.
- Manual smoke test: tab into the app from a fresh load, see the
  skip link, activate it, focus jumps to main content.
