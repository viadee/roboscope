import { describe, it, expect } from 'vitest'
import { resourceImportPath, isResourceImport } from '@/components/editor/flow/resourcePath'

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

describe('isResourceImport', () => {
  it('classifies a same-directory .robot resource as Resource, not Library', () => {
    // The 2026-07-31 regression: `resourceImportPath` returns a bare basename
    // for a sibling file, so the old `/`-or-`.resource` heuristic saw
    // "09_database.robot" as a third-party library name.
    expect(isResourceImport('09_database.robot')).toBe(true)
  })

  it('classifies every RF resource-file extension, case-insensitively', () => {
    expect(isResourceImport('common.resource')).toBe(true)
    expect(isResourceImport('Common.Resource')).toBe(true)
    expect(isResourceImport('legacy.txt')).toBe(true)
    expect(isResourceImport('legacy.tsv')).toBe(true)
    expect(isResourceImport('SHARED.ROBOT')).toBe(true)
  })

  it('still classifies path-bearing imports as Resource', () => {
    expect(isResourceImport('../resources/common.resource')).toBe(true)
    expect(isResourceImport('shared/kw.resource')).toBe(true)
  })

  it('leaves real library names as Library', () => {
    expect(isResourceImport('Browser')).toBe(false)
    expect(isResourceImport('SeleniumLibrary')).toBe(false)
    expect(isResourceImport('DatabaseLibrary')).toBe(false)
    // A dotted module path is a Python library import, not a file.
    expect(isResourceImport('my.package.Library')).toBe(false)
  })

  it('trims surrounding whitespace before classifying', () => {
    expect(isResourceImport('  09_database.robot  ')).toBe(true)
    expect(isResourceImport('  Browser  ')).toBe(false)
  })
})

/**
 * FlowEditor.vue::addLibrary derives BOTH the settings key and the
 * install-prompt suppression from `isResourceImport`. Mirror that derivation
 * so a future change to the classifier can't silently reopen the bug where
 * adding a keyword from a local `.robot` resource asked the user to
 * pip-install it.
 */
describe('addLibrary import-kind derivation (FlowEditor)', () => {
  const RF_BUNDLED = new Set([
    'collections', 'string', 'datetime', 'operatingsystem', 'process', 'xml',
    'dialogs', 'screenshot', 'telnet', 'remote',
  ])

  /** Mirror of the two decisions FlowEditor.vue::addLibrary makes. */
  function classify(name: string): { key: string; installPrompt: boolean } {
    const isResource = isResourceImport(name)
    return {
      key: isResource ? 'Resource' : 'Library',
      installPrompt: !(isResource || RF_BUNDLED.has(name.toLowerCase())),
    }
  }

  it('writes a Resource row and never prompts to install a local .robot file', () => {
    expect(classify('09_database.robot')).toEqual({ key: 'Resource', installPrompt: false })
  })

  it('writes a Resource row and never prompts for a relative resource path', () => {
    expect(classify('../resources/common.resource'))
      .toEqual({ key: 'Resource', installPrompt: false })
  })

  it('still prompts for a genuine third-party library', () => {
    expect(classify('Browser')).toEqual({ key: 'Library', installPrompt: true })
  })

  it('writes a Library row but skips the prompt for RF-bundled libs', () => {
    expect(classify('Collections')).toEqual({ key: 'Library', installPrompt: false })
  })
})
