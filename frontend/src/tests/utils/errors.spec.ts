/**
 * `extractErrorDetail` — shared error-message unwrapper.
 *
 * Pins the contract every `catch` block in the codebase relies on:
 * extract the FastAPI-shaped `{ detail: "..." }` from an axios error
 * when present, fall back through the axios message, native Error
 * message, and finally the localised fallback. Always returns a
 * non-empty string; never throws.
 */
import { describe, it, expect } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'

import { extractErrorDetail } from '@/utils/errors'

function _axiosErrorWith(data: unknown, message = 'Request failed'): AxiosError {
  const err = new AxiosError(message)
  err.response = {
    data,
    status: 400,
    statusText: 'Bad Request',
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as AxiosError['response']
  return err
}

describe('extractErrorDetail', () => {
  describe('axios error — FastAPI {detail: "..."} shape', () => {
    it('returns the string detail when present', () => {
      const e = _axiosErrorWith({ detail: 'Repository not found' })
      expect(extractErrorDetail(e, 'fallback')).toBe('Repository not found')
    })

    it('returns the structured detail.message when detail is an object', () => {
      const e = _axiosErrorWith({
        detail: { message: 'Validation failed', code: 'INVALID' },
      })
      expect(extractErrorDetail(e, 'fallback')).toBe('Validation failed')
    })

    it('falls through past empty-string detail to the next layer', () => {
      // Empty detail is not "human-readable" — fall back to the
      // axios message so the user sees something useful.
      const e = _axiosErrorWith({ detail: '' }, 'Request failed with status code 500')
      expect(extractErrorDetail(e, 'fallback')).toBe(
        'Request failed with status code 500',
      )
    })

    it('handles a structured detail without a message field', () => {
      const e = _axiosErrorWith(
        { detail: { code: 'XYZ' } },
        'Request failed with status code 500',
      )
      // No usable detail.message → axios message → returned.
      expect(extractErrorDetail(e, 'fallback')).toBe(
        'Request failed with status code 500',
      )
    })
  })

  describe('axios error — plain-string body', () => {
    it('returns the body when response.data is a string', () => {
      const e = _axiosErrorWith('Internal Server Error')
      expect(extractErrorDetail(e, 'fallback')).toBe('Internal Server Error')
    })

    it('skips empty string body and falls through to message', () => {
      const e = _axiosErrorWith('', 'Network Error')
      expect(extractErrorDetail(e, 'fallback')).toBe('Network Error')
    })
  })

  describe('axios error — no response (network failure)', () => {
    it('uses the axios message', () => {
      const e = new AxiosError('Network Error')
      expect(extractErrorDetail(e, 'fallback')).toBe('Network Error')
    })
  })

  describe('non-axios errors', () => {
    it('returns the message of a native Error', () => {
      expect(extractErrorDetail(new Error('Boom'), 'fallback')).toBe('Boom')
    })

    it('returns the message of a TypeError subclass', () => {
      expect(extractErrorDetail(new TypeError('bad arg'), 'fallback')).toBe('bad arg')
    })

    it('returns fallback for a string thrown bare', () => {
      // `throw "oops"` is bad practice but happens; can't extract
      // a usable message from a primitive.
      expect(extractErrorDetail('oops', 'fallback')).toBe('fallback')
    })

    it('returns fallback for null/undefined', () => {
      expect(extractErrorDetail(null, 'fallback')).toBe('fallback')
      expect(extractErrorDetail(undefined, 'fallback')).toBe('fallback')
    })

    it('returns fallback for plain object without recognised shape', () => {
      expect(extractErrorDetail({ random: 'stuff' }, 'fallback')).toBe('fallback')
    })
  })

  describe('always returns a non-empty string', () => {
    it('returns the fallback when an Error has no message', () => {
      const e = new Error('')
      expect(extractErrorDetail(e, 'fallback')).toBe('fallback')
    })
  })
})
