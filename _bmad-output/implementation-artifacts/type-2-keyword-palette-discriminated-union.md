# Story TYPE-2: KeywordPalette discriminated-union refactor

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `type-2-keyword-palette-discriminated-union`

## Reported

Continuing the `as any` cleanup from TYPE-1 (which dropped 12 of 25
casts). Of the 13 remaining, **5 lived in
`KeywordPalette.vue`** — all of them papering over the fact that
`allCategories` returns a heterogeneous list:

- Keyword categories: `{ name, keywords: string[] }`
- Control category: `{ name, items: { label, type: StepType }[] }`

The original code typed the array as `any` and used `as any` on
every push and every template access.

## Fix

Add a proper discriminated union:

```ts
type KeywordCategory = { name: string; keywords: string[] }
type ControlCategory = { name: string; items: ControlItem[] }
type PaletteCategory = KeywordCategory | ControlCategory
```

TS narrows correctly at every `'keywords' in cat` / `'items' in cat`
template branch — the casts disappear at all five sites:

| Site | Was | Now |
|---|---|---|
| `cats.push({ name: file, keywords: names } as any)` | line 199 | unwrapped, types match |
| `cats.push({ name: lib, keywords: ... } as any)` | line 208 | unwrapped, types match |
| `(cat as any).keywords?.length` (template count) | line 312 | narrowed via `'keywords' in cat` |
| `v-for="kw in (cat as any).keywords"` | line 320 | narrowed |
| `v-for="item in (cat as any).items"` | line 339 | narrowed |

Also collapsed the inline `as StepType` casts on the Control items
(11 of them) — `ControlItem.type: StepType` propagates the narrowing
to the literal strings.

`filteredCategories` was annotated explicitly and its `.filter(Boolean)`
replaced with a real type predicate
`((cat): cat is PaletteCategory => cat !== null)` so the template
no longer needs `cat!` non-null assertions either.

## Verification

- `grep "as any" frontend/src/components/editor/flow/KeywordPalette.vue` →
  0 (only one match remains and it's a comment in the type-block doc).
- `npx vue-tsc --noEmit` — zero new errors anywhere in the app
  (the pre-existing teams/sso errors are untouched).
- `npx vitest run` — 358/358 still green.
- `npx vite build` — clean.
- Cumulative `as any` count across the frontend: 25 → 9 (TYPE-1
  removed 12, TYPE-2 removed 5 more in this file plus 11 inline
  casts on control items).

## Out of scope (TYPE-3+)

Of the 9 remaining `as any` casts:

- `SpecEditor.vue` — `yaml.load(yamlContent) as any` and dynamic
  field assignment. Needs a Zod / io-ts schema to narrow.
- `SettingsView.vue` — passes `password` to `updateUser` which
  doesn't include it in `Partial<User>`. Needs a separate
  `ChangeUserPasswordRequest` type.
- `FlowEditor.vue:649` — control type cast.
- `ProviderConfig.vue` — provider_type union narrowing.
- `ExplorerView.vue:707` — createRun payload.
- `ui.store.spec.ts` — test private property access (acceptable).

Each is a small targeted fix; pick them off in TYPE-3.
