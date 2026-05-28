# 05 — Survey Plan: Problem Validation and Workflow Feedback

**Document type:** Survey Plan  
**Purpose:** Validate user needs, trust requirements and workflow assumptions for the Medical Record Summarization MVP  

---

## 1. Survey Objective

The survey aims to validate whether healthcare-related users experience difficulty reviewing long or fragmented patient records, and whether citation-grounded AI summaries with human review would be useful and trustworthy.

The survey is not intended to provide clinical validation. It is used for product discovery and problem validation.

---

## 2. Target Respondents

| Respondent group | Target count | Purpose |
|---|---:|---|
| Medical/healthcare students | 5–10 | Domain-aware feedback |
| Clinicians/nurses if available | 3–5 | Stronger workflow relevance |
| Health IT/product reviewers | 3–5 | System and workflow feedback |
| Non-domain users | 5–10 | Usability/readability feedback only |

---

## 3. Research Assumptions to Validate

| Assumption | Survey validation |
|---|---|
| A1: Long patient records create review burden | Ask about time and difficulty of reviewing records |
| A2: Users need evidence before trusting AI summary | Ask about citation usefulness |
| A3: AI output should remain draft | Ask about clinician approval expectation |
| A4: Safety warnings improve trust | Ask about unsupported/weak claim flags |
| A5: Summary should be role-aware | Ask about who should approve/view/edit |

---

## 4. Survey Structure

### Section A — Respondent background

1. What best describes your background?
   - Doctor / clinician
   - Nurse
   - Medical/healthcare student
   - Health IT / product
   - AI/engineering
   - Other

2. How familiar are you with electronic health records or patient records?
   - Not familiar
   - Slightly familiar
   - Moderately familiar
   - Very familiar
   - Professional user

### Section B — Problem validation

Use 1–5 Likert scale: 1 = Strongly disagree, 5 = Strongly agree.

| No. | Statement |
|---:|---|
| 1 | Reviewing long patient records can be time-consuming. |
| 2 | Important patient information may be missed when records are spread across many notes/results. |
| 3 | A structured patient summary would help speed up record review. |
| 4 | It is difficult to trust a summary if the source is not shown. |
| 5 | A summary should show uncertainty or missing information instead of guessing. |

### Section C — Trust and safety

| No. | Statement |
|---:|---|
| 6 | I would trust an AI-generated summary more if each important claim had a citation. |
| 7 | Claims without supporting evidence should be clearly flagged. |
| 8 | Conflicting information should be shown instead of automatically resolved by AI. |
| 9 | AI-generated medical summaries should require clinician review before being used officially. |
| 10 | The system should keep audit logs of who generated, edited or approved a summary. |

### Section D — Workflow and UI

| No. | Statement |
|---:|---|
| 11 | A side-by-side view of summary and source evidence would be useful. |
| 12 | A safety panel showing unsupported claims would improve review confidence. |
| 13 | Role-based access is important in a medical summary system. |
| 14 | A doctor should be able to edit AI-generated summaries before approving them. |
| 15 | An admin dashboard showing citation coverage and rejection rate would be useful. |

### Section E — Open-ended questions

1. What information should always appear in a patient summary?
2. What would make you distrust an AI-generated clinical summary?
3. Which action should require human approval?
4. Which safety warning would be most useful?
5. What would make this system more useful for real workflow?

---

## 5. Survey Output Analysis Plan

### Quantitative analysis

For Likert-scale questions:

- Calculate average score by question.
- Group questions by theme: burden, trust, safety, workflow.
- Identify top 3 strongest needs.
- Identify lowest-scoring or controversial assumptions.

### Qualitative analysis

For open-ended questions:

- Code answers into themes: missing data, citation, hallucination, workflow, trust, UI clarity.
- Extract representative quotes.
- Translate insights into PRD changes.

---

## 6. How Survey Results Inform PRD

| Survey insight | PRD impact |
|---|---|
| Users report record review burden | Strengthen problem statement |
| Users require citation | Prioritize citation panel |
| Users worry about hallucination | Strengthen safety requirements |
| Users want doctor approval | Keep HITL as core flow |
| Users value dashboard | Keep monitoring/admin module |
| Users find role-based access important | Add role-based UI matrix |

---

## 7. Minimum Survey Success Criteria

| Criterion | Target |
|---|---:|
| Respondents collected | 10+ for MVP discovery |
| Average score for summary usefulness | >= 4/5 desirable |
| Average score for citation usefulness | >= 4/5 desirable |
| Average score for clinician approval need | >= 4/5 desirable |
| At least 5 useful open-ended comments | Yes |

---

## 8. Reporting Format

Survey findings should be summarized in the final report as:

```text
Survey results indicate that respondents perceive patient record review as time-consuming and consider citation visibility important for trust. The majority of respondents prefer AI-generated medical summaries to remain draft until reviewed by a clinician. These findings support the MVP design decisions: citation-based summary, safety panel, and doctor-in-the-loop review workflow.
```

---

## 9. Limitations

- Survey sample may not include enough practicing clinicians.
- Results validate user perception, not clinical safety.
- Non-domain respondents should only be used for usability feedback.
- Survey should not replace human evaluation of generated summaries.
