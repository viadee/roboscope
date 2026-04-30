/**
 * `extractErrorDetail` — shared error-message unwrapper.
 *
 * Pins the contract every migrated `catch` block in the codebase
 * relies on: walk the structural `e.response.data.detail` path,
 * fall back to the supplied string when nothing usable was found.
 * Mirrors the old `e?.response?.data?.detail || fallback` idiom
 * exactly — and deliberately does NOT extract Error.message /
 * AxiosError.message, because the old idiom didn't either.
 */
import { describe, it, expect } from 'vitest'

import { extractErrorDetail } from '@/utils/errors'

describe('extractErrorDetail', () => {
  describe('FastAPI {detail: "..."} shape', () => {
    it('returns the string detail when present', () => {
      const e = { response: { data: { detail: 'Repository not found' } } }
      expect(extractErrorDetail(e, 'fallback')).toBe('Repository not found')
    })

    it('returns the structured detail.message when detail is an object', () => {
      const e = {
        response: { data: { detail: { message: 'Validation failed', code: 'INVALID' } } },
      }
      expect(extractErrorDetail(e, 'fallback')).toBe('Validation failed')
    })

    it('falls through past empty-string detail to fallback', () => {
      const e = { response: { data: { detail: '' } } }
      expect(extractErrorDetail(e, 'fallback')).toBe('fallback')
    })

    it('handles a structured detail without a message field', () => {
      const e = { response: { data: { detail: { code: 'XYZ' } } } }
      expect(extractErrorDetail(e, 'fallback')).toBe('fallback')
    })
  })

  describe('plain-string body', () => {
    it('returns the body when response.data is a string', () => {
      const e = { response: { data: 'Internal Server Error' } }
      expect(extractErrorDetail(e, 'fallback')).toBe('Internal Server Error')
    })

    it('falls back when body is empty string', () => {
      const e = { response: { data: '' } }
      expect(extractErrorDetail(e, 'fallback')).toBe('fallback')
    })
  })

  describe('inputs that don\'t match the response.data path', () => {
    it('returns fallback for native Error (no response field)', () => {
      // Matches the OLD `e?.response?.data?.detail || fallback`
      // behavior — the call sites uniformly preferred their
      // localised fallback over the raw `Error.message`.
      expect(extractErrorDetail(new Error('Network Error'), 'fallback')).toBe(
        'fallback',
      )
    })

    it('returns fallback for plain string thrown bare', () => {
      expect(extractErrorDetail('oops', 'fallback')).toBe('fallback')
    })

    it('returns fallback for null/undefined', () => {
      expect(extractErrorDetail(null, 'fallback')).toBe('fallback')
      expect(extractErrorDetail(undefined, 'fallback')).toBe('fallback')
    })

    it('returns fallback for object without response field', () => {
      expect(extractErrorDetail({ random: 'stuff' }, 'fallback')).toBe('fallback')
    })

    it('returns fallback when response is not an object', () => {
      expect(extractErrorDetail({ response: 'not-an-object' }, 'fallback')).toBe(
        'fallback',
      )
    })

    it('returns fallback when response.data is not an object or string', () => {
      expect(extractErrorDetail({ response: { data: 42 } }, 'fallback')).toBe(
        'fallback',
      )
    })
  })

  describe('test-mock parity (plain objects, no AxiosError prototype)', () => {
    it('handles the existing codebase test-mock shape', () => {
      // Tests across the codebase mock errors with this exact
      // shape: `{ response: { data: { detail: "..." } } }` — a
      // plain object, not an AxiosError. The helper must work
      // structurally so those tests continue to pass.
      const e = { response: { data: { detail: 'Ungueltige Anmeldedaten' } } }
      expect(extractErrorDetail(e, 'fallback')).toBe('Ungueltige Anmeldedaten')
    })
  })
})
