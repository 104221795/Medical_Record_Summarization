# Phase 7C Gemini Provider Integration

Gemini is integrated into the persisted summary workflow through:

```http
POST /api/v1/patients/{patient_id}/summaries/generate
```

The external provider is disabled by default. Deterministic generation remains
the default for local development, CI, and demos.

## Required Environment Flags

Gemini can only run when all of these are configured:

```text
RAG_LLM_PROVIDER=gemini
RAG_LLM_EXTERNAL_ENABLED=true
RAG_LLM_ALLOW_PHI_EXTERNAL=true
RAG_GEMINI_API_KEY=<google-ai-studio-api-key>
```

Optional:

```text
RAG_GEMINI_MODEL=gemini-2.5-flash-lite
```

## Safety Warning

Use Gemini only with de-identified data or with clinical data covered by an
approved governance, security, and data-processing agreement. Do not send PHI to
an external provider by default.

Gemini output must remain a draft until doctor approval. It must pass through
the same persisted claim, citation, safety, audit, and HITL review workflow as
deterministic summaries.

## Validation Rules

- Output must be valid JSON matching the prompt schema.
- Unsupported or uncited clinical claims are downgraded and surfaced for review.
- A claim cannot be persisted as `supported` unless its citation ID maps back to
  the current patient's evidence pack.
- Summary status remains `draft`.
- ModelRun stores provider, model, prompt version, latency, context hash, and
  output hash.
- Invalid Gemini output fails safely and does not create a summary.

