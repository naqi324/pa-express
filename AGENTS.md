# Prior Auth Express

Prior authorization review app for UM nurses. Vue 3 + TypeScript + Vite
frontend, FastAPI backend (uv), pnpm, Oxlint, Playwright.

## Commands

- `pnpm dev` — backend on `127.0.0.1:8004`, frontend on `127.0.0.1:5175`.
- `pnpm check` — lint and typecheck. Run before every commit.
- `pnpm build` — typecheck, then production build.
- `uv run pytest` — backend tests in `backend/tests/`.
- `pnpm test:e2e` — Playwright flows in `tests/e2e/`. Starts both servers if they are not running.
- `pnpm brand:check` — scan files, `dist/`, and commit messages for retired vendor names.
- `pnpm verify` — every check above, in order.

## Rules

- Use pnpm for JavaScript and uv for Python. Do not add npm or yarn lockfiles.
- Frontend source lives in `src/`. Backend source lives in `backend/app/`.
- This app has no vendor branding. Present it only as "Prior Auth Express". `pnpm brand:check` must pass before every commit and push, including commit messages.
- Oxlint runs the vendored anti-slop rules in `tools/oxlint/anti-slop/`. Fix findings in the code. Do not suppress rules or lower their severity.
- To update anti-slop, use the `install-anti-slop` update procedure. Keep the provenance in `tools/oxlint/anti-slop/UPSTREAM.md`.
- Automation recommends approve or pend only. Never add an automated deny path. Possible denials go to an MD.
- A letter is immutable after it is marked ready.
- UI: no modals, dialogs, or side panels. Use inline disclosures. Follow the tokens and shared classes in `src/styles/`. Keep motion between 120 and 200 ms and honor `prefers-reduced-motion`.
- Never commit real patient data (PHI). Use synthetic data for fixtures and demos.
- Never commit secrets. Runtime credentials stay in server memory for one session.

## Session Context

- 2026-09-25: Engine connections, model catalog, and settings polish pushed.
- State: Claude runs through the claude CLI, an Anthropic API key, or Bedrock.
  GPT runs through the codex CLI or an OpenAI API key. The catalog in
  `backend/app/engines/catalog.py` holds the models and efforts.
- Checks: pytest 131, e2e 11/11, lint/typecheck clean, brand clean.
- Decisions: defaults are CLI, `claude-opus-5-5` and `gpt-6-astra`, effort
  `high`. A blank effort selects the model's default. Host lists accept CSV or
  JSON. The form rejects a `command` field; CLI commands are server config.
- Detector: 6 advisory findings in older `app.css` rules (mask `#000`, small
  radii). They are out of scope for this change.
- Next: live-test each connection with real session credentials. The CLI
  connection inherits the server's shell environment (AWS profile, Bedrock
  flag). Check the catalog again when providers ship new models.
