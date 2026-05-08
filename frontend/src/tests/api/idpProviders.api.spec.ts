/**
 * SSO-1 regression guard.
 *
 * `sso.store.ts` imported `listPublicSsoProviders` from
 * `@/api/idpProviders.api` for months, but the function was never
 * defined in the source module. The `sso.store.spec.ts` tests use
 * `vi.mock('@/api/idpProviders.api', () => ({ listPublicSsoProviders:
 * vi.fn() }))`, which silently replaces the entire module — so the
 * test passed against a fabricated function while production crashed
 * at runtime with `TypeError: listPublicSsoProviders is not a
 * function`. The store's `try/catch` swallowed it and every login
 * page silently fell back to "local login only" mode, hiding
 * configured SSO providers from every user.
 *
 * This file deliberately does NOT mock the API module. It imports
 * `listPublicSsoProviders` for real and asserts:
 *   - the symbol exists,
 *   - it's a callable function.
 *
 * If the function is renamed, deleted, or accidentally re-mocked
 * away by some future test-config drift, this assertion catches it
 * before the bug ships again.
 *
 * The function's *behaviour* (correct URL, response shape) is
 * validated indirectly by the existing sso.store tests; we don't
 * actually call the network here.
 */

import { describe, it, expect } from 'vitest'

describe('idpProviders.api — SSO-1 regression guard', () => {
  it('exports a callable `listPublicSsoProviders`', async () => {
    // Dynamic import so a stray `vi.mock(...)` in a sibling spec
    // can't replace the module before this assertion runs.
    const mod = await import('@/api/idpProviders.api')
    expect(mod.listPublicSsoProviders).toBeDefined()
    expect(typeof mod.listPublicSsoProviders).toBe('function')
  })

  it('exports a callable `listIdps` (admin counterpart)', async () => {
    // Sister assertion — the file's main public-Endpoint helper. Same
    // guard pattern: catches accidental deletion / rename.
    const mod = await import('@/api/idpProviders.api')
    expect(mod.listIdps).toBeDefined()
    expect(typeof mod.listIdps).toBe('function')
  })
})
