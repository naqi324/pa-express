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

## 2026-09-25 — Add CLI and API key connections to the model engines

**Summary:** Anthropic Claude and OpenAI GPT now each offer a CLI connection
and an API key connection. Claude also keeps AWS Bedrock. A backend catalog
lists the current models and the reasoning efforts each connection takes. The
settings form reads the catalog, and polish from Impeccable tidies its layout.

**Decisions:**
- Claude models: `claude-opus-5-5`, `claude-fable-5-1`, `claude-sonnet-5`,
  `claude-haiku-4-5-20251001` (no effort setting). Efforts low to max.
- GPT models: `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`. The codex CLI adds
  `ultra`; the Responses API adds `none` for sol and luna.
- Defaults: CLI connection, Opus 5.5 and GPT-6 Astra, effort `high`.
- Sources: provider model and effort docs (through Firecrawl), local
  `claude --help` (v2.1.283), and the local codex CLI.
- Impeccable choices were made without asking, as the user asked: boxed
  connection fields with a selected wash and inset ring, API key field on the
  grid, legend reset, no repeated no-effort text.
- Settings fix: blank effort variables select the model default; host lists
  accept CSV or JSON (NoDecode). The CSV bug came from the source app.

**Files:** backend/app/engines/** (new catalog, claude_cli, anthropic_api,
codex_cli, openai_api, provider_call; replaces anthropic_skill and codex),
backend/app/{config,schemas,main,state}.py, backend/tests/**,
src/components/{ConfigureEngineForm,ConnectionView,LlmInspector}.vue,
src/enginePresentation.ts, src/types.ts, src/styles/app.css, tests/e2e/**,
docs/api-contract.md, .env.example, PRODUCT.md, DESIGN.md, pyproject.toml,
uv.lock.

**Checks:** pytest 131 passed; pnpm check clean; e2e 11/11; build OK;
brand check clean (151 files); gitleaks clean. No live model calls ran.

**Next steps:**
- Live-test each connection with real session credentials.
- Fix the 6 advisory detector findings in older `app.css` rules if wanted.
