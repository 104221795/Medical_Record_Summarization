# Evaluation Report Template

Use this template for real evaluation runs only. Do not fill metrics with synthetic or assumed values.

## 1. Evaluation Overview

- Evaluation date:
- Evaluator:
- Environment:
- Evaluation objective:
- Scope:

## 2. Dataset Description

- Dataset name/version:
- Source system:
- De-identification status:
- Number of patients:
- Number of encounters:
- Number of clinical documents:
- Included document types:
- Excluded data:
- Known dataset limitations:

## 3. Model / Provider Version

- Summarization mode: deterministic / LLM-assisted
- Model/provider:
- Model version:
- Runtime configuration:
- External services used:
- Notes:

## 4. Prompt Version

- Prompt/template ID:
- Prompt version:
- Guardrail version:
- Citation policy version:
- Change summary since previous evaluation:

## 5. Summary Quality Metrics

- Total summaries evaluated:
- Draft count:
- Under review count:
- Edited count:
- Approved count:
- Rejected count:
- Approval rate:
- Rejection rate:
- Average edit distance:
- Top rejection reasons:

## 6. Citation Metrics

- Average citation coverage:
- Supported claims with citations:
- Claims missing citations:
- Weak citation count:
- Citation source types:
- Citation quality notes:

## 7. Hallucination / Safety Metrics

- Unsupported claim count:
- Conflicting claim count:
- Critical unsupported claim proxy count:
- Wrong-patient retrieval count:
- Safety gate status:
- Safety gate failures or warnings:
- Clinician safety notes:

## 8. HITL Review Metrics

- Total reviews:
- Approvals:
- Rejections:
- Edits:
- Average time to review:
- Reviewer activity summary:
- Review workflow issues:

## 9. Audit Coverage

- Sensitive actions checked:
- Audit log coverage:
- Missing audit events:
- Access control findings:
- Notes on PHI minimization:

## 10. Known Limitations

- Data limitations:
- Model/prompt limitations:
- Citation limitations:
- UI/workflow limitations:
- Operational limitations:

## 11. MVP Readiness Decision

- Decision: pass / warning / fail
- Required fixes before production-like pilot:
- Accepted residual risks:
- Sign-off owner:
- Sign-off date:

## 12. Recommended Next Actions

- Immediate actions:
- Next evaluation run:
- Longer-term improvements:
