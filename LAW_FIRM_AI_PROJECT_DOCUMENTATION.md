# Law Firm AI

## 1. Project Overview
Law Firm AI is a legal intelligence platform for lawyers, law firms, and legal professionals.  
It has two primary capabilities:

1. Legal Chat Assistant (ChatGPT for Law)  
   A domain-aware legal assistant that answers legal queries using grounded legal sources.
2. Legal Notice Generation  
   A workflow-driven system that drafts legal notices using user facts, legal context, and retrieved references.

---

## 2. Vision and Objectives

### 2.1 Vision
Build a reliable, citation-grounded legal AI system that improves legal research speed, drafting quality, and overall legal workflow productivity.

### 2.2 Primary Objectives
- Reduce legal research time for professionals.
- Generate legally relevant, structured, and editable legal notice drafts.
- Reduce hallucinations through retrieval-grounded generation.
- Support multiple legal domains, including travel, insurance, medicine, estate, banking, and related categories.

---

## 3. Current Data and Processing Pipeline

### 3.1 Legal Notice/Judgement PDF Collection
- Source domains include travel, insurance, medicine, estate, banking, and others.
- Download script: `judgement_agent.py`
- Output folder: `judgements/`

`judgement_agent.py` responsibilities:
- Uses domain/topic-based retrieval strategy for legal notice/judgement documents.
- Fetches/crawls PDF links from configured sources.
- Downloads PDFs in batch mode.
- Stores the downloaded files in `judgements/` for downstream conversion.

### 3.2 Legal Notice/Judgement PDF to JSON Conversion
- Conversion scripts are part of the existing project pipeline (for example, `pdf2json/run_pipeline.py` and related modules).
- Processing environment: rented VM with RTX 4090.
- Throughput: approximately 30-40 seconds per PDF.
- Current volume: approximately 3,500 legal notice PDFs.
- Estimated processing time at current throughput: approximately 35 hours.

Conversion pipeline responsibilities:
- Read each PDF from `judgements/`.
- Extract text page by page.
- Normalize and structure content into JSON chunks.
- Attach metadata needed for indexing and retrieval.
- Write JSON output for downstream RAG/training use.

### 3.3 Indian Central Acts PDF Collection
- Source: India Code website.
- Download script: `browser_agent_download_acts` (or equivalent browse-agent script in this repository).
- Output folder: `laws_browse/`
- Current volume mentioned: approximately 845 Acts PDFs.

`browser_agent_download_acts` / browse-agent responsibilities:
- Open India Code Acts listing pages.
- Iterate through paginated Central Acts listings.
- Open each `View...` link and follow the PDF link.
- Download and store each Acts PDF in `laws_browse/`.

### 3.4 Acts PDF to JSON Conversion (Planned)
- This pipeline is pending implementation/finalization.
- Planned output should match the JSON structure used for legal notices/judgements for unified indexing.

Planned conversion responsibilities:
- Read PDFs from `laws_browse/`.
- Convert Acts into structured JSON chunks.
- Attach metadata (for example: act title, year, page, source path).
- Produce schema-compatible JSON for shared retrieval/indexing.

---

## 4. System Architecture

Law Firm AI is organized into five layers:

1. UI Layer (User Interface)
2. Backend/API Layer
3. AI Orchestration Layer
4. Data Layer
5. LLM Layer

### 4.1 UI Layer
Primary interactions:
- Submit legal queries.
- Upload case facts/documents.
- Generate legal notices.
- Review citations/sources.
- Export drafts for review.

### 4.2 Backend/API Layer
Core responsibilities:
- Authentication and authorization.
- Session management.
- Request validation and rate limiting.
- Routing requests to orchestration services.
- Audit logging and observability.

### 4.3 AI Orchestration Layer
This layer controls the end-to-end AI flow and includes three core modules:

1. Domain Classifier  
   Identifies legal domain and user intent (research vs drafting).
2. RAG Engine  
   Retrieves relevant legal context and prepares grounded input for generation.
3. LLM Engine  
   Generates final answers and draft notices using retrieved context.

### 4.4 Data Layer
The data layer includes:
- Raw document storage (PDFs).
- Structured JSON corpus.
- Operational database records.
- Vector database for semantic retrieval.

---

## 5. Component Roles: RAG, LLM, and Vector DB

### 5.1 RAG Engine
RAG (Retrieval Augmented Generation) is required to:
- Retrieve relevant legal material (Acts, sections, precedents) from the corpus.
- Build grounded context before LLM generation.
- Improve output reliability and reduce unsupported answers.
- Enable source-linked responses and notice drafting.

RAG flow:
1. Query understanding.
2. Retrieval from legal corpus.
3. Context ranking and selection.
4. Context assembly with citations.
5. LLM response generation.

### 5.2 LLM Engine (Llama)
The Llama-based LLM is responsible for:
- Reasoning over retrieved legal context.
- Converting legal content into usable professional responses.
- Drafting legal notices in structured form.
- Supporting iterative refinements based on user follow-up.

Expected behavior:
- Citation-aware responses.
- Domain-consistent legal style.
- Structured outputs for notice drafting.

### 5.3 Vector Database
A vector database is required because exact keyword matching alone is not sufficient for legal retrieval.

Benefits:
- Semantic retrieval beyond exact term matching.
- Better recall for paraphrased legal queries.
- Reduced hallucination risk by grounding responses in retrieved context.
- Strong support for citation-linked responses.

Each vector record should include:
- Embedding vector.
- Original text chunk.
- Metadata (for example: source file, act name, section, year, jurisdiction, page/chunk index, domain tags).

---

## 6. End-to-End Runtime Workflow

1. User submits a legal query or notice request in the UI.
2. Backend validates the request and forwards it.
3. Orchestration layer classifies domain and intent.
4. RAG retrieves relevant legal passages from legal DB/vector DB.
5. Context is assembled for generation.
6. Llama LLM generates the response or notice draft.
7. Output is returned with source references/citations.
8. User reviews, edits, and exports as needed.

---

## 7. Legal Notice Generation Workflow

1. Collect facts (parties, timeline, contract/policy references, claims, jurisdiction).
2. Domain classifier selects the relevant notice context.
3. RAG retrieves relevant laws and similar historical notices.
4. Draft engine composes structured notice sections:
   - Facts
   - Legal basis
   - Demands/relief
   - Timeline/deadline
   - Consequence of non-compliance
5. LLM generates an editable draft with references.
6. Human legal review is performed before finalization.

---

## 8. JSON Schema Guidance

Each JSON chunk should contain:
- `document_id`
- `document_type` (`judgement`, `notice`, `act`)
- `title`
- `year`
- `domain`
- `jurisdiction`
- `source_path`
- `page_number`
- `chunk_id`
- `chunk_text`
- `citations` (if available)
- `entities` (for example: parties, statute references)

This supports unified indexing and retrieval across notices, judgements, and Acts.

---

## 9. Reliability and Governance Requirements

- Human-in-the-loop review before final legal notice output.
- Citation-first response mode for legal Q&A.
- Prompt/source/output audit trail.
- Versioning of models, datasets, and templates.
- PII/confidentiality controls for legal documents.
- Role-based access controls (lawyer/admin/staff).

---

## 10. Implementation Roadmap

### Phase 1: Data Foundation
- Complete conversion of `judgements/` PDFs to JSON.
- Implement and run `laws_browse/` PDFs to JSON pipeline.
- Standardize schema across all corpora.

### Phase 2: Retrieval Core
- Finalize chunking and embedding pipeline.
- Index data into vector DB with metadata.
- Evaluate retrieval relevance (top-k quality).

### Phase 3: Assistant and Drafting
- Domain classifier integration.
- RAG orchestration integration.
- Llama response generation integration.
- Legal notice template workflow integration.

### Phase 4: Productization
- UI workflow maturity.
- User authentication/access control completion.
- Monitoring/logging and QA workflow refinement.

---

## 11. Success Metrics (Initial)

- Retrieval relevance quality for top-k retrieved chunks.
- Citation coverage rate in generated outputs.
- Legal notice draft acceptance/edit ratio.
- Average response latency.
- Hallucination/error rate from legal QA review.

---

## 12. Open Questions

1. Is the product scope India-only, or should it support additional jurisdictions later?
2. Which exact Llama variant/version will be used in production?
3. Which vector database will be finalized?
4. Is the JSON schema already fixed across notices/judgements/acts?
5. What citation granularity is required (page-level, section-level, or both)?
6. What notice output formats are mandatory (text, DOCX, PDF)?
7. Is multilingual support required?
8. Is the product single-firm only or multi-firm?
9. What data retention/encryption/audit constraints must be enforced?
10. What mandatory legal review gate should be enforced before final notice issuance?

---

## 13. Immediate Next Actions

1. Freeze a single JSON schema for all document types.
2. Complete Acts-to-JSON conversion pipeline.
3. Finalize vector DB and embedding stack.
4. Implement minimal citation-grounded RAG flow.
5. Build and validate the first production-ready legal notice workflow.
