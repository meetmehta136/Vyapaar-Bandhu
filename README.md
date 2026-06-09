# VyapaarBandhu
> AI-Powered GST Compliance Assistant for Indian Small Businesses
> **103 tests** · RAG pipeline (ChromaDB + Claude) · Async OCR (Redis cache) · CI/CD · Alembic · Loguru

## Architecture

```
WhatsApp → Twilio Webhook → FastAPI Backend → PostgreSQL
                         ↓
              OpenRouter VLM (invoice OCR)
              HuggingFace XLM-RoBERTa (GST classifier)
              Compliance Engine (Pure Python)
                         ↓
              ┌─ GSTMind RAG Pipeline ─────────────────┐
              │  Query → Embed(e5-small)               │
              │         → ChromaDB (994 sections)      │
              │         → Claude Sonnet (answer+cites)  │
              └─────────────────────────────────────────┘
                         ↓
              ┌─ Security & Infrastructure ─────────────┐
              │  Rate limiting (slowapi)                 │
              │  Security headers · Input sanitization   │
              │  File validation · CORS (env config)     │
              │  Redis (opt) OCR cache                   │
              │  Alembic migrations                      │
              │  GitHub Actions CI (lint + test)         │
              │  Structured logging (loguru)             │
              └──────────────────────────────────────────┘
                         ↓
              CA Dashboard (React + Vite + Tailwind)
```

## Project Structure

```
vyapaar-bandhu/
├── backend/                  # FastAPI Python app
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── routes/          # API routes (auth, gstmind, whatsapp, ocr, ...)
│   │   ├── models/          # SQLAlchemy models (8 tables)
│   │   ├── services/        # OCR, classifier, GSTMind, invoice, PDF parser
│   │   └── core/            # Database, auth utils, security, logging config
│   ├── tests/               # 103 pytest tests (conftest.py + 7 test files)
│   ├── alembic/             # Migration scripts (001_initial.py)
│   ├── alembic.ini          # Alembic configuration
│   ├── requirements.txt     # Production deps (chromadb, redis, slowapi, loguru)
│   ├── requirements-dev.txt # Dev deps (pytest, ruff)
│   ├── pyproject.toml       # Ruff config
│   └── Dockerfile
├── vyapaarbandhu-ca-elite/  # React frontend (CA Dashboard)
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── ml/                      # Data pipeline & ML assets
│   ├── data/                # Chunks, citation graph, parsed sections
│   ├── data_pipeline/       # Scraper, PDF parser, chunker, QA generator
│   ├── notebooks/           # Colab for embedding fine-tuning
│   ├── evaluation/          # 30-question benchmark + runner
│   ├── models/              # Model card (HuggingFace-style)
│   └── scripts/             # Build ChromaDB index CLI
├── .github/workflows/       # CI pipeline (lint + test)
├── docker-compose.yml
├── SECURITY.md              # Security policy & known gaps
├── docs/PROGRESS.md         # Session state tracking
└── .env
```

## Quick Start (Docker)

### Prerequisites
- Docker Desktop installed and running
- Docker Compose v2+

### 1. Setup Environment
```bash
cp .env.example .env
# Edit .env with your API keys (see Required API Keys below)
```

### 2. Start All Services
```bash
docker-compose up --build
```

This starts:
- **PostgreSQL** on port `5433`
- **FastAPI Backend** on port `8000`
- **React Frontend** on port `3000`

### 3. Run Database Migrations
```bash
docker exec -it vyapaarbandhu-backend-1 alembic upgrade head
```

### 4. Build the GSTMind Index
```bash
cd backend
pip install -r requirements.txt
python ../ml/scripts/build_chroma_index.py \
    --chunks ../ml/data/processed/all_chunks.jsonl \
    --db data/chromadb \
    --model intfloat/multilingual-e5-small
```

### 5. Access
- **CA Dashboard**: http://localhost:3000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **GSTMind Status**: http://localhost:8000/api/gstmind/status
- **Health Check**: http://localhost:8000/health

## Manual Setup (Without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Environment
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/vyapaar_bandhu"
export OPENROUTER_API_KEY="your_key"
export HF_API_KEY="your_key"
export ANTHROPIC_API_KEY="your_key"  # For GSTMind Claude responder
export JWT_SECRET="your-secret-key-min-32-chars"
export GSTMIND_DB_PATH="data/chromadb"

# Run migrations
alembic upgrade head

# Build index first, then run
python ../ml/scripts/build_chroma_index.py
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd vyapaarbandhu-ca-elite
npm install
npm run dev
```

## Required API Keys

| Service | Purpose | Get Key From |
|---------|---------|--------------|
| OpenRouter | Invoice OCR (VLM) | https://openrouter.ai/keys |
| HuggingFace | GST Classification | https://huggingface.co/settings/tokens |
| Anthropic | GSTMind RAG (Claude) | https://console.anthropic.com/ |
| Twilio | WhatsApp Bot | https://console.twilio.com/ |
| Redis (optional) | OCR result caching | `REDIS_URL` env var; falls back to in-memory |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `""` | Redis connection URL for OCR cache (optional; in-memory fallback) |
| `OCR_CACHE_TTL` | `3600` | OCR cache TTL in seconds |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `GSTMIND_DB_PATH` | `data/chromadb` | ChromaDB persistent path |
| `GSTMIND_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Embedding model name |

## GSTMind — RAG Query Engine

GSTMind is a retrieval-augmented generation pipeline for the CGST Act, 2017 and CBIC circulars. It answers GST compliance questions with section-level citations.

### Pipeline

```
User Question
     ↓
  Embed (multilingual-e5-small, cosine similarity)
     ↓
  ChromaDB — top-15 dense search → section dedup → top-5
     ↓
  Claude Sonnet (with context + citation format)
     ↓
  Answer + Citations
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/gstmind/ask` | Query GSTMind (body: `{"query": "...", "top_k": 5}`) |
| `GET` | `/api/gstmind/status` | Index health check |

### Example
```bash
curl -X POST http://localhost:8000/api/gstmind/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "When is ITC blocked?"}'
```

Response:
```json
{
  "answer": "As per Section 17(5) of the CGST Act, 2017, input tax credit is blocked for...",
  "citations": [
    {
      "citation": "CGST Act, 2017 — Section 17(5)",
      "source_type": "cgst_act",
      "section": "17",
      "relevance_score": 0.92
    }
  ],
  "needs_more_info": false,
  "error": null
}
```

## Async OCR with Redis Caching

OCR tasks (invoice processing via OpenRouter VLM) support both sync and async modes with optional Redis caching.

### Async Workflow

```
POST /ocr/async  ──→  { task_id: "abc123", status: "pending" }
                           ↓ (background)
                      processing...
                           ↓
GET /ocr/async/abc123/status  ──→  { status: "done" }
                           ↓
GET /ocr/async/abc123/result  ──→  { fields: {...}, confidence: 0.92 }
```

### Design
- **In-memory task store** — tasks are ephemeral (lost on restart), acceptable for Render free tier
- **Redis cache** — SHA-256 keyed, 1-hour TTL, graceful in-memory fallback
- **Sync endpoints** (`POST /ocr/`) also use cache — repeated images return in ~50ms instead of ~10s

## Security

Security is enforced at multiple layers:

### Rate Limiting (slowapi)
| Endpoint | Limit |
|----------|-------|
| Global (all endpoints) | 60/min per IP |
| `POST /auth/login` | 10/min |
| `POST /auth/signup` | 5/min |
| `POST /ocr/*` | 20/min |
| `POST /upload/*` | 10-20/min |
| `POST /whatsapp/webhook` | 30/min |
| `POST /api/clients/{id}/remind` | 5/min |

### Input Validation
- **Text sanitization**: HTML escaping, script tag removal, length truncation (10K chars)
- **File validation**: MIME type restricted to `image/jpeg`, `image/png`, `image/webp`, `application/pdf`, max 10MB

### Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Cache-Control: no-store`

### CORS
- Configurable via `CORS_ORIGINS` env var (comma-separated or `*`)

**Known gaps** (see `SECURITY.md`): status polling endpoints unauthenticated (intentional), 30-day JWT tokens, keys in git history.

## CI/CD — GitHub Actions

| Trigger | Workflow |
|---------|----------|
| Push/PR to `main` | CI runs `ruff check .` (lint) + `pytest tests/` (103 tests) |

- **OS**: `ubuntu-latest`
- **Python**: 3.11
- **Database**: SQLite (test DB)
- **Caching**: HuggingFace model cache (sentence-transformers ~120MB)
- **Concurrency**: Cancel-in-progress for redundant runs
- **Lint**: `continue-on-error: true` (non-blocking)

## Structured Logging

All application logs use **loguru** instead of print():

```
2026-05-25 14:30:00 | INFO    | ocr_service:parse_invoice_with_openrouter:47 - Sending to OpenRouter VLM...
2026-05-25 14:30:02 | INFO    | ocr_service:parse_invoice_with_openrouter:119 - OpenRouter status: 200
2026-05-25 14:30:02 | ERROR   | ocr_service:parse_invoice_with_openrouter:122 - OpenRouter error: 401 ...
```

- Level configurable via `LOG_LEVEL` env var (default: `INFO`)
- Stdlib logging (fastapi, uvicorn, alembic) intercepted and redirected through loguru
- Backtrace on errors, `diagnose=False` for production safety
- 62 print() calls replaced across 9 files

## API Endpoints

### Auth
| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| POST | `/auth/signup` | 5/min | Register CA account |
| POST | `/auth/login` | 10/min | Login |
| GET | `/auth/me` | — | Get current CA profile |
| PUT | `/auth/profile` | — | Update CA profile |

### GSTMind (RAG)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/gstmind/ask` | GST compliance Q&A with citations |
| GET | `/api/gstmind/status` | Index health and responder status |

### OCR
| Method | Path | Rate Limit | Cached | Description |
|--------|------|------------|--------|-------------|
| POST | `/ocr/` | 20/min | Yes | OCR invoice (base64) |
| POST | `/ocr/upload` | 20/min | Yes | Upload + OCR + classify |
| POST | `/ocr/async` | 30/min | No | Submit async OCR job |
| POST | `/ocr/async/upload` | 20/min | No | Upload + submit async OCR |
| GET | `/ocr/async/{task_id}/status` | — | — | Check async task status |
| GET | `/ocr/async/{task_id}/result` | — | — | Get async task result |

### Upload
| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| POST | `/upload/` | 10/min | Upload invoice + OCR + compliance check + save |
| POST | `/upload/compliance-check` | 20/min | Quick compliance check without saving |

### WhatsApp
| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| POST | `/whatsapp/webhook` | 30/min | Twilio webhook endpoint |

### Compliance
| Method | Path | Description |
|--------|------|-------------|
| GET | `/compliance/itc/{category}` | Check ITC eligibility |
| GET | `/compliance/deadlines/{period}` | Get filing deadlines |
| GET | `/compliance/penalty/{type}/{days}/{tax}` | Calculate late filing penalty |
| POST | `/compliance/liability` | Calculate GST liability |

### GSTIN
| Method | Path | Description |
|--------|------|-------------|
| GET | `/gstin/validate/{gstin}` | Validate GSTIN format + Modulo36 checksum |

### Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard/stats` | Dashboard statistics |
| GET | `/api/clients` | List all clients |
| POST | `/api/clients` | Add a client |
| GET | `/api/clients/{id}` | Get client detail with invoices |
| POST | `/api/clients/{id}/remind` | Send WhatsApp filing reminder (5/min) |
| GET | `/api/invoices` | List all invoices |
| POST | `/api/invoices/{id}/approve` | Approve invoice |
| POST | `/api/invoices/{id}/reject` | Reject invoice |
| GET | `/api/alerts` | Get filing alerts |
| GET | `/api/admin/stats` | Admin system stats |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check with scheduler status |
| GET | `/api/alerts/trigger-test` | Trigger alert job manually |

## Database Schema

Managed via **Alembic migrations** (runs `Base.metadata.create_all()` as fallback on startup).

```bash
cd backend
alembic upgrade head        # Apply all pending migrations
alembic downgrade -1        # Rollback one step
alembic revision --autogenerate -m "description"  # Create new migration
```

8 tables defined in `app/models/base.py`:

- `ca_partners` — CA accounts (auth, JWT)
- `users` — WhatsApp users (clients)
- `invoices` — Extracted invoice data
- `gst_ledger` — Monthly ITC tracking
- `filing_history` — GST return filings
- `alerts` — Deadline alerts
- `transactions` — Bank statement transactions
- `gstr2b_cache` — GSTR-2B supplier cache

## Tests

```bash
cd backend
python -m pytest tests/ -q
# 103 passed
```

| Test file | Tests | Coverage |
|---|---|---|
| `conftest.py` | fixture | SQLite DB, mock env vars, sys.path setup |
| `test_compliance_engine.py` | 59 | Section 17(5), penalty, liability, deadlines, GSTIN |
| `test_auth_routes.py` | 8 | Signup, login, token refresh, auth guards |
| `test_gstmind_route.py` | 11 | Route-level (mock index + responder) |
| `test_gstmind_index.py` | 10 | ChromaDB build, query, persist, cleanup |
| `test_gstmind_responder.py` | 9 | Claude API, insufficient context, error handling |
| `test_dashboard_routes.py` | 3 | Dashboard auth guards |
| `test_ocr_routes.py` | 3 | OCR upload validation |

All tests run in CI on every push/PR to `main` (GitHub Actions, ubuntu-latest, SQLite).

## ML Stack

| Component | Model | Purpose |
|---|---|---|
| OCR | google/gemini-2.0-flash-001 | Invoice field extraction |
| Classification | facebook/bart-large-mnli | Zero-shot GST category detection |
| Fine-tuned | meet136/indicbert-gst-classifier | XLM-RoBERTa GST classifier v1 |
| Legal Retrieval | meet136/gst-legal-embeddings-v1 | 4970 pairs, MNRL, 8 epochs, 994 chunks |
| RAG Generator | claude-sonnet-4-20250514 | Answer with citations |
| Vector Store | ChromaDB | 994 indexed chunks |
| Chunker | LegalChunker | Section → Sub-section → Clause → Proviso |

## Training Data

7,229 synthetic multilingual invoice descriptions (5,353 train / 1,876 test) generated via:
- **46%** Claude Sonnet — diverse category coverage with Indian business vocabulary
- **23%** DeepSeek — complementary descriptions with Hindi-English code-mixing
- **31%** Template — rule-based fallback with multilingual token insertion (Hindi, Gujarati, English)

Labels: Clothing, Electronics, Food, Pharma, Travel, Vehicle, Office. Synthetic data is toy-separable; real-world F1 will be lower.

## Data Pipeline

```
CGST Act PDF (1.4MB)       CBIC Circulars (seed data)
         ↓                          ↓
  parse_cgst_act.py         seed_circulars.py
         ↓                          ↓
  98 parsed sections        21 circular metadata files
         ↓                          ↓
  build_citation_graph.py ── section→circular mappings
         ↓
  legal_chunker.py
         ↓
  994 chunks (all_chunks.jsonl)
         ↓
  build_chroma_index.py
         ↓
  ChromaDB (data/chromadb/)
```

## GSTMind Benchmark Results

Evaluation against 30 hand-crafted GST QA pairs (994 chunks):

| Model | Section Recall@1 | Avg Keyword Recall | Avg Score |
|-------|-----------------|-------------------|-----------|
| e5-small (zero-shot) | 37% (11/30) | 0.475 | 0.918 |
| meet136/gst-legal-embeddings-v1 | 20% (6/30) | 0.242 | 0.721 |

**Retrieved correctly by v2:** Time of supply (s12), penalty no invoice (s122), penalty late filing (s47), penalty waiver (s126), transition (s140), matching (s42)

**Missed due to data gaps:** 18 questions reference sections never parsed from the government PDF (s2, s9, s18, s22, s49, s62, s107, etc.) — these are not retrieval failures.

Run the benchmark yourself:
```bash
python ml/evaluation/benchmark.py --db data/chromadb --verbose
```

## Known Limitations

- **Classifier F1=1.00** is a data artifact — synthetic training data, not real-world performance
- **CBIC scraper** may fail on some circulars (government site inconsistency)
- **PDF parsing** extracted only 97/174 sections (multi-column government PDF layout)
- **Contamination** in sections 1 and 3 (merged text across section boundaries)
- **21 circulars** indexed (seed data; cbic-gst.gov.in connection resets from current network)
- **Eval set** is 200 pairs from same synthetic distribution as training. Real-world MRR will differ.
- **Render free tier** has 30-60s cold start and 512MB RAM — embedding model loaded lazily; switch to `all-MiniLM-L6-v2` (~80MB) if OOM
- **OCR status polling** endpoints (`/ocr/status/{task_id}`, `/ocr/result/{task_id}`) are unauthenticated (intentional for polling UX)
- **Live keys in git history** — rotate all credentials before production (commits `6146fa3`, `6020f4b`)

## Contact

- GitHub: [@meetmehta136](https://github.com/meetmehta136)
- Model: [meet136/indicbert-gst-classifier](https://huggingface.co/meet136/indicbert-gst-classifier) (based on XLM-RoBERTa)
