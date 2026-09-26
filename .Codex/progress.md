# Progress

## 2026-09-25 — Port the reviewer app as Prior Auth Express

**Summary:** Rebuilt the source reviewer app as a standalone, unbranded
"Prior Auth Express". FastAPI backend (uv), Vue 3 + TypeScript frontend,
new gridded clinical record design, Playwright flows, brand guard.

**Decisions:**
- Persona: UM nurse working a daily queue (Operate mode).
- Scenarios 3–5 rebased on public CMS LCDs L34220, L33405, L39911.
- Offline engine shown as "Rules engine"; engine id stays `offline`.
- Letters are dated in the reviewer's time zone (`tz` query, UTC fallback).
- Logic qualifiers stay under each criterion, not as group header rows.
- 2px inset bottom underline is the selection mark; side stripes stay banned.

**Files:** backend/app/**, src/**, tests/e2e/**, scripts/check_brand.py,
README.md, AGENTS.md, docs/api-contract.md, PRODUCT.md, DESIGN.md,
.impeccable/{decision,surfaces,design.json}.

**Checks:** pytest 107 passed; pnpm check clean; e2e 9/9; build OK;
brand check clean; design detector 0 findings; gitleaks clean.

**Next steps:**
- Try the Claude and GPT engines with real session credentials.
- Consider the Impeccable v4.4.0 update (`npx impeccable update`).
