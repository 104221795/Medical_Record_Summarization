# 04 — Research Background and Research Gaps

**Document type:** Research Appendix  
**Purpose:** Provide academic grounding for the PRD and User Flow  

---

## 1. Research Motivation

Medical records contain a mixture of structured information, such as diagnoses, medication orders and lab results, and unstructured narratives, such as discharge notes, progress notes and radiology reports. Clinicians often need to reconstruct patient context from multiple sources under time pressure. This creates a strong motivation for summarization tools that can reduce information burden.

However, medical summarization is not a standard text summarization problem. In healthcare, an incorrect, unsupported or misleading summary can affect clinical reasoning. Therefore, a useful product must address not only generation quality, but also evidence traceability, missing information, hallucination risk, human review and auditability.

---

## 2. Literature Review Themes

### 2.1 Clinical text summarization need

Recent literature highlights information overload in EHRs and the increasing interest in automatic clinical text summarization. MIMIC-IV-Note provides de-identified discharge summaries and radiology reports, while MIMIC-IV-Ext-BHC was created specifically to support Brief Hospital Course summarization from clinical notes.

### 2.2 LLMs and summarization potential

LLMs and encoder-decoder models have shown strong summarization capability. However, medical summarization requires higher factual reliability than general summarization because outputs may be used by healthcare professionals.

### 2.3 Evaluation challenge

Automatic metrics such as ROUGE and BERTScore are useful for comparing generated summaries against references, but they do not fully measure factual correctness, missing information, or clinical risk. Human evaluation remains important but is costly and difficult to scale.

### 2.4 Hallucination and unsupported claims

LLM-generated medical summaries can introduce unsupported details, omit important facts or overstate certainty. These problems are especially risky when the system does not expose the source of generated claims.

### 2.5 Integration and governance

Healthcare AI tools require governance beyond model output: role-based access, audit logs, privacy controls, evidence traceability, and safe workflow integration. FHIR and SMART on FHIR are relevant standards for future integration.

---

## 3. Research Gaps

| Gap ID | Gap | Why it matters | MVP response |
|---|---|---|---|
| RG-01 | Lack of claim-level evidence traceability | Clinicians need to verify where a claim came from | Citation-based summary with evidence panel |
| RG-02 | Overreliance on automatic metrics | ROUGE/BERTScore do not guarantee factual safety | Human evaluation + safety/citation metrics |
| RG-03 | Hallucination in high-stakes context | Unsupported claims may mislead users | Unsupported claim detection and safety panel |
| RG-04 | Missing workflow integration | Model-only demos do not show how clinicians review outputs | Doctor UI + HITL review workflow |
| RG-05 | Weak auditability | Clinical systems need traceability of actions | Audit logs for generation, citation, review |
| RG-06 | Unclear role boundaries | Different users require different permissions | Role-based UI and backend checks |
| RG-07 | Restricted access to real EHR notes | True benchmarks often require credentialed access | Multi-layer evaluation and pending benchmark status |
| RG-08 | External LLM privacy risk | Clinical data may not be safe to send externally | Gemini disabled by default; de-identified/demo data policy |

---

## 4. Research Questions

### RQ1 — Workflow usefulness

How can a citation-grounded summary workflow reduce the effort of reviewing patient context while preserving clinician control?

### RQ2 — Evidence traceability

Can claim-level citation improve user trust and support safer review of AI-generated medical summaries?

### RQ3 — Safety and hallucination mitigation

Can unsupported claim detection and safety panels make hallucination risk visible before clinician approval?

### RQ4 — Model comparison

How do baseline models such as BART/Pegasus compare with a real LLM provider such as Gemini under available proxy medical summarization datasets?

### RQ5 — Evaluation design under data constraints

How can a medical summarization MVP be evaluated honestly when real EHR note-level datasets require credentialed access?

---

## 5. Proposed Research Contribution

This project contributes a **production-style MVP design** rather than only a model benchmark. Its contribution is the integration of:

```text
summarization model providers
+ citation grounding
+ hallucination mitigation
+ doctor-in-the-loop review
+ auditability
+ role-based UI
+ multi-layer evaluation
```

This design bridges the gap between clinical summarization research and practical clinical workflow prototyping.

---

## 6. Dataset Strategy

| Dataset | Role | Limitation |
|---|---|---|
| Mock/de-identified demo data | Functional validation | Cannot claim model quality |
| MIMIC-III demo DB | Structured EHR validation | No clinical note rows for note summarization |
| OPI/D2N/CHQ | Proxy medical text summarization evaluation | Not full real EHR discharge-note benchmark |
| MIMIC-IV-Ext-BHC | Preferred real benchmark | Pending credentialed access |
| MIMIC-IV-Note | Fallback real benchmark | Requires section extraction and access |

---

## 7. Survey Research Plan Link

The survey is designed to validate three assumptions:

1. Long/fragmented records create review burden.
2. Users need citations to trust AI summaries.
3. Users want doctor approval before generated summaries become official.

Survey results will inform persona refinement, feature priority and UI trust requirements.

---

## 8. Research Limitations

- The MVP does not perform clinical diagnosis or treatment recommendation.
- Functional validation using mock data cannot prove clinical model performance.
- BART/Pegasus proxy evaluation cannot replace real EHR note-level benchmark.
- Human evaluation may be limited by evaluator expertise and sample size.
- Gemini evaluation on restricted clinical data requires careful data governance.

---

## 9. Future Research Directions

1. Run real EHR note-level benchmark using MIMIC-IV-Ext-BHC.
2. Conduct clinician-led human evaluation.
3. Improve factuality and citation verification methods.
4. Compare local LLMs vs external LLM APIs under privacy constraints.
5. Study the effect of citation UI on trust and review efficiency.
6. Evaluate doctor edit distance as a product quality signal.

---


## References

- Aali, A. et al. (2025) *MIMIC-IV-Ext-BHC: Labeled Clinical Notes Dataset for Hospital Course Summarization*. PhysioNet. Available at: https://physionet.org/content/labelled-notes-hospital-course/
- Bednarczyk, L. et al. (2025) *Scientific Evidence for Clinical Text Summarization Using Large Language Models*. Journal of Medical Internet Research. Available at: https://www.jmir.org/2025/1/e68998/
- Croxford, E. et al. (2025) *Evaluating clinical AI summaries with large language models*. npj Digital Medicine. Available at: https://www.nature.com/articles/s41746-025-02005-2
- FDA (2026) *Clinical Decision Support Software: Guidance for Industry and Food and Drug Administration Staff*. Available at: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
- HL7 (2024) *SMART App Launch Implementation Guide*. Available at: https://build.fhir.org/ig/HL7/smart-app-launch/
- Johnson, A. et al. (2024) *MIMIC-IV-Note: Deidentified free-text clinical notes*. PhysioNet. Available at: https://physionet.org/content/mimic-iv-note/
- NIST (2024) *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. Available at: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
- Tang, L. et al. (2023) *Evaluating large language models on medical evidence summarization*. npj Digital Medicine. Available at: https://pmc.ncbi.nlm.nih.gov/articles/PMC10449915/
- WHO (2021) *Ethics and governance of artificial intelligence for health*. Available at: https://www.who.int/publications/i/item/9789240029200
