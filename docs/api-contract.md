# API contract — Prior Auth Express

All routes are under `/api`. Response bodies use the pydantic models in
`backend/app/schemas.py`. The frontend types in `src/types.ts` must mirror them.
The backend runs on port 8004 (`uv run uvicorn backend.app.main:app --port 8004`).
The dev frontend runs on port 5175.

Case state is session-scoped. The server keys it on the `pa_express_session`
cookie (HttpOnly, `SameSite=lax` by default). All `/api/*` responses carry
`Cache-Control: no-store`.

## Errors

Every application error uses one envelope (`ApiErrorBody`):

```json
{"error": {"status": 404, "code": "POLICY_NOT_FOUND", "message": "...",
           "retry_guidance": "...", "correlation_id": "uuid"}}
```

| Status | Code | Raised by |
|---|---|---|
| 400 | `ANTHROPIC_KEY_REQUIRED` | PUT engine-config/anthropic-claude with `api_key` and no stored or supplied key |
| 400 | `BEDROCK_KEYS_REQUIRED` | PUT engine-config/anthropic-claude with `access_keys` and no stored or supplied key pair |
| 400 | `OPENAI_KEY_REQUIRED` | PUT engine-config/openai-gpt with `api_key` and no stored or supplied key |
| 404 | `SCENARIO_NOT_FOUND` | POST /requests with an unknown `scenario_id` |
| 404 | `REQUEST_NOT_FOUND` | any `/requests/{id}` route with an unknown id |
| 404 | `EVALUATION_NOT_FOUND` | GET evaluation with an unknown `eval_id` |
| 404 | `ENGINE_NOT_FOUND` | an engine id that is valid in the schema but not registered |
| 404 | `DETERMINATION_NOT_READY` | GET determination before an evaluation completes |
| 404 | `LLM_INSPECTION_NOT_READY` | GET llm-inspection before an evaluation completes |
| 404 | `LETTER_NOT_READY` | GET letter before a completed evaluation and a disposition |
| 404 | `POLICY_NOT_FOUND` | GET /policies/{id} with an id that has no local file and no citing scenario |
| 404 | `COVERAGE_NOT_FOUND` | GET /coverage/{id} with an id that has no local file |
| 409 | `ACTION_NOT_ALLOWED` | POST actions before a completed determination |
| 409 | `ALREADY_DISPOSED` | POST actions when a disposition is already recorded |
| 409 | `NO_LETTER_FOR_REFERRAL` | GET letter for a `referred_md` case |
| 409 | `LETTER_ALREADY_FINALIZED` | POST letter after the letter is `ready` |
| 422 | `PEND_ITEMS_REQUIRED` | pend action with an empty `requested_items` |
| 422 | `MD_SUMMARY_REQUIRED` | refer_md action with an empty `note` |
| 422 | `MODEL_NOT_SUPPORTED` | PUT engine-config with a model the chosen auth method does not offer |
| 422 | `EFFORT_NOT_SUPPORTED` | PUT engine-config with an effort the chosen model and auth method do not take |

Request bodies that fail pydantic validation return FastAPI's standard 422
`{"detail": [...]}` body. Examples: an engine id outside `EngineId`, a model id
outside the engine's catalog, or a field that the input does not define.
`ClaudeConfigInput` and `OpenAiGptConfigInput` forbid extra fields, so a
`command` field is rejected. CLI commands are server configuration. Unknown non-API paths
fall through to the SPA handler; unknown `/api/*` paths return 404
`{"detail": "API route not found."}`.

## Routes

| Method | Path | Request body | Response | Notes |
|---|---|---|---|---|
| GET | `/api/health` | — | `HealthStatus` | `version` comes from `VERSION`; `capabilities` is `RuntimeCapabilities` |
| GET | `/api/scenarios` | — | `ScenarioSummary[]` | from `backend/app/data/scenarios.py`; `policy_label` is e.g. `Medicare NCD 150.3` |
| GET | `/api/engines` | — | `EngineInfo[]` | cheap availability probe (flags, CLI on PATH, stored key, boto3 import); never calls a provider; carries the effective `auth_method`, `model_id`, and `effort` |
| GET | `/api/requests` | — | `PARequestSummary[]` | expedited first, then nearest `sla_due_at` |
| POST | `/api/requests` | `{scenario_id, urgency?: Urgency, engine?: EngineId}` | `PARequest` (201) | intake creates the case and starts its evaluation at once; audit `request_created` |
| POST | `/api/requests/seed` | `{engine?: EngineId}` | `PARequestSummary[]` (201) | loads each scenario once per session (idempotent); `ncd-20-32-tavr` arrives expedited |
| GET | `/api/requests/{id}` | — | `PARequest` | `latest_eval_id` names the newest evaluation |
| POST | `/api/requests/{id}/evaluations` | `EvaluationRequest` | `EvaluationStatus` (202) | re-run; resets disposition, letter, validity window, requested items, and `notified_at` |
| GET | `/api/requests/{id}/evaluations/{eval_id}` | — | `EvaluationStatus` | poll until `completed` or `failed`; carries `determination` and a fallback notice in `error` |
| GET | `/api/requests/{id}/determination` | — | `Determination` | latest completed determination |
| GET | `/api/requests/{id}/llm-inspection` | — | `LlmInspection` | prompt, provider payload, raw response, parsed JSON, errors; `traces=[]` for the rules engine |
| POST | `/api/requests/{id}/actions` | `HumanActionRequest` | `PARequest` | approve → `approved` (+ validity window, 90 days by default); pend → `pended` (+ `requested_items`); refer_md → `referred_md` (+ `md_summary`) |
| GET | `/api/requests/{id}/letter` | optional `tz` query (IANA zone) | `Letter` | composed on first read from the determination and the current status; dated in `tz`, or UTC when `tz` is missing or unknown |
| POST | `/api/requests/{id}/letter` | `LetterUpdateRequest` | `Letter` | `save` keeps a draft; `mark_ready` finalizes and sets `notified_at` |
| GET | `/api/policies/{policy_id}` | — | `PolicyDocument` | local-only policy lookup (see below) |
| GET | `/api/coverage/{policy_id}` | — | `CoverageCheck` | local NCD or LCD file summary (see below) |
| GET | `/api/engine-config` | — | `EngineConfig[]` | one entry per engine; `auth_methods` and `models` list the connections, models, and efforts the form offers |
| PUT | `/api/engine-config/anthropic-claude` | `ClaudeConfigInput` | `EngineConfig` | session override of auth method, model, effort, Bedrock region and credentials, and secrets; secrets are write-only and come back only as a masked hint |
| DELETE | `/api/engine-config/anthropic-claude` | — | `EngineConfig` | reset to process defaults |
| PUT | `/api/engine-config/openai-gpt` | `OpenAiGptConfigInput` | `EngineConfig` | session override of auth method, model, effort, and API key; the key is write-only |
| DELETE | `/api/engine-config/openai-gpt` | — | `EngineConfig` | reset to process defaults |
| GET | `/` and `/{path}` | — | built SPA | serves `dist/`; 404 when no frontend build exists |

## Engines

Engine ids: `offline | anthropic_claude | openai_gpt`. The default is `offline`, shown to
reviewers as "Rules engine".

| Engine | Auth methods | Defaults |
|---|---|---|
| `offline` | none | deterministic lenient rubric over the scenario's authored facts; sleeps `mock_processing_seconds` to show the analyzing state |
| `anthropic_claude` | `cli` (Claude Code CLI), `api_key` (Anthropic API key), `bedrock` (AWS Bedrock) | `cli`, model `claude-opus-5-5`, effort `high` |
| `openai_gpt` | `cli` (Codex CLI), `api_key` (OpenAI API key) | `cli`, model `gpt-6-astra`, effort `high` |

`EngineConfig` carries `auth_methods` (`AuthMethodOption[]`: `id`, `label`,
`summary`, `ready`, `note`) and `models` (`ModelOption[]`: `id`, `label`,
`summary`, and `methods`). Each `ModelMethodSupport` in `methods` gives the
`provider_model_id` sent for one auth method, the `efforts` it takes, and the
provider's `default_effort`. The catalog lives in `backend/app/engines/catalog.py`.
The routes validate every saved model and effort against it. A missing effort
selects the model's default.

Models and efforts (checked 2026-09-25 against the provider docs and the local
`claude` and `codex` CLIs):

| Model | Auth methods | Efforts | Default |
|---|---|---|---|
| `claude-opus-5-5` | all three | `low` `medium` `high` `xhigh` `max` | `medium` |
| `claude-fable-5-1` | all three | `low` `medium` `high` `xhigh` `max` | `high` |
| `claude-sonnet-5` | all three | `low` `medium` `high` `xhigh` `max` | `high` |
| `claude-haiku-4-5-20251001` | all three | none (no effort setting) | — |
| `gpt-6-astra` | `cli` | `low` `medium` `high` `xhigh` `max` `ultra` | `medium` |
| `gpt-6-astra` | `api_key` | `low` `medium` `high` `xhigh` `max` | `medium` |
| `gpt-6-sol` | `cli` | `low` `medium` `high` `xhigh` `max` `ultra` | `medium` |
| `gpt-6-sol` | `api_key` | `none` `low` `medium` `high` `xhigh` `max` | `medium` |
| `gpt-6-luna` | `cli` | `low` `medium` `high` `xhigh` `max` | `medium` |
| `gpt-6-luna` | `api_key` | `none` `low` `medium` `high` `xhigh` `max` | `medium` |

Bedrock sends the regional inference profile: `us.anthropic.<model id>`, and
`us.anthropic.claude-haiku-4-5-20251001-v1:0` for Claude Haiku 4.5.

Provider calls:

- Claude Code CLI: `claude -p --safe-mode --output-format json
  --no-session-persistence --strict-mcp-config --tools "" --model <id>
  [--effort <effort>]`. The prompt goes on stdin. The CLI uses its own sign-in
  and inherits the server's environment.
- Anthropic API key: `POST https://api.anthropic.com/v1/messages` with
  `anthropic-version: 2023-06-01`. A model with an effort setting sends
  `thinking: {type: "adaptive"}` and `output_config.effort`.
- AWS Bedrock: Converse in `bedrock_region`. The adaptive thinking and effort
  fields go in `additionalModelRequestFields`. `bedrock_credentials` is
  `profile` (an empty `aws_profile` uses the standard boto3 credential chain) or
  `access_keys` (session keys, with an optional session token).
- Codex CLI: `codex exec --skip-git-repo-check --ephemeral --sandbox read-only
  --output-schema <file> --output-last-message <file> -m <id>
  [-c model_reasoning_effort="<effort>"] -`. The prompt goes on stdin.
- OpenAI API key: `POST https://api.openai.com/v1/responses` with
  `reasoning.effort`.

Settings use the `PA_EXPRESS_` environment prefix (see `.env.example`).

## Evaluation semantics

- An unavailable or failing engine never fails the case. The registry runs the
  rules engine instead. `EvaluationStatus.error` carries
  `"<label> unavailable — fell back to the rules engine: <reason>"`, and
  `determination.attribution.engine` names the engine that actually ran.
- The recommendation is only `approve | pend`. No engine denies.
- The lenient rubric approves when every required criterion is `MET`. Any
  `NOT_MET` or `INSUFFICIENT` criterion pends, and its text is listed in `gaps`.
  A criterion with no authored fact is `INSUFFICIENT` with confidence 0. A case
  with no clinical documents pends before criteria are evaluated.
- Model-backed engines get the vendored prior-auth-review skill and rubric in the
  prompt. The server rejects output that omits a criterion, cites a quote that is
  not verbatim in the named document, recommends against the rubric, or marks a
  criterion `MET` without evidence. A rejection triggers the rules-engine fallback.
- `criteria_met` is a display string such as `"4/4 required criteria met"`.
- Traces are in memory and bounded. They never include API keys, AWS keys, or
  CLI sign-in tokens. Provider error text is redacted before it is recorded.
  `LlmTrace` records the `auth_method` and `effort` of each call.
- Engines never set a disposition. Only a human action moves
  `determination_status` from `in_review`.
- The server records the reviewer actor for disposition audit events. It does
  not trust client-supplied actor text. A finalized letter is immutable.

Status models:

- `processing_status`: `queued → analyzing → completed | failed`.
- `determination_status`: `in_review → approved | pended | referred_md`.
- SLA clock (CMS-0057-F): standard 7 days, expedited 72 hours from `created_at`.

## Policies and coverage (local only)

A policy is a Medicare NCD or LCD. `PolicySourceType = "ncd" | "lcd"`. No policy
route makes a network call. The data comes from the top level of
`data/cms-coverage/` (`ncd-*.json`, `lcd-*.json`) and from the scenarios.

- Accepted ids. NCD: `150.3`, `150-3`, `NCD 150.3`, `ncd-150-3`. LCD: `L12345`,
  `l12345`, `LCD L12345`, `lcd-l12345`, `LCD 12345`. The canonical ids are
  `150.3` and `L12345`.
- The directory is scanned on each lookup. A new `lcd-*.json` file works without
  a code change or a restart. The app works when no LCD file exists. Unreadable
  or malformed files are skipped. The id comes from `ncd_id` / `lcd_id` in the
  file, or from the file name.
- LCD files may carry `contractor` as a string, an object with `name`, or a list.
  The version is read from `document_version`, `version`, `lcd_version`, or
  `ncd_version`, in that order. `effective_date` falls back to
  `revision_effective_date`, then `original_effective_date`.
- `GET /api/policies/{id}` returns a `PolicyDocument`: `policy_id`,
  `source_type`, `code` (`"NCD 150.3"` / `"LCD L12345"`), `title`, `version`,
  `contractor`, `effective_date`, `last_updated`, `benefit_category`,
  `coverage_model`, `summary`, `source_url`, `api_url`, `local_file_available`,
  `criteria[]` (`PolicyCriterion`), `non_covered[]`, `notes[]`, `sections[]`
  (`PolicySection` from the file's `full_text`), and `review_criteria[]`
  (`ReviewCriteriaSet`: the criteria each scenario that cites this policy uses).
  When no file exists but a scenario cites the policy, the document is built from
  the scenario's `policy` with `local_file_available: false`.
- `GET /api/coverage/{id}` returns a `CoverageCheck`: `policy_id`,
  `source_type`, `version`, `title`, `covered`, `summary`, `source_url`, plus
  `ncd_id` / `ncd_version` for an NCD or `lcd_id` / `contractor` for an LCD.
- The rules engine attaches a `CoverageCheck` when the cited NCD or LCD has a
  local file, and `null` otherwise.

## Attribution and letters

`PolicyRef` (on `PARequest.policy`): `source_type`, `code`, `title`, `version`,
`ncd_id`, `ncd_version`, `lcd_id`, `contractor`, `source_url`.

`Attribution` (on `Determination.attribution`): `engine`, `engine_label`,
`model_id`, `policy_source_type`, `policy_code`, `policy_title`,
`policy_version`, `ncd_id`, `ncd_version`, `lcd_id`, `contractor`,
`evaluated_at`.

The provider letter prints one policy line from the attribution:

- NCD: `Coverage Policy: Medicare NCD 150.3 (Version 2)`
- LCD: `Coverage Policy: Medicare LCD L12345 — <title> (<contractor>)`
- Otherwise: `Coverage Policy: <policy_code or policy_title or "Not specified">`

## Changes from the source contract

- Removed the vendor clinical-guideline engine. `EngineId` drops that id.
- `EngineConfig.auth_style` is replaced by `auth_methods` and `models`. Each
  model engine offers a CLI and an API key connection, and Anthropic Claude also
  offers AWS Bedrock. `EngineInfo` and `LlmTrace` add `auth_method` and `effort`.
- Removed `GET/POST/DELETE /api/credentials` and the `CredentialInput`,
  `CredentialStatus`, and `EngineConfig.credential` shapes. No engine uses
  runtime OAuth credentials now.
- Removed `GET /api/guidelines/{code}` and the `GuidelinePack` family. It used a
  remote guideline service. `GET /api/policies/{policy_id}` replaces it and
  returns a local `PolicyDocument`.
- `GET /api/coverage/{ncd_id}` is now `GET /api/coverage/{policy_id}`. It accepts
  NCD and LCD ids in several forms. `CoverageCheck` adds `policy_id`,
  `source_type`, `version`, `lcd_id`, and `contractor`. `ncd_id` and
  `ncd_version` are now optional.
- `PolicySourceType` is now `"ncd" | "lcd"`. It no longer includes the vendor
  guideline type.
- `PolicyRef.edition` is renamed to `version`. `PolicyRef` adds `lcd_id` and
  `contractor`, and drops the companion and remote guideline references. The NCD
  `code` is now the display code `"NCD 150.3"`.
- `Attribution.guideline_code`, `guideline_title`, and `guideline_edition` are
  renamed to `policy_code`, `policy_title`, and `policy_version`. The product and
  guideline-id fields are removed. `policy_source_type`, `lcd_id`, and
  `contractor` are new.
- `RuntimeCapabilities` drops the vendor-engine and runtime-credential flags.
  Only `anthropic_claude_enabled` and `openai_gpt_enabled` remain.
- `LlmTrace.provider` is now `"anthropic" | "bedrock" | "openai"`.
- `PA_EXPRESS_AWS_PROFILE` defaults to empty, which means the standard AWS
  credential chain. The source defaulted to a named profile.
- Ports: backend 8004, frontend 5175. The FastAPI title is "Prior Auth Express".
- The demo caseload has five scenarios. Each has a local policy file.

  | Scenario id | Policy | Contractor | Plan type | Expected path |
  |---|---|---|---|---|
  | `ncd-150-3-dxa` | NCD 150.3 v2 | — | `medicare_advantage` | approve |
  | `ncd-20-32-tavr` | NCD 20.32 v2 | — | `medicare_advantage` | approve |
  | `lcd-l34220-lumbar-mri` | LCD L34220 v40 | Noridian (JE/JF), Oregon member | `commercial` | approve |
  | `lcd-l33405-psg` | LCD L33405 v25 | First Coast (JN), Florida member | `medicaid` | pend (no Epworth score) |
  | `lcd-l39911-tka` | LCD L39911 v10 | WPS (J5/J8), Michigan member | `medicare_advantage` | approve |

  New scenarios need only a scenario entry and an optional `ncd-*.json` or
  `lcd-*.json` file.
