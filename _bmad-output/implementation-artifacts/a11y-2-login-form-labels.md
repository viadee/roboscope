# Story A11Y-2: Login form label / autocomplete fixes

Status: done

Epic: POLISH — backlog from CLAUDE.md "Known open issues"
Story Key: `a11y-2-login-form-labels`

## Reported

A11Y-1 covered the top-level chrome (skip link, html lang,
icon-button labels). The login form is the entry point for every
user including assistive-tech users; three issues:

1. `<label>` had no `for=`. The input had no `id`. Without that
   association, screen readers announce the label as a separate
   text node, then the input as "edit text, blank". Same problem
   on the password field.

2. Email input was `type="text"`. Password managers + mobile
   keyboards key off `type="email"` (mobile shows the @-keyboard,
   PMs offer to fill the right credential).

3. No `autocomplete` hints. PMs can't reliably distinguish
   username from password fields without them, so they offer
   wrong suggestions or none at all. Also affects screen-reader
   form-mode workflows.

## Fix

```diff
- <label class="form-label">{{ t('auth.email') }}</label>
- <input v-model="email" type="text" ...>
+ <label for="login-email" class="form-label">{{ t('auth.email') }}</label>
+ <input id="login-email" v-model="email" type="email"
+        autocomplete="username" ...>

- <label class="form-label">{{ t('auth.password') }}</label>
- <input v-model="password" type="password" ...>
+ <label for="login-password" class="form-label">{{ t('auth.password') }}</label>
+ <input id="login-password" v-model="password" type="password"
+        autocomplete="current-password" ...>
```

Audit of the rest of the app:
- `IdpProviderEditView.vue` — already does for/id properly.
- `ChangePasswordModal.vue` — uses *wrapping* labels
  (`<label>...<input/></label>`) which is also valid HTML and
  associates implicitly. No change needed.
- Other forms checked via `grep "form-label"` — all already correct.

## Ripple — unit-test selectors

`LoginView.spec.ts` had 4 places using `wrapper.find('input[type="text"]')`
to get the email input. Updated to `input[type="email"]`. The tests
now match the post-fix DOM and stay green (358/358).

## Verification

- `npx vitest run` 358/358 green.
- `npx vite build` clean.

## Out of scope

- **Color contrast review** — A11Y-3 candidate; needs WCAG ratios.
- **`aria-describedby` for hint texts** in modals — current
  implicit association via wrapping labels is acceptable.
- **Form-label audit on every view** — done piecemeal; LoginView
  was the highest-leverage as the entry point.
