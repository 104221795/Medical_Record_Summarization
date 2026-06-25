# Figure Index for Presentation Evidence

This folder contains slide-ready evidence screenshots for the Medical Record Summarization PoC. The figures are ordered for a presentation narrative: product entry, doctor workflow, admin evaluation, then technical proof.

Clinical boundary: these screenshots demonstrate a local demo/staging PoC workflow with clinician-review-only AI drafts. They do not demonstrate production readiness, clinical safety, clinical effectiveness, or real-EHR validation.

| Figure | File | Slide purpose | Suggested caption |
| --- | --- | --- | --- |
| Figure 1 | [Product Landing Page](<Tổng quan hệ thống/Figure_01_Product_Landing_Page.png>) | Introduce the product concept | Role-based medical record summarization workspace with evidence-first positioning. |
| Figure 2 | [Role-Based Login Page](<Tổng quan hệ thống/Figure_02_Role_Based_Login_Page.png>) | Show access entry point | Login screen with role selection for doctor/admin demo access. |
| Figure 3 | [Governed Sign-Up Page](<Tổng quan hệ thống/Figure_03_Governed_Sign_Up_Page.png>) | Show governed account creation | Demo account creation with role control and password policy hints. |
| Figure 4 | [Doctor Workspace Overview](<Doctor Dashboard FLow/Figure_04_Doctor_Workspace_Overview.png>) | Start doctor journey | Doctor workspace guides the user from patient selection to evidence review and final decision. |
| Figure 5 | [De-identified Patient List](<Doctor Dashboard FLow/Figure_05_Deidentified_Patient_List.png>) | Show patient selection | Patient list uses de-identified demo records before summary generation. |
| Figure 6 | [Patient Context and Timeline](<Doctor Dashboard FLow/Figure_06_Patient_Context_and_Timeline.png>) | Show clinical context | Patient context combines profile, encounter timeline, source documents, and previous summaries. |
| Figure 7 | [RAG Evidence-First Generate Summary](<Doctor Dashboard FLow/Figure_07_RAG_Evidence_First_Generate_Summary.png>) | Show generation workflow | Summary generation uses patient-scoped retrieval before provider inference. |
| Figure 8 | [Review and Evidence Quality Gate](<Doctor Dashboard FLow/Figure_08_Review_and_Evidence_Quality_Gate.png>) | Show clinical safety boundary | Evidence quality gate surfaces citation coverage, unsupported claims, conflicts, and retrieval warnings. |
| Figure 9 | [Citation and Claim Review](<Doctor Dashboard FLow/Figure_09_Citation_and_Claim_Review.png>) | Show citation-first review | Review workspace links generated claims to source evidence and unsupported-claim status. |
| Figure 10 | [Citation Tracking Detail](<Doctor Dashboard FLow/Figure_10_Citation_Tracking_Detail.png>) | Show evidence traceability | Citation hover/detail panel shows the source excerpt behind a selected claim. |
| Figure 11 | [Editable Draft and Reject Decision](<Doctor Dashboard FLow/Figure_11_Editable_Draft_and_Reject_Decision.png>) | Show human-in-the-loop decision | Doctor can edit, approve, request changes, or reject the AI-generated draft. |
| Figure 12 | [Patient Summary History Status](<Doctor Dashboard FLow/Figure_12_Patient_Summary_History_Status.png>) | Show summary lifecycle | Patient history tracks provider, review status, generated time, reviewer, and final action. |
| Figure 13 | [Audit History Trace](<Doctor Dashboard FLow/Figure_13_Audit_History_Trace.png>) | Show auditability | Audit history preserves user actions and summary lifecycle events. |
| Figure 14 | [Admin Evaluation Readiness](<Admin FLow/Figure_14_Admin_Evaluation_Readiness.png>) | Show admin readiness view | Admin dashboard summarizes provider readiness, citation readiness, safety readiness, and benchmark governance. |
| Figure 15 | [RAG Best Models Admin Overview](<Admin FLow/Figure_15_RAG_Best_Models_Admin_Overview.png>) | Show benchmark overview | Flow 2.1 compares deterministic, BART, Pegasus, Qwen2.5, and Llama3.2 on 50-record proxy evaluation artifacts. |
| Figure 16 | [Provider ROUGE Leaderboard](<Admin FLow/Figure_16_Provider_ROUGE_Leaderboard.png>) | Show provider ranking | ROUGE leaderboard provides one benchmark view, alongside citation and safety proxy metrics. |
| Figure 17 | [Evidence Grounding Metrics](<Admin FLow/Figure_17_Evidence_Grounding_Metrics.png>) | Show evidence-first evaluation | Evidence grounding metrics compare citation coverage, unsupported claim rate, faithfulness proxy, omission, and timeline completeness. |
| Figure 18 | [RAG vs Raw Context Comparison](<Admin FLow/Figure_18_RAG_vs_Raw_Context_Comparison.png>) | Explain why RAG helps | Flow comparison shows where retrieval-grounded context improves evidence coverage compared with raw/context-only runs. |
| Figure 19 | [Per-Record Failure Analysis](<Admin FLow/Figure_19_Per_Record_Failure_Analysis.png>) | Show diagnostic depth | Per-record analysis supports reviewer inspection of hallucination proxy, omission, retrieval issues, and source limitations. |
| Figure 20 | [RAG Benchmark Artifacts and Run Files](<Admin FLow/Figure_20_RAG_Benchmark_Artifacts_and_Run_Files.png>) | Show reproducibility evidence | Admin artifacts page exposes prediction files, metric CSVs, manifests, run logs, and reports. |
| Figure 21 | [Technical System Running Checklist](<Proofs_of_running_sys/Figure_21_Technical_System_Running_Checklist.png>) | Show technical evidence checklist | Local technical proof checklist covers Docker Compose, health/readiness, tests, frontend build, and Docker build. |
| Figure 22 | [Evidence Package Folder Structure](<Proofs_of_running_sys/Figure_22_Evidence_Package_Folder_Structure.png>) | Show evidence package organization | Evidence package stores logs, endpoint responses, benchmark summaries, build outputs, and reproducibility files. |
| Figure 23 | [Latest Running Test Evidence](<Proofs_of_running_sys/Figure_23_Latest_Running_test.png>) | Show latest technical evidence package | Latest evidence package includes backend tests, frontend build, Docker build, health/readiness responses, provider JSON, and benchmark summary logs. |
