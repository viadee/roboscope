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
