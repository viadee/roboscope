# Epic AIX — AI Provider & Output Enhancements — PRD + Design

**Status**: Planning → ready for implementation
**Date**: 2026-06-18
**PM/Architect**: John / Winston
**Parent**: [presentation-feedback-epics.md](./presentation-feedback-epics.md)
**Epic**: AIX

## What already exists

- `call_llm` (`ai/llm_client.py`) routes every non-`anthropic` provider through `_call_openai_compatible`, honoring `provider.api_base_url`. So an OpenAI-compatible **LiteLLM gateway** already works today via a generic provider with `api_base_url` set — it just isn't offered as a labeled choice.
- The analysis already threads a `language` param (request → `dispatch_task(run_analyze, job.id, language)` → prompt directive). Verbosity mirrors this exactly.

## AIX-1 — LiteLLM provider type

**JTBD**: *"As an admin, I want to point RoboScope at our LiteLLM gateway so I can use any model we proxy and centralize keys/spend."*

- FE: add `{ value: 'litellm', label: 'LiteLLM (Gateway)' }` to `ProviderConfig.vue` provider types; freeform model list; empty default model; a hint that **the base URL is the gateway endpoint and is required**.
- BE: `litellm` already resolves to `_call_openai_compatible`. Add a guard: if `provider_type == 'litellm'` and no `api_base_url`, the call raises a clear error (no silent fallback to api.openai.com).
- i18n: `ai.litellmHint` in EN/DE/FR/ES/ZH.

## AIX-2 — Analysis verbosity control

**JTBD**: *"As a user, I want a concise summary or a deep dive on demand, so the analysis fits the moment."*

- `concise | standard | detailed` → a prompt directive (appended to `SYSTEM_PROMPT_ANALYZE`, like the language directive) and an effective `max_tokens` cap (concise ≈ 600, standard = provider default, detailed = provider default). Default `standard`.
- Plumbing mirrors `language`: `AnalyzeRequest.verbosity` → `dispatch_task(run_analyze, job.id, language, verbosity)` → `verbosity_directive(verbosity)` composed into the system prompt. Frontend sends the chosen verbosity (a small select near the Analyze button; default standard).
- i18n: `reportDetail.analysis.verbosity.*` in all 5 locales.

## Functional requirements

- **FR-1** LiteLLM is selectable; configuring it with a base URL + model produces working analyses; without a base URL it fails with a clear error (not a wrong-endpoint call).
- **FR-2** Verbosity is selectable per analysis (default standard); `concise` yields a materially shorter prompt directive + lower max_tokens; code/keywords/patches stay verbatim; composes with the language directive.
- **FR-3** Non-breaking: existing providers + analyses behave exactly as before when verbosity is unset (treated as standard).

## Acceptance

1. `verbosity_directive` unit-pinned (concise/standard/detailed/None); analyze dispatch passes verbosity through.
2. LiteLLM provider type appears in the form and round-trips; backend guard unit-pinned (litellm + no base_url → error).
3. i18n complete in EN/DE/FR/ES/ZH (Gate 8 stays green).
4. Real-UI E2E: the analysis card shows a verbosity selector.

## Handoff
→ Implementation (Amelia) → review → E2E.
