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

import {
  describeRequestError,
  extractErrorDetail,
  extractErrorStatus,
} from '@/utils/errors'

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

describe('extractErrorStatus', () => {
  it('returns the numeric status when present', () => {
    expect(extractErrorStatus({ response: { status: 401 } })).toBe(401)
    expect(extractErrorStatus({ response: { status: 422 } })).toBe(422)
    expect(extractErrorStatus({ response: { status: 409 } })).toBe(409)
    expect(extractErrorStatus({ response: { status: 500 } })).toBe(500)
  })

  it('returns null when status is not a number', () => {
    expect(extractErrorStatus({ response: { status: '401' } })).toBeNull()
    expect(extractErrorStatus({ response: { status: null } })).toBeNull()
  })

  it('returns null when response is missing', () => {
    expect(extractErrorStatus(new Error('boom'))).toBeNull()
    expect(extractErrorStatus({ random: 'stuff' })).toBeNull()
    expect(extractErrorStatus(null)).toBeNull()
    expect(extractErrorStatus(undefined)).toBeNull()
    expect(extractErrorStatus('plain string')).toBeNull()
  })

  it('returns null when response is not an object', () => {
    expect(extractErrorStatus({ response: 'not-an-object' })).toBeNull()
  })
})

describe('describeRequestError', () => {
  const messages = {
    fallback: 'fallback',
    serverError: (status: number) => `server error ${status}`,
    networkError: 'backend unreachable',
  }

  it('uses serverError for a 500 and NEVER leaks the raw "Internal Server Error" body', () => {
    // The exact regression: Starlette returns a bare-text 500 body.
    // extractErrorDetail would surface it verbatim; describeRequestError must not.
    const e = { response: { status: 500, data: 'Internal Server Error' } }
    expect(describeRequestError(e, messages)).toBe('server error 500')
  })

  it('uses serverError for 502/503 too', () => {
    expect(describeRequestError({ response: { status: 502, data: '' } }, messages)).toBe(
      'server error 502',
    )
    expect(describeRequestError({ response: { status: 503, data: '' } }, messages)).toBe(
      'server error 503',
    )
  })

  it('keeps the server-provided detail for 4xx', () => {
    const e = { response: { status: 403, data: { detail: 'Insufficient permissions' } } }
    expect(describeRequestError(e, messages)).toBe('Insufficient permissions')
  })

  it('falls back for a 4xx with no usable detail', () => {
    expect(describeRequestError({ response: { status: 404, data: {} } }, messages)).toBe(
      'fallback',
    )
  })

  it('uses networkError when there is no response (backend down)', () => {
    // axios connection-refused: an Error with no `.response`.
    const e = Object.assign(new Error('Network Error'), { request: {} })
    expect(describeRequestError(e, messages)).toBe('backend unreachable')
  })

  it('uses networkError for a bare native Error', () => {
    expect(describeRequestError(new Error('boom'), messages)).toBe('backend unreachable')
  })

  it('falls back to plain fallback when 5xx but no serverError supplied', () => {
    expect(
      describeRequestError({ response: { status: 500, data: 'x' } }, { fallback: 'fb' }),
    ).toBe('fb')
  })

  it('falls back to plain fallback when no response and no networkError supplied', () => {
    expect(describeRequestError(new Error('boom'), { fallback: 'fb' })).toBe('fb')
  })
})
