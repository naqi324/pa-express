# Prior Auth Express

A payer-side prior authorization review app for utilization management (UM)
nurses. A reviewer works a daily queue. Each case is checked against public CMS
coverage policy, and the reviewer approves, requests information, or refers the
case to a Medical Director (MD).

All demo data is synthetic. The app holds no protected health information (PHI).

## Quick start

```bash
pnpm install
uv sync
pnpm dev
```

`pnpm dev` starts the FastAPI backend on `http://127.0.0.1:8004` and the Vite
frontend on `http://127.0.0.1:5175`. Open the frontend URL. The rules engine
needs no setup.

## Stack

- Vue 3, TypeScript, and Vite for the frontend
- FastAPI and Pydantic for the backend, managed with `uv`
- Oxlint with the vendored anti-slop rules
- Playwright for end-to-end reviewer flows
- pnpm for packages

## Commands

| Command | Purpose |
|---|---|
| `pnpm dev` | Run the backend and the frontend together. |
| `pnpm dev:backend` | Run FastAPI with reload on `127.0.0.1:8004`. |
| `pnpm dev:frontend` | Run Vite on `127.0.0.1:5175`. |
| `pnpm check` | Run Oxlint and `vue-tsc`. |
| `pnpm build` | Type-check, then build the frontend to `dist/`. |
| `uv run pytest` | Run the backend tests. |
| `pnpm test:e2e` | Run the Playwright reviewer flows. |
| `pnpm brand:check` | Fail if a retired vendor name appears in files or commit messages. |
| `pnpm verify` | Run the version check, brand check, lint, pytest, build, and E2E. |

## How the app works

Automation recommends **approve** or **pend** only. The app has no automated
deny path. A case that may need a denial goes to an MD. Pend letters name the
specific unmet criteria. Each determination records the engine, the model ID
when one applies, the policy basis, a timestamp, and the evidence citations.

Screens:

1. **Worklist**: one status per case, the recommendation, urgency, and the time
   left before the deadline.
2. **New request**: choose one of five synthetic scenarios and submit.
   Evaluation starts at once.
3. **Case workspace**: the submission, the criteria and evidence, and the
   decision and audit tabs.
4. **Letter**: an editable provider letter. It locks when it is marked ready.
5. **Engine**: choose the reasoning engine and set its model and effort.

Scenarios:

| Scenario | Policy | Expected result |
|---|---|---|
| DXA bone density | Medicare NCD 150.3 | Approve, 5/5 criteria |
| TAVR | Medicare NCD 20.32 | Approve, 9/9 criteria |
| Lumbar spine MRI | Medicare LCD L34220 | Approve, 6/6 criteria |
| In-lab sleep study | Medicare LCD L33405 | Pend, 6/7 criteria |
| Total knee replacement | Medicare LCD L39911 | Approve, 6/6 criteria |

## Reasoning engines

| Engine | How it works | Local setup |
|---|---|---|
| **Rules engine** | Fixed coverage rules over the scenario facts. No model or network call. | None. |
| **Anthropic Claude** | Claude on Bedrock with the vendored prior-auth-review skill prompt and strict JSON checks. | An AWS profile, the standard AWS credential chain, or session access keys. |
| **OpenAI GPT** | The signed-in local `codex` CLI with the same skill prompt and JSON checks. | `codex` on `PATH`, signed in outside the app. |

The rules engine is the default and the baseline for automated tests. Its engine
id is `offline`. If Claude or GPT is not available, the app falls back to the
rules engine and shows a notice.

The **Engine calls** section on the decision tab shows the sanitized inputs and
outputs of each engine call. It never records AWS keys or Codex tokens.

Backend settings use the `PA_EXPRESS_` environment prefix. See
`backend/app/config.py` for the full list.

## Repository layout

```text
backend/app/                   FastAPI app, config, schemas, state, engines, services
backend/app/data/              Synthetic scenarios and their criteria facts
backend/tests/                 Backend tests
data/cms-coverage/             Public CMS NCD and LCD coverage data
docs/                          API contract
scripts/                       Version and brand checks
src/                           Vue app, components, store, typed API client
tests/e2e/                     Playwright reviewer flows
tools/oxlint/anti-slop/        Vendored Oxlint rules
vendor/anthropic-prior-auth-review/  Vendored prior-auth-review skill
```

## Credentials and secrets

Do not commit secrets. Bedrock access keys that you enter in the app stay in
server memory for the current browser session only.

Run `gitleaks detect` before you push.
