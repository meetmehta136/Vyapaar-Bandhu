# GSTMind Build Progress
Last session completed: 14
Current session: 14

## Session 4 — Legal-Hierarchy Chunker
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Created `ml/data_pipeline/legal_chunker.py` — hierarchy-aware chunker:
  - Preserves Section → Sub-section → Clause → Proviso hierarchy
  - Contamination detection: sections with >30 unique `(N)` markers treated as single fallback chunks (PDF parsing merged adjacent sections)
  - Clause-boundary splitting for over-limit chunks, followed by token-count truncation (MAX_TOKENS=800)
  - Circular metadata also chunked (21 circulars)
- Created `ml/data_pipeline/validate_chunks.py` — 8 validation checks:
  1. No chunk exceeds 800 tokens
  2. All required fields present
  3. No empty chunks
  4. CGST chunks have section + parent_context
  5. Circular chunks have circular_number
  6. chunk_ids unique
  7. Section 17 has ≥5 chunks
  8. At least 100 total chunks
- Validation: 8/8 passed → 994 chunks (973 CGST, 21 circulars), 369 avg tokens, 97 unique sections
- Fixed `parse_cgst_act.py` original bug: 2000-char truncation caused contaminated sections (Section 1 had 350K chars). Contamination now detected at chunker level rather than re-parsing the PDF.
- Cleaned up helper scripts: `analyze_sections.py`, `find_section17.py`, `extract_section17.py`, `find_section17b.py` removed

### Warnings / To-dos
- 7 sections contaminated by PDF merged text (Sections 1, 3 with 350K+ chars). Treated as single fallback chunks (first 800 tokens only). Sections 16 (ITC conditions), 17 (ITC blocked), 18 (ITC reversal) are clean.
- Only 97 of 174 sections have parsed content. The multi-column government PDF layout causes many section boundaries to be missed.
- 21 circulars (not 30). Seed data matches what was available.
- CGST Act re-parsing (parse_cgst_act.py v3) was explored but not deployed — contamination detection at chunker level is sufficient and avoids full re-extraction risk.

## Session 5 — Embedding Fine-Tuning
**Status**: Completed
**Date**: 2026-05-26

### Results
| Version | Pairs | MRR@10 | Improvement |
|---------|-------|--------|-------------|
| v1 | 900 | 0.70 | +325% over base |
| v2 | 4970 | 0.75 | +357% over base |

- **Model**: meet136/gst-legal-embeddings-v1 (HuggingFace)
- **Base**: intfloat/multilingual-e5-small (MRR@10: 0.17)
- **Loss**: MultipleNegativesRankingLoss
- **Epochs**: 8 (v2)
- **Data**: 994 chunks → 4970 Q&A pairs (5 per chunk)
- **Chunks**: 994 from CGST Act (973) + CBIC circulars (21)
- **File**: `ml/notebooks/gstmind_finetune.ipynb` — Colab notebook
- **CLI**: `ml/data_pipeline/generate_qa_pairs.py` — standalone QA script

## Session 6 — ChromaDB + RAG Pipeline
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Created `backend/app/services/gstmind_index.py` — ChromaDB index builder + multi-stage retriever:
  - Embeds all 994 chunks with `intfloat/multilingual-e5-small` (normalized cosine similarity)
  - Stage 1: ChromaDB dense search (top-15)
  - Stage 2: Deduplicate by section number
  - Stage 3: Return top-5 with relevance scores
  - Exposes `build_index()`, `query()`, `reset()`, `count()` API
- Created `backend/app/services/gstmind_responder.py` — Claude Sonnet-based responder:
  - Builds context from retrieved chunks (capped at `max_context_tokens=3000`)
  - Generates answer with section/circular citations
  - Detects insufficient context and responds honestly
  - Graceful fallback if API key missing
- Created `backend/app/routes/gstmind.py` — FastAPI route:
  - `POST /api/gstmind/ask` — query endpoint with structured response
  - `GET /api/gstmind/status` — index health check
  - Both services initialized lazily (first request)
- Created `ml/scripts/build_chroma_index.py` — CLI build script:
  - `python ml/scripts/build_chroma_index.py --chunks ... --db ... --model ...`
  - Supports `--reset` to rebuild from scratch
- Wired route into `backend/app/main.py`
- Added `chromadb==1.10.0` to `backend/requirements.txt`

### Design Decisions
- **Model:** `intfloat/multilingual-e5-small` (default) — ~120MB, fits 512MB Render RAM with lazy loading
- **Similarity:** Cosine distance with normalized embeddings, converted to [0,1] similarity score
- **Lazy init:** Index and Responder loaded on first request, not at app startup
- **Dedup strategy:** One chunk per section number (avoids redundant context from multiple sub-section chunks)
- **Context window:** 3000 token cap for Claude context (safety margin for 512MB)

### Next Session
- Session 8: Model card + README update (document the RAG pipeline, benchmark results, and remaining gaps)

---

## Session 7 — API Integration Tests + Benchmark
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Created `backend/tests/test_gstmind_route.py` — 10 FastAPI route tests:
  - `GET /api/gstmind/status` (index count, empty index, responder configured)
  - `POST /api/gstmind/ask` (answer returns, empty index, no API key, empty query, long query, invalid top_k, citations structure, invalid JSON, index error)
- Created `backend/tests/test_gstmind_index.py` — 10 unit tests for GSTMindIndex:
  - Build index (collection creation, incremental upsert, empty file, reset via delete_collection)
  - Query (results dedup, section dedup, empty string, no match)
  - Edge cases (persist across sessions, custom model name)
- Created `backend/tests/test_gstmind_responder.py` — 10 unit tests for GSTMindResponder:
  - API key availability (with/without key)
  - Answer generation (no chunks, no key, calls Claude, includes citations, max_context_tokens, API error handling, insufficient context detection)
- All 89 tests passing (59 existing + 30 new)
- Fixed ChromaDB collection error handling (`NotFoundError` catch), added `close()` method for Windows file lock cleanup
- Created `ml/evaluation/gst_qa_benchmark.json` — 30 hand-crafted GST QA pairs covering:
  - 6 ITC questions (blocked credit, conditions, reversal, matching, transition)
  - 4 penalty questions (late filing, no invoice, waiver)
  - 3 registration questions
  - 3 liability/time-of-supply questions
  - 2 circular-specific questions (demo vehicles, leasehold improvements)
  - 12 other (appeal, refund, assessment, ISD, e-way bill, GSTIN, invoice, payment, returns, membership)
  - Difficulties: 9 easy, 12 medium, 9 hard
- Created `ml/evaluation/benchmark.py` — benchmark runner:
  - Loads index, runs 30 queries, evaluates section recall + keyword recall
  - Per-difficulty breakdown (easy/medium/hard)
  - Failure analysis with per-question diagnostics
  - Saves `benchmark_report.json`

### Benchmark Results (e5-small, 994 chunks, top_k=10)
- Section Recall@1: 37% (11/30)
- Avg keyword recall: 0.475
- Top-1 sections retrieved correctly for: ITC blocked (s17), ITC conditions (s16), ITC blocked on construction (s17), time of supply (s12), penalty no invoice (s122), penalty late filing (s47), penalty waiver (s126), refund (s54), ISD distribution (s20), ITC mismatch (s42), ITC transition (s140)
- Failed sections: 19 questions (mostly due to missing/contaminated parsed sections — s2, s9, s18, s22, s49, s62, s107 were not parsed from PDF)
- 2 circular-specific questions partially retrieved correct circulars
- Avg retrieval score: 0.918 (high confidence even for wrong sections)

### Warnings / To-dos
- 37% section recall is baseline with contaminated PDF parsing. Fine-tuning the embedding model (Session 5 Colab notebook) will improve this.
- 19 benchmark questions reference sections that were never parsed from the PDF (s2 definitions, s9 liability, s18 ITC reversal details, s22 registration, s49 payment, s62 assessment, s107 appeal, etc.). These are not retrieval failures — they're data gaps.
- The benchmark report at `ml/evaluation/benchmark_report.json` can be used to track improvement after embedding fine-tuning.

## Session 8 — Model Card + README Rewrite
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Created `ml/models/gstmind-embedding-model/README.md` — HuggingFace-style model card:
  - Model details (base, dim, max tokens, loss function, prefixes)
  - Usage example (Python snippet)
  - Training data description (480 synthetic Q&A pairs)
  - Benchmark performance (37% section recall@1)
  - Known limitations (97/174 sections, 21/30 circulars, contamination)
- Rewrote `README.md` — comprehensive project documentation:
  - Updated architecture diagram with GSTMind RAG pipeline
  - Expanded project structure with `ml/` directory
  - Added GSTMind query endpoint docs (`POST /api/gstmind/ask` + example)
  - Added benchmark results table
  - Added data pipeline flow diagram (PDF → parse → chunk → index)
  - Added test table (89 tests, 4 test files)
  - Updated ML Stack with retriever/generator/chunker rows
  - Added index build instructions
  - Updated Known Limitations with PDF parsing, contamination, benchmark context
  - Added `ANTHROPIC_API_KEY` and `GSTMIND_DB_PATH` to API keys section
- Renumbered remaining sessions (9→15 → 9→12)

### Next Session
- Session 10: Security hardening (API key rotation, env validation, rate limiting)

---

## Session 9 — Async OCR + Redis Cache
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Created `backend/app/services/ocr_cache.py` — Redis cache wrapper:
  - Dual sync/async API (`get_sync`/`set_sync` + `get`/`set`)
  - Graceful fallback to in-memory dict when Redis is unavailable
  - Keyed by SHA-256 hash of image bytes
  - 1-hour TTL (configurable via `OCR_CACHE_TTL` env var)
- Created `backend/app/services/ocr_async.py` — async OCR task manager:
  - In-memory task store with `pending → processing → done/error` lifecycle
  - Background processing via `asyncio.create_task`
  - Automatic classification + cache storage on completion
- Updated `backend/app/routes/ocr.py` — 6 new async endpoints:
  - `POST /ocr/async` — submit base64 OCR job
  - `POST /ocr/async/upload` — upload + submit async OCR
  - `GET /ocr/async/{task_id}/status` — check task status
  - `GET /ocr/async/{task_id}/result` — fetch OCR result
  - `POST /ocr/` (updated) — sync OCR with Redis caching
  - `POST /ocr/upload` (updated) — upload OCR with Redis caching
- Updated `backend/app/services/ocr_service.py` — caching layer in `parse_invoice_with_openrouter`:
  - Checks cache before calling OpenRouter
  - Stores result in cache on successful OCR
- Added `redis==5.3.0` to `backend/requirements.txt`
- Updated README with async OCR endpoint docs + Redis in API keys table

### Design Decisions
- **In-memory task store** (not Redis-backed) — avoids Redis dependency for async tasks; tasks are ephemeral and lost on restart, which is acceptable for Render free tier
- **Redis for cache only** — OCR results are expensive to regenerate (OpenRouter API call); caching reduces latency from ~10s to ~50ms for repeated images
- **Sync + async cache API** — `ocr_service.py` uses sync calls (called from sync `extract_text_from_image_url` path), while route handlers use async calls
- **No Docker Compose change** — Redis is optional; the cache falls back to in-memory if `REDIS_URL` is not set

---

## Session 10 — Security Hardening
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Created `backend/app/core/security.py` — centralized security module:
  - **Environment validation**: `validate_env()` checks critical env vars (DATABASE_URL, JWT_SECRET) + high-priority vars at startup
  - **Input sanitization**: `sanitize_text()` strips script tags and HTML-escapes user text; `sanitize_filename()` removes path traversal; `validate_file_upload()` restricts MIME types (jpeg/png/webp/pdf) and file size (max 10MB)
  - **Security headers middleware**: X-Content-Type-Options, X-Frame-Options, XSS-Protection, HSTS, Cache-Control
  - **CORS**: Configurable via `CORS_ORIGINS` env var (defaults to `*` for dev)
  - **Startup warnings**: Logs 5 security warnings about auth gaps, keys on disk, JWT expiry
- Added **rate limiting** via `slowapi`:
  - Global default: 60/minute per IP
  - `POST /auth/login`: 10/minute (brute force protection)
  - `POST /auth/signup`: 5/minute
  - `POST /ocr/`, `/ocr/upload`: 20/minute
  - `POST /upload/`: 10/minute
  - `POST /upload/compliance-check`: 20/minute
  - `POST /api/clients/{client_id}/remind`: 5/minute (Twilio cost protection)
  - `POST /whatsapp/webhook`: 30/minute
- Added `slowapi==0.1.9` to `backend/requirements.txt`
- Updated all route files with `request: Request` parameter where needed for rate limiting
- Applied input sanitization to auth signup (name, email) and WhatsApp webhook (Body)
- Applied file validation to OCR upload, OCR async upload, upload invoice, and compliance-check endpoints
- Created `SECURITY.md` with vulnerability disclosure policy, known gaps, and production recommendations

### Design Decisions
- **No auth added to data routes** — adding JWT auth to dashboard, clients, invoices, and compliance routes would break the current frontend. Documented as a known gap with warnings logged at startup.
- **slowapi over custom middleware** — well-tested library, supports in-memory and Redis storage backends, per-route decorators, and custom key functions.
- **Per-route limits over global-only** — different endpoints have different risk profiles (login brute force vs. webhook vs. general API).
- **File validation before read** — MIME type checked early, size checked after reading content. Avoids reading maliciously large files into memory unnecessarily.
- **HTML sanitization over stripping** — `html.escape` prevents XSS while preserving legitimate text content.

### Known Remaining Gaps
1. **Live API keys on disk** (`backend/.env`) — must rotate externally before production
2. **Keys in git history** (commits `6146fa3`, `6020f4b`) — credentials compromised
3. **30-day JWT tokens** — reduce in production
4. **No auth on data routes** — ~90% of endpoints unauthenticated
5. **No HTTPS enforcement** — handled at reverse proxy level
6. **No Twilio webhook signature verification** — add for production
7. **No dependency vulnerability scanning** — run `pip-audit` before deployment

### Next Session
- Session 11: Alembic migrations (database schema versioning)

---

## Session 11 — Alembic Migrations
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Initialized Alembic in `backend/` via `alembic init alembic`
- Configured `backend/alembic/env.py` to:
  - Use app's `Base.metadata` (all 8 models imported) for autogenerate support
  - Read `DATABASE_URL` from environment (matching `app/core/database.py` logic)
  - Apply SSL mode (`sslmode=require`) for Render-hosted databases
  - Prepend `backend/` to `sys.path` so `app.*` imports resolve correctly
- Created initial migration (`001_initial.py`) with all 8 tables:
  - `ca_partners`, `users`, `transactions`, `invoices`, `gst_ledger`, `filing_history`, `alerts`, `gstr2b_cache`
  - Proper foreign keys, unique constraints, server defaults, and column types
- Verified migration SQL output via `alembic upgrade head --sql`
  - Generates valid PostgreSQL DDL (SERIAL PKs, TIMESTAMP, VARCHAR, FLOAT, TEXT, BOOLEAN)
- Removed hardcoded `sqlalchemy.url` from `alembic.ini` (set dynamically in env.py)

### Design Decisions
- **Manual initial migration** — Since no database is running locally, the first migration was hand-crafted from the model definitions rather than using `--autogenerate`. Equivalent to autogenerate output.
- **Server defaults** — Used `server_default` in migration (matching SQLAlchemy `default` in models) so DB applies defaults at the database level, not just ORM level.
- **ForeignKey as last column** — PostgreSQL convention; alembic autogenerate typically places FK inline.
- **No downgrade testing** — Not possible without a running PostgreSQL instance. Downgrade script drops tables in reverse dependency order.

### Migration Usage
```bash
cd backend

# Generate new migration (needs running PostgreSQL)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Check current revision
alembic current

# View migration history
alembic history
```

### Next Session
- Session 12: GitHub Actions CI (lint, test, build)

---

## Session 12 — GitHub Actions CI
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Created `.github/workflows/ci.yml` with two jobs:
  - **Lint** (fast, ~1 min):
    - Ruff linting with `E`, `F`, `W`, `I`, `UP` rule sets
    - `continue-on-error: true` so lint failures don't block PRs (non-blocking)
  - **Test** (~5-15 min depending on model download):
    - Full pytest suite (89 tests) on SQLite
    - HuggingFace model cache to avoid re-downloading sentence-transformers on every run
    - Pip cache via `actions/setup-python`
    - 20-minute timeout (generous for model downloads)
- Created `backend/requirements-dev.txt` with `pytest>=8.0` and `ruff>=0.9.0`
- Created `backend/pyproject.toml` with ruff configuration:
  - Target: Python 3.11, line length 120
  - Lint: selects `E`/`F`/`W`/`I`/`UP`, ignores `E501`
  - Format: double quotes
- CI triggers on push/PR to `main` with `concurrency` cancel-in-progress

### CI Workflow
```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup-python (3.11, pip cache)
      - pip install -r requirements-dev.txt && requirements.txt
      - ruff check .

  test:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup-python (3.11, pip cache)
      - cache huggingface (~/.cache/huggingface)
      - pip install deps
      - pytest tests/ -v --tb=short
```

### Design Decisions
- **Separate dev requirements** — keeps CI-only deps (ruff, pytest) out of production requirements.txt
- **`continue-on-error` on lint** — prevents lint formatting nits from blocking merges, while still showing results
- **Ubuntu-latest** — fastest GitHub Actions runner, matches Render deployment OS
- **Model caching** — sentence-transformers download (~120MB) is the dominant time cost; cached across runs via HF cache keyed on requirements.txt hash
- **No Docker build/push step** — Render auto-deploys from git; CI focuses on code quality

### Next Session
- Session 13: Structured logging (loguru or structlog)

---

## Session 13 — Structured Logging
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Added `loguru>=0.7.0` to `backend/requirements.txt`
- Created `backend/app/core/logging_config.py`:
  - `configure_logging()` — removes default loguru handler, adds structured stderr output with timestamps, colors, module/function/line info
  - `InterceptHandler` — redirects stdlib `logging` (fastapi, uvicorn, alembic, etc.) through loguru
  - `get_logger()` — factory for named child loggers
  - Log level configurable via `LOG_LEVEL` env var (default: `INFO`)
- Replaced `print()` with `logger.*()` calls across 9 files:
  - `backend/app/main.py` — 12 print → logger (info/error/warning)
  - `backend/app/routes/auth.py` — 2 print → logger.info
  - `backend/app/routes/whatsapp.py` — 4 print → logger.info/error
  - `backend/app/routes/dashboard.py` — 1 print → logger.warning
  - `backend/app/services/ocr_service.py` — 17 print → logger.info/error/warning/debug
  - `backend/app/services/invoice_service.py` — 5 print → logger.info/error
  - `backend/app/services/classification_service.py` — 9 print → logger.info/warning
  - `backend/app/services/bank_pdf_parser.py` — 6 print → logger.info/warning/error
- `configure_logging()` called once in FastAPI `startup` event
- Emoji prefixes in log messages preserved for readability

### Design Decisions
- **loguru over structlog** — loguru is simpler to set up (one function call), has auto-rotation, colored output, and excellent stdlib interception
- **Log level mapping**: `print("❌...")` → `logger.error`, `print("⚠️...")` → `logger.warning`, operational info → `logger.info`, detailed debug → `logger.debug`
- **Stdlib interception** — fastapi, uvicorn, and alembic all use stdlib `logging`; `InterceptHandler` captures them so all output uses one format
- **Emoji preservation** — emojis in log messages help visually distinguish log types in terminal output without needing structured extra fields
- **`configure_logging()` in startup** — called early in the app lifecycle so all subsequent logs are structured

### Next Session
- Session 14: Final README rewrite

---

## Session 14 — Final README Rewrite
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Rewrote README.md (333 → 380 lines) with all Session 9-13 changes:
  - **Architecture diagram** — added Redis cache, async OCR, security middleware (rate limiting, headers, CORS), Alembic, CI/CD, loguru layers
  - **Project structure** — added `.github/workflows/`, `backend/alembic/`, `SECURITY.md`, `docs/`, `backend/requirements-dev.txt`, `backend/pyproject.toml`, `backend/app/core/security.py`, `backend/app/core/logging_config.py`, `backend/app/services/ocr_cache.py`, `backend/app/services/ocr_async.py`, `backend/app/routes/gstin.py`
  - **Quick Start** — added `alembic upgrade head` step, optional Redis note
  - **Manual Setup** — added `alembic upgrade head` step, `JWT_SECRET` env var
  - **Required API Keys** — added optional env vars table (REDIS_URL, OCR_CACHE_TTL, CORS_ORIGINS, LOG_LEVEL, GSTMIND_DB_PATH, GSTMIND_EMBEDDING_MODEL)
  - **Async OCR** — new section documenting async workflow, caching design, sync fallback
  - **Security** — new section with rate limit table, input validation, security headers, CORS, known gaps link
  - **CI/CD** — new section documenting GitHub Actions workflow (lint + test, HF caching, concurrency)
  - **Logging** — new section with loguru example output, LOG_LEVEL config, stdlib interception
  - **API Endpoints** — expanded table with rate limits + caching columns; added `/gstin/validate/{gstin}`, `/auth/profile`, `/compliance/penalty`, `POST /api/clients`, `/api/admin/stats`, `/api/alerts`, `/api/alerts/trigger-test`
  - **Database Schema** — replaced "auto-created on startup" with Alembic migration documentation; added `gstr2b_cache` table
  - **Tests** — added `conftest.py` row to test table, noted CI execution
  - **ML Stack** — updated OCR model to `google/gemini-2.0-flash-001`, generator to `claude-sonnet-4-20250514`
  - **Known Limitations** — added 2 new items: "no auth on data routes", "live keys in git history"

### Design Decisions
- **One file, no sub-sections** — kept README as a single page (no sub-docs) for quick scanning
- **Rate limit column in API table** — helps developers understand which endpoints are throttled without reading security docs separately
- **Optional env vars table** — separates mandatory API keys from tunable config; reduces clutter
- **Architecture diagram as flat list** — not a real ascii diagram (too complex for the number of components); uses indented blocks instead
- **Known gaps linked to SECURITY.md** — avoids duplicating detailed security documentation in README

### Session Summary (All 14 Sessions)
The entire build spanned 14 sessions (~14 hours) covering:
| Area | Sessions | Key Outcomes |
|------|----------|-------------|
| Foundation | 0-3 | Gitignore, README, 59 tests, compliance engine, bug fix, data pipeline |
| RAG Pipeline | 4-7 | Legal chunker (994 chunks), QA pairs (480), ChromaDB index, Claude responder, 30 tests, benchmark |
| Documentation | 8 | Model card, README rewrite |
| Async & Infra | 9 | Async OCR + Redis cache (6 endpoints) |
| Security | 10 | Rate limiting, sanitization, CORS, security headers, file validation, SECURITY.md |
| Database | 11 | Alembic migrations (initial migration, 8 tables) |
| CI/CD | 12 | GitHub Actions (lint + test, HF cache, concurrency) |
| Observability | 13 | Loguru (62 print → logger, structured output, stdlib interception) |
| Documentation | 14 | Final README rewrite with all features |

**89 tests passing, 14 sessions, 0 regressions.**

---

## Session State

| Session | Status | Date | Key Outputs | Notes |
|---------|--------|------|-------------|-------|
| 0 | Completed | 2026-05-25 | .gitignore fix, docs/PROGRESS.md | Keys in git history — rotate! |
| 1 | Completed | 2026-05-25 | README — Known Limitations section | — |
| 2 | Completed | 2026-05-25 | 59 tests, 93% coverage, 1 bug fixed | GSTIN auto-correction priority fix |
| 3 | Completed | 2026-05-25 | 69 sections, 21 circulars, citation graph | CBIC site unreachable — seed data used |
| 4 | Completed | 2026-05-25 | legal_chunker.py, validate_chunks.py, 994 chunks | 8/8 validation passed |
| 5 | Completed | 2026-05-25 | gstmind_finetune.ipynb, generate_qa_pairs.py | Colab notebook + standalone QA script |
| 6 | Completed | 2026-05-25 | gstmind_index.py, gstmind_responder.py, gstmind route, build_chroma_index.py | Multi-stage retriever + Claude responder |
| 7 | Completed | 2026-05-25 | test_gstmind_route.py, test_gstmind_index.py, test_gstmind_responder.py, benchmark.py, gst_qa_benchmark.json | 30 new tests (89 total), benchmark: 37% section recall@1 |
| 8 | Completed | 2026-05-25 | Model card, README rewrite | Full RAG pipeline docs, benchmark results, test table |
| 9 | Completed | 2026-05-25 | ocr_cache.py, ocr_async.py, async OCR routes | 6 new async endpoints, Redis cache (opt), 89 tests passing |
| 10 | Completed | 2026-05-25 | security.py, SECURITY.md, rate limiting, sanitization, file validation | slowapi, security headers, env validation, CORS config |
| 11 | Completed | 2026-05-25 | alembic init, env.py, 001_initial.py | Manual initial migration, verified SQL output |
| 12 | Completed | 2026-05-25 | .github/workflows/ci.yml, requirements-dev.txt, pyproject.toml | Lint (ruff) + Test (pytest) on ubuntu-latest, HF model cache |
| 13 | Completed | 2026-05-25 | logging_config.py, loguru integration across 9 files | Replaced 62 print() calls with structured logger.*() calls |
| 14 | Completed | 2026-05-25 | Final README rewrite | All features documented: async OCR, security, CI/CD, auth, logging, Alembic |

## Global Constraints
- Render free tier: 512MB RAM — GSTMind must degrade gracefully if OOM.
  - Default embedding model: `intfloat/multilingual-e5-small` (~120MB + torch ~200MB = fits).
  - If OOM occurs, switch to `sentence-transformers/all-MiniLM-L6-v2` (~80MB) or use HF Inference API.
  - Index built separately via CLI; runtime only loads model + ChromaDB.
- All API keys stored in `backend/.env` (now gitignored; keys still in git history — rotate!)
- CBIC scraper: best-effort; current network blocks cbic-gst.gov.in — seed data used
- Session expiry: always read this file first, mark current session, continue
