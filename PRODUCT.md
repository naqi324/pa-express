# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vue 3 + TypeScript on Vite (pnpm, Oxlint with the vendored anti-slop rules). FastAPI backend on Python 3.12 (uv) with session-scoped in-memory state. Hand-built components; no third-party component library.

## Users

The primary user is a utilization management (UM) nurse reviewer at a health plan. They work a daily queue of prior authorization requests at a desktop workstation, for most of the shift. For each case they read the submitted clinical documentation, check it against the coverage policy criterion by criterion, and then approve, request more information, or refer to a Medical Director. They are clinically trained, fast, and accountable for every decision they sign. Every request carries a regulatory clock.

## Product Purpose

Prior Auth Express is a payer-side prior authorization demo app. It moves a request from intake to evaluation, recommendation, a human decision, a provider letter, and an audit record. A reasoning engine evaluates the clinical documentation against a public Medicare coverage policy. It returns a criterion-level recommendation with verbatim evidence quotes. The nurse decides.

Success means the nurse reaches a defensible decision quickly. They can see which criteria are met, which are not, and the exact words in the record that prove each one. They trust the result because they can inspect how the engine produced it.

## Positioning

Automation recommends **approve** or **pend** only. It never denies. Every recommendation traces each criterion to a verbatim quote from the submitted record and to a public CMS policy (NCD or LCD). The engine is swappable: a deterministic offline rubric, Claude, or GPT. An inspector shows the sanitized inputs and outputs, so the nurse can audit how the recommendation was produced.

## Operating Context

- Desktop web, used for long sessions. A worklist sorted by urgency and SLA time.
- The regulatory clock follows CMS-0057-F: 7 calendar days for standard requests, 72 hours for expedited requests.
- Case documents: clinical notes, imaging reports, study results, and orders, all synthetic.
- Policy sources: public CMS National Coverage Determinations and Local Coverage Determinations, stored locally under `data/cms-coverage/`.
- Screens: Worklist, New request, Case workspace (submission, criteria and evidence, decision and audit), Letter and audit, and Engine settings.

## Capabilities and Constraints

- Evaluation starts automatically at intake. The UI polls status until it completes.
- Two status tracks. Processing status: queued, analyzing, completed, failed. Determination status: in review, approved, pended, referred to Medical Director.
- Adverse outcomes route to "request information" or "refer to Medical Director". The product has no automated deny path.
- Pend letters cite the specific unmet or insufficient criteria. A letter can be edited until it is marked ready; after that it is immutable.
- Every determination records the engine, the model id when applicable, the policy basis, a timestamp, and evidence citations. A full audit trail records each action.
- Engines: Offline (default, deterministic, the test baseline), Anthropic Claude through AWS Bedrock, and OpenAI GPT through the local `codex` CLI. An unavailable engine falls back to Offline and shows a visible notice.
- Engine credentials are session-scoped and held in server memory only. The UI shows only a masked hint.
- An engine can recommend approval only when evidence supports every criterion.
- Terminology: "request", "case", "criterion", "evidence", "recommendation", "determination", "pend", "request information", "refer to Medical Director", "SLA".

## Brand Commitments

The product name is "Prior Auth Express". It stands alone and is not associated with any other vendor, guideline publisher, or product family. It uses no third-party clinical guideline content, brand assets, fonts, or component libraries. Policy content comes only from public CMS coverage documents.

## Evidence on Hand

- Five synthetic demo scenarios: two built on public NCDs (NCD 150.3 bone mass measurement, NCD 20.32 TAVR) and three built on public Medicare LCDs (knee MRI, attended polysomnography, total knee arthroplasty).
- Public CMS policy data in `data/cms-coverage/`.
- The vendored Anthropic prior-auth-review skill in `vendor/anthropic-prior-auth-review/`, used as the LLM engine prompt.
- There are no real customers, testimonials, performance benchmarks, or production deployments. Do not invent any. All patient data is synthetic.

## Product Principles

1. The nurse decides. The engine recommends, and the interface never presents a recommendation as a decision.
2. Show the evidence, not a score. Every criterion leads to the exact words in the record.
3. The clock is always visible. SLA time is part of every case view.
4. Never deny. Adverse paths are "request information" and "refer to Medical Director", and the interface makes this safe path easy.
5. Explain the machine. Every recommendation is open to inspection.

## Accessibility & Inclusion

Target WCAG 2.2 AA. Reviewers work long shifts. Keyboard operation of the whole queue-to-decision path, visible focus, and status that never depends on color alone are requirements.
