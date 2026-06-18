import { describe, it, expect } from 'vitest'
import { resourceImportPath } from '@/components/editor/flow/resourcePath'

describe('resourceImportPath', () => {
  it('goes up to a sibling directory', () => {
    expect(resourceImportPath('tests/login.robot', 'resources/common.resource'))
      .toBe('../resources/common.resource')
  })

  it('same directory → bare basename', () => {
    expect(resourceImportPath('tests/login.robot', 'tests/common.resource'))
      .toBe('common.resource')
  })

  it('both at repo root', () => {
    expect(resourceImportPath('login.robot', 'common.resource')).toBe('common.resource')
  })

  it('nested open file, divergent resource path', () => {
    expect(resourceImportPath('a/b/test.robot', 'a/c/d/foo.resource'))
      .toBe('../c/d/foo.resource')
  })

  it('resource deeper under the open file directory', () => {
    expect(resourceImportPath('tests/suite.robot', 'tests/shared/kw.resource'))
      .toBe('shared/kw.resource')
  })

  it('no open-file context → resource path as-is', () => {
    expect(resourceImportPath('', 'resources/common.resource'))
      .toBe('resources/common.resource')
  })

  it('tolerates Windows-style separators and ./ prefix', () => {
    expect(resourceImportPath('tests\\login.robot', './resources/common.resource'))
      .toBe('../resources/common.resource')
  })
})
