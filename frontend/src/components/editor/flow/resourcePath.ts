/**
 * Epic RES — compute the Robot Framework `Resource` import path for a keyword
 * sourced from another file in the repo.
 *
 * RF resolves `Resource    <path>` relative to the *importing* file's
 * directory. Given the open file and the resource file (both repo-relative,
 * POSIX), return the path from the open file's directory to the resource —
 * e.g. open `tests/login.robot` + resource `resources/common.resource` →
 * `../resources/common.resource`; same directory → just the basename.
 */
export function resourceImportPath(openFile: string, resourceFile: string): string {
  const norm = (p: string) => p.replace(/\\/g, '/').replace(/^\.\//, '')
  const open = norm(openFile)
  const target = norm(resourceFile)
  if (!open) return target // no open-file context → use as-is

  const fromDir = open.split('/').slice(0, -1) // directory segments of the open file
  const toParts = target.split('/')

  // Longest common directory prefix (stop before the resource's own basename).
  let i = 0
  while (i < fromDir.length && i < toParts.length - 1 && fromDir[i] === toParts[i]) {
    i++
  }
  const ups = fromDir.length - i
  const down = toParts.slice(i)
  const segments = [...Array(ups).fill('..'), ...down]
  return segments.join('/') || target
}

/**
 * RF file-based imports. A `.robot` / `.resource` (and the legacy plain-text
 * `.txt` / `.tsv`) file is ALWAYS a `Resource`, never a `Library` — RF has no
 * such thing as `Library    09_database.robot`.
 */
const RESOURCE_FILE_RE = /\.(resource|robot|txt|tsv)$/i

/**
 * Does this import name denote a `Resource` (file) rather than a `Library`?
 *
 * The extension check must cover `.robot` too: a resource keyword living next
 * to the open file resolves to a bare basename (`resourceImportPath` drops the
 * directory for same-dir files), so a `/`-only heuristic would classify it as
 * a third-party library — writing an invalid `Library    09_database.robot`
 * row AND popping the "install 09_database.robot?" pip dialog.
 * Regression seen 2026-07-31.
 */
export function isResourceImport(name: string): boolean {
  const n = name.trim()
  return RESOURCE_FILE_RE.test(n) || n.includes('/')
}
