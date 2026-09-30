# Enterprise RAG assistant: implementation plan

## Scenario and first release

Default scenario: an internal employee policy and process knowledge base in
Chinese. Employees ask questions about policies; answers cite the exact document
and section. An administrator uploads, updates, and retires documents. Access
labels determine which documents each user may retrieve.

The scenario, source documents, model provider, budget, and deployment target
are provisional until confirmed by the project owner.

## Delivery stages

1. **Corpus and evaluation set.** Gather 20-50 public or self-authored documents.
   Record source, owner, version, effective date, access label, and format.
   Label 60-100 questions with expected answer and supporting document/section.
   Include exact terms, multi-document questions, outdated versions, no-answer
   cases, and access-denied cases.
2. **Retrieval baseline.** Parse Markdown/PDF/Word, preserve headings and page
   numbers, split by sections, embed chunks, and retrieve from Qdrant. Return
   source references even before answer generation is added.
3. **Answering.** Generate answers only from authorized retrieved passages.
   Attach citations to claims and state when evidence is insufficient. Add a
   model provider adapter and record token usage and latency.
4. **Enterprise workflows.** Add upload status, idempotent indexing, document
   version replacement, deletion, role-based retrieval filters, and a second
   permission check when opening a cited source. Add retries and audit events.
5. **Quality and delivery.** Compare dense retrieval with hybrid search and
   reranking on the same frozen test set. Report Recall@5, answer correctness,
   citation support, no-answer handling, permission violations, p95 latency,
   and cost per question. Package services with Docker Compose and record a
   reproducible demonstration.

## Initial architecture

- FastAPI: HTTP API and authentication boundary.
- PostgreSQL: users, document metadata, versions, ingestion jobs, audit events.
- Qdrant: chunk vectors and searchable access metadata.
- Background worker: parsing, embedding, indexing, and retryable jobs.
- Web UI: document management, question answering, and source viewer.

## First milestone acceptance

- A documented corpus and at least 20 manually checked evaluation questions.
- A running API with health check and a reproducible local setup.
- A document-to-chunk pipeline that retains section and page provenance.
- A search endpoint that returns relevant chunks and source references.
- One baseline retrieval report; all later improvements use the same test set.

No portfolio metric is reported as a production result. All figures must come
from the measured demo corpus and state its size and evaluation method.
