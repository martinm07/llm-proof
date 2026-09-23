# 01 — Web package scaffold

Status: done
Blocked by: none

Read `../spec.md` first — this ticket implements spec §2/§5 (package.json, tsconfig) and decision 8.

## Scope

- `web/package.json` (private, ESM, scripts, devDeps only)
- `web/tsconfig.json` (strict, ES2022)
- `web/.gitignore` (node_modules/)
- `npm install` in `web/` (sandbox: approve `registry.npmjs.org`)

## Steps

1. `web/package.json`: `"private": true`, `"type": "module"`, scripts `"test": "vitest run"`, `"typecheck": "tsc --noEmit"`; devDependencies only.
2. `web/tsconfig.json`: strict; target ES2022; module ESNext + moduleResolution bundler; lib ES2022 + DOM (the `File`/`Blob` types); noEmit; include `src/**` and `tests/**`.
3. `npm install` in `web/`.

## Done when

- `cd web && npm run typecheck` and `npm test` run (the suite is empty until ticket 04 — vitest's "no test files" report is expected at this point).

## Comments

- 2026-09-22: devDependencies are `vitest`, `typescript`, and `@types/node`. The spec's "vitest, typescript" list is honored for runtime-relevant deps; `@types/node` is type-only support for the `node:fs` fixture reads required by ticket 04's tests.
- 2026-09-22: Done — `web/package.json`, `web/tsconfig.json`, `web/.gitignore` in place; `npm run typecheck` and `npm test` both run clean.
