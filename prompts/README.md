# Prompt Templates

Phase 7 loads active prompt templates from this directory.

Each JSON file includes:

- `template_name`
- `template_version`
- `task_type`
- `prompt_text`
- `system_instruction`
- `output_schema`
- `is_active`

The current MVP uses file-backed prompt templates because the `prompt_templates`
table is not yet implemented in the active SQLAlchemy schema. A future phase can
move these records into a database-backed prompt registry with approval and
change-management workflow.

Gemini-backed persisted summary generation uses these templates only when all
external-provider safeguards are explicitly enabled:

- `RAG_LLM_PROVIDER=gemini`
- `RAG_LLM_EXTERNAL_ENABLED=true`
- `RAG_LLM_ALLOW_PHI_EXTERNAL=true`
- `RAG_GEMINI_API_KEY` is configured

Use that path only with de-identified or formally governed clinical data.
Generated summaries remain drafts and still pass through claim/citation
validation before clinician review.
