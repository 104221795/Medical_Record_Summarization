# Clinical Safety Guardrails

This application is a de-identified/demo-data Medical Record Summarization PoC. It is not a production clinical system and must not be used for diagnosis, treatment, prescription, discharge decisions, or real-world patient care.

## Implemented Guardrails

| Guardrail | Implementation status |
| --- | --- |
| Generated summaries start as drafts | Implemented. Summary generation returns `draft` status. |
| Human review required | Implemented. Doctor review workflow controls start review, edit, approve, reject, and audit history. |
| Unsupported claims visible | Implemented in Review & Evidence and citation panels. Unsupported/insufficient/conflicting claims remain surfaced. |
| Unsupported claim approval blocking | Implemented. Approval is blocked for clinically actionable unsupported, unchecked, insufficient, or conflicting claims. |
| Citation coverage visible | Implemented in summary safety/evidence quality panels and admin metrics. |
| Wrong-patient citation prevention | Implemented. Citation source scope is validated before approval. |
| Encounter-scope enforcement | Implemented. Encounter-specific citation sources must match the summary encounter. |
| PHI-safe audit metadata | Implemented. Audit metadata is sanitized at write time; raw notes, prompts, generated summaries, evidence excerpts, and free-text review comments are not stored in audit metadata. |
| Audit trail | Implemented for sensitive workflow actions and audit export. |
| Provider failure handling | Implemented as graceful UI/backend error states for unavailable optional providers. |
| Staging authentication | Implemented. Railway/staging protected routes require signed bearer tokens; client role headers are ignored and public admin self-registration is disabled. |
| Request size limit | Implemented through a configurable `Content-Length` limit for staging ingress. Railway/proxy limits should also remain enabled. |
| Proxy evaluation disclaimer | Required in reports and admin/evaluation areas. |

## Safety Cues That Must Remain Visible

- AI summaries are drafts.
- Clinician review is required before approval.
- Unsupported or weakly cited claims need review.
- Evidence/citations must remain inspectable.
- Proxy benchmark results are not clinical safety or effectiveness evidence.

## Remaining Limitations

- No real EHR/FHIR writeback is enabled for production use.
- No credentialed MIMIC-IV-Note or MIMIC-IV-BHC real EHR benchmark is included.
- Medical NLI validation is configurable but not mandatory for all demo flows.
- External LLM use requires governance and explicit environment configuration.
- Gemini staging use is limited to de-identified/demo data configured through server-side secrets.
- Railway staging may not support local Ollama providers; Qwen/Llama are local benchmark/testing providers unless an external model service is attached.
- Dataset and benchmark results are proxy/de-identified/open-benchmark artifacts only.

## Staging/Demo Deployment Position

Deploy this as:

> Railway-ready staging deployment for a de-identified, clinician-review-only Medical Record Summarization PoC.

Do not describe it as clinically validated, clinically safe, real EHR ready, or production medical software.
