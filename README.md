# VyapaarBandhu
> **AI-Powered GST Compliance Assistant for Indian Small Businesses**

Built for **OceanLab × CHARUSAT Hacks 2026** — a full-stack AI system that brings legal intelligence, async OCR, and WhatsApp-native compliance to CA firms and their SMB clients.

**103 pytest cases · RAG pipeline (ChromaDB + Claude Sonnet) · Async OCR with Redis · CI/CD (GitHub Actions) · Alembic migrations · Structured logging (Loguru)**

| Layer | Live URL |
|---|---|
| Landing Page | https://vyapaar-bandhu-web.vercel.app |
| CA Dashboard | https://vyapaarbandhu-ca-elite.vercel.app |
| REST API (Swagger) | https://vyapaar-bandhu-h53q.onrender.com/docs |

---

## Why VyapaarBandhu?

Indian SMBs lose thousands of rupees annually to GST penalties — not because they intend to default, but because the CGST Act is 174 sections of dense legalese. VyapaarBandhu puts a compliance engine directly on WhatsApp: CAs get a React dashboard for centralized client management; their clients get OCR-powered invoice processing and cited legal answers — all without leaving the app they already use.

---

## System Architecture

```
WhatsApp → Twilio Webhook → FastAPI Backend → PostgreSQL
                         ↓
              ┌─ Intelligence Layer ────────────────────────┐
              │  OpenRouter VLM (Gemini Flash — invoice OCR)│
              │  HuggingFace XLM-RoBERTa (GST classifier)  │
              │  Compliance Engine (Pure Python rules)      │
              └────────────────────────────────────────────┘
                         ↓
              ┌─ GSTMind RAG Pipeline ──────────────────────┐
              │  Query → Embed (multilingual-e5-small)      │
              │        → ChromaDB (994 indexed sections)    │
              │        → Claude Sonnet (answer + citations) │
              └────────────────────────────────────────────┘
                         ↓
              ┌─ Infrastructure ───────────────────────────┐
              │  Rate limiting (slowapi) per endpoint       │
              │  Security headers · Input sanitization      │
              │  File validation · CORS (env-configurable)  │
              │  Redis OCR cache (SHA-256, 1hr TTL)         │
              │  Alembic schema migrations                  │
              │  GitHub Actions CI (lint + 103 tests)       │
              │  Structured logging via loguru              │
              └────────────────────────────────────────────┘
                         ↓
              CA Dashboard (React + Vite + Tailwind CSS)
```

---

## Repository Structure

```
vyapaar-bandhu/
├── backend/                        # FastAPI application
│   ├── app/
│   │   ├── main.py                 # Entry point
│   │   ├── routes/                 # auth, gstmind, whatsapp, ocr, upload, compliance
│   │   ├── models/                 # SQLAlchemy (8 tables)
│   │   ├── services/               # OCR, classifier, GSTMind, invoice, PDF parser
│   │   └── core/                   # DB config, auth, security, logging
│   ├── tests/                      # 103 pytest cases (7 modules + conftest)
│   ├── alembic/                    # Migration scripts
│   ├── requirements.txt            # Production: chromadb, redis, slowapi, loguru
│   ├── requirements-dev.txt        # Dev: pytest, ruff
│   ├── pyproject.toml              # Ruff lint config
│   └── Dockerfile
├── vyapaarbandhu-ca-elite/         # React CA Dashboard
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── ml/                             # ML assets and data pipeline
│   ├── data/                       # Chunks, citation graph, parsed sections
│   ├── data_pipeline/              # Scraper, PDF parser, chunker, QA generator
│   ├── notebooks/                  # Colab: embedding fine-tuning
│   ├── evaluation/                 # 30-question benchmark + runner
│   ├── models/                     # HuggingFace-style model card
│   └── scripts/                    # build_chroma_index.py CLI
├── .github/workflows/              # CI: lint (ruff) + test (pytest)
├── docker-compose.yml
├── SECURITY.md
├── docs/PROGRESS.md
└── .env
```

---

## Quick Start (Docker)

### Prerequisites
- Docker Desktop running
- Docker Compose v2+

### 1. Configure Environment
```bash
cp .env.example .env
# Fill in API keys (see Required API Keys section below)
```

### 2. Start All Services
```bash
docker-compose up --build
```

Starts: **PostgreSQL** (port 5433) · **FastAPI** (port 8000) · **React** (port 3000)

### 3. Apply Database Migrations
```bash
docker exec -it vyapaarbandhu-backend-1 alembic upgrade head
```

### 4. Build the GSTMind Vector Index
```bash
cd backend
pip install -r requirements.txt
python ../ml/scripts/build_chroma_index.py \
    --chunks ../ml/data/processed/all_chunks.jsonl \
    --db data/chromadb \
    --model intfloat/multilingual-e5-small
```

### 5. Access
| Service | URL |
|---|---|
| CA Dashboard | http://localhost:3000 |
| API Swagger Docs | http://localhost:8000/docs |
| GSTMind Status | http://localhost:8000/api/gstmind/status |
| Health Check | http://localhost:8000/health |

---

## Manual Setup (Without Docker)

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Required environment variables
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/vyapaar_bandhu"
export OPENROUTER_API_KEY="your_key"
export HF_API_KEY="your_key"
export ANTHROPIC_API_KEY="your_key"
export JWT_SECRET="your-secret-key-min-32-chars"
export GSTMIND_DB_PATH="data/chromadb"

# Migrate then build index then serve
alembic upgrade head
python ../ml/scripts/build_chroma_index.py
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd vyapaarbandhu-ca-elite
npm install && npm run dev
```

---

## Required API Keys

| Service | Purpose | Where to Get |
|---|---|---|
| OpenRouter | Invoice OCR (Gemini Flash VLM) | https://openrouter.ai/keys |
| HuggingFace | GST category classification | https://huggingface.co/settings/tokens |
| Anthropic | GSTMind RAG (Claude Sonnet) | https://console.anthropic.com |
| Twilio | WhatsApp bot webhook | https://console.twilio.com |
| Redis *(optional)* | OCR result caching | Set `REDIS_URL`; falls back to in-memory |

### Optional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `""` | Redis connection string (in-memory fallback if unset) |
| `OCR_CACHE_TTL` | `3600` | Cache TTL in seconds |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `GSTMIND_DB_PATH` | `data/chromadb` | ChromaDB persistence path |
| `GSTMIND_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Embedding model |

---

## GSTMind — Legal RAG Engine

GSTMind is the core intelligence of VyapaarBandhu. It answers GST compliance questions with **section-level citations** from the CGST Act, 2017 and CBIC circulars.

### Pipeline

```
User Question
     ↓
  Embed  →  multilingual-e5-small (cosine similarity)
     ↓
  ChromaDB  →  top-15 dense recall → section dedup → top-5
     ↓
  Claude Sonnet  →  answer with inline citations
     ↓
  Structured JSON response
```

### API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/gstmind/ask` | Query engine (`{"query": "...", "top_k": 5}`) |
| `GET` | `/api/gstmind/status` | Index health + responder status |

### Example

```bash
curl -X POST http://localhost:8000/api/gstmind/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "When is ITC blocked?"}'
```

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

---

## Async OCR with Redis Caching

Invoice processing via OpenRouter VLM supports both sync and async modes with optional Redis caching that brings repeated invoice lookups from ~10s down to ~50ms.

### Async Flow

```
POST /ocr/async  ──→  { task_id: "abc123", status: "pending" }
                            ↓  (background worker)
                       OpenRouter VLM processing...
                            ↓
GET /ocr/async/{task_id}/status  ──→  { status: "done" }
GET /ocr/async/{task_id}/result  ──→  { fields: {...}, confidence: 0.92 }
```

**Design decisions:**
- In-memory task store (ephemeral — acceptable on Render free tier)
- Redis cache keyed on SHA-256 file hash, 1-hour TTL, graceful in-memory fallback
- Sync endpoints (`POST /ocr/`) also benefit from cache — cache hit returns in ~50ms

---

## Security

### Rate Limits (slowapi)

| Endpoint | Limit |
|---|---|
| Global (all endpoints) | 60/min per IP |
| `POST /auth/login` | 10/min |
| `POST /auth/signup` | 5/min |
| `POST /ocr/*` | 20/min |
| `POST /upload/*` | 10–20/min |
| `POST /whatsapp/webhook` | 30/min |
| `POST /api/clients/{id}/remind` | 5/min |

### Input Validation
- HTML escaping, script-tag removal, 10K character truncation on all text inputs
- File MIME types restricted to `image/jpeg`, `image/png`, `image/webp`, `application/pdf`; max 10MB

### HTTP Security Headers
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Cache-Control: no-store
```

### Known Gaps *(see SECURITY.md)*
- OCR status/result polling endpoints are intentionally unauthenticated (polling UX trade-off)
- 30-day JWT lifetime
- API keys present in git history — **rotate all credentials before production** (commits `6146fa3`, `6020f4b`)

---

## CI/CD Pipeline

| Trigger | Jobs |
|---|---|
| Push / PR to `main` | `ruff check .` (lint) + `pytest tests/` (103 tests) |

- **Runtime:** ubuntu-latest, Python 3.11, SQLite test database
- **HuggingFace model cache** warmed (~120MB sentence-transformers)
- **Concurrency:** cancel-in-progress for redundant runs
- **Lint** runs with `continue-on-error: true` (non-blocking)

---

## Structured Logging

All logs route through **loguru** (no bare `print()` calls). 62 print statements replaced across 9 files.

```
2026-05-25 14:30:00 | INFO  | ocr_service:parse_invoice_with_openrouter:47  - Sending to OpenRouter VLM...
2026-05-25 14:30:02 | INFO  | ocr_service:parse_invoice_with_openrouter:119 - OpenRouter status: 200
2026-05-25 14:30:02 | ERROR | ocr_service:parse_invoice_with_openrouter:122 - OpenRouter error: 401
```

- Log level configurable via `LOG_LEVEL` env var
- FastAPI, uvicorn, and alembic logs intercepted and unified through loguru
- Backtrace enabled; `diagnose=False` for production safety

---

## API Reference

### Auth
| Method | Path | Rate Limit | Description |
|---|---|---|---|
| POST | `/auth/signup` | 5/min | Register CA account |
| POST | `/auth/login` | 10/min | Login, returns JWT |
| GET | `/auth/me` | — | Current CA profile |
| PUT | `/auth/profile` | — | Update CA profile |

### GSTMind
| Method | Path | Description |
|---|---|---|
| POST | `/api/gstmind/ask` | GST compliance Q&A with citations |
| GET | `/api/gstmind/status` | Index health and responder status |

### OCR
| Method | Path | Rate Limit | Cached | Description |
|---|---|---|---|---|
| POST | `/ocr/` | 20/min | ✓ | OCR invoice (base64 payload) |
| POST | `/ocr/upload` | 20/min | ✓ | Upload file → OCR → classify |
| POST | `/ocr/async` | 30/min | — | Submit async OCR job |
| POST | `/ocr/async/upload` | 20/min | — | Upload file → async OCR |
| GET | `/ocr/async/{task_id}/status` | — | — | Poll job status |
| GET | `/ocr/async/{task_id}/result` | — | — | Retrieve result |

### Upload
| Method | Path | Rate Limit | Description |
|---|---|---|---|
| POST | `/upload/` | 10/min | Upload → OCR → compliance check → persist |
| POST | `/upload/compliance-check` | 20/min | Quick check without saving |

### Compliance
| Method | Path | Description |
|---|---|---|
| GET | `/compliance/itc/{category}` | ITC eligibility check |
| GET | `/compliance/deadlines/{period}` | Filing deadline lookup |
| GET | `/compliance/penalty/{type}/{days}/{tax}` | Late-filing penalty calculator |
| POST | `/compliance/liability` | GST liability computation |

### GSTIN
| Method | Path | Description |
|---|---|---|
| GET | `/gstin/validate/{gstin}` | Format + Modulo-36 checksum validation |

### Dashboard & Clients
| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/stats` | Aggregate dashboard metrics |
| GET | `/api/clients` | List all clients |
| POST | `/api/clients` | Add client |
| GET | `/api/clients/{id}` | Client detail with invoices |
| POST | `/api/clients/{id}/remind` | Send WhatsApp filing reminder (5/min) |
| GET | `/api/invoices` | List all invoices |
| POST | `/api/invoices/{id}/approve` | Approve invoice |
| POST | `/api/invoices/{id}/reject` | Reject invoice |
| GET | `/api/alerts` | Active filing alerts |
| GET | `/api/admin/stats` | System-wide admin stats |

### System
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check with scheduler status |
| GET | `/api/alerts/trigger-test` | Manually trigger alert job |

---

## Database Schema

8 tables managed via Alembic. `Base.metadata.create_all()` runs as a startup fallback.

```bash
alembic upgrade head                           # Apply migrations
alembic downgrade -1                           # Roll back one step
alembic revision --autogenerate -m "desc"      # Generate new migration
```

| Table | Purpose |
|---|---|
| `ca_partners` | CA accounts and JWT auth |
| `users` | WhatsApp clients |
| `invoices` | Extracted invoice fields |
| `gst_ledger` | Monthly ITC tracking |
| `filing_history` | GST return submissions |
| `alerts` | Deadline alert records |
| `transactions` | Bank statement entries |
| `gstr2b_cache` | GSTR-2B supplier cache |

---

## Test Suite

```bash
cd backend && python -m pytest tests/ -q
# 103 passed
```

| Module | Tests | What's Covered |
|---|---|---|
| `test_compliance_engine.py` | 59 | Section 17(5), penalties, liability, deadlines, GSTIN |
| `test_gstmind_route.py` | 11 | Route-level with mocked index and responder |
| `test_gstmind_index.py` | 10 | ChromaDB build, query, persist, cleanup |
| `test_gstmind_responder.py` | 9 | Claude API, insufficient-context paths, error handling |
| `test_auth_routes.py` | 8 | Signup, login, token validation, auth guards |
| `test_dashboard_routes.py` | 3 | Dashboard auth guards |
| `test_ocr_routes.py` | 3 | File upload validation |

All tests run in CI on every push/PR (SQLite in-memory, no external service dependencies).

---

## ML Stack

| Component | Model | Purpose |
|---|---|---|
| OCR | `google/gemini-2.0-flash-001` | Invoice field extraction |
| Zero-shot Classifier | `facebook/bart-large-mnli` | GST category detection |
| Fine-tuned Classifier | `meet136/indicbert-gst-classifier` | XLM-RoBERTa GST classifier |
| Legal Embeddings | `meet136/gst-legal-embeddings-v1` | 4,970 pairs · MNRL · 8 epochs |
| RAG Generator | `claude-sonnet-4-20250514` | Cited legal answers |
| Vector Store | ChromaDB | 994 indexed CGST chunks |
| Chunker | LegalChunker | Section → Sub-section → Clause → Proviso |

### Training Data — GST Classifier

7,229 synthetic multilingual invoice descriptions (5,353 train / 1,876 test):

| Source | Share | Notes |
|---|---|---|
| Claude Sonnet | 46% | Diverse category coverage, Indian business vocabulary |
| DeepSeek | 23% | Hindi-English code-mixed descriptions |
| Template (rule-based) | 31% | Multilingual token insertion (Hindi, Gujarati, English) |

Labels: Clothing · Electronics · Food · Pharma · Travel · Vehicle · Office

> **Caveat:** F1=1.00 is a data artifact from toy-separable synthetic data. Real-world performance will be lower.

---

## Data Pipeline

```
CGST Act PDF (1.4 MB)              CBIC Circulars (seed data)
         ↓                                    ↓
  parse_cgst_act.py              seed_circulars.py
         ↓                                    ↓
   98 parsed sections            21 circular metadata files
         ↓                                    ↓
  build_citation_graph.py  ←── section → circular mappings
         ↓
  legal_chunker.py
         ↓
  994 chunks  →  all_chunks.jsonl
         ↓
  build_chroma_index.py
         ↓
  ChromaDB  (data/chromadb/)
```

---

## GSTMind Benchmark

Evaluated against 30 hand-crafted GST QA pairs across 994 indexed chunks:

| Embedding Model | Section Recall@1 | Avg Keyword Recall | Avg Score |
|---|---|---|---|
| `e5-small` (zero-shot) | 37% (11/30) | 0.475 | 0.918 |
| `meet136/gst-legal-embeddings-v1` | 20% (6/30) | 0.242 | 0.721 |

**Correctly retrieved by fine-tuned v1:** time of supply (s12), penalty no-invoice (s122), penalty late filing (s47), penalty waiver (s126), transition (s140), matching (s42).

**Missed (18 questions):** target sections were never parsed from the government PDF — these are **data gaps**, not retrieval failures. The government PDF uses a multi-column layout that caused 77 of 174 sections to be skipped during parsing.

```bash
# Run the benchmark yourself
python ml/evaluation/benchmark.py --db data/chromadb --verbose
```

---

## Known Limitations

| Area | Limitation |
|---|---|
| Classifier F1 | F1=1.00 is a synthetic data artifact, not real-world performance |
| PDF Parsing | Extracted 97/174 CGST sections; multi-column government layout drops rest |
| Section Contamination | Sections 1 and 3 have merged text across boundaries |
| CBIC Scraper | May fail on some circulars due to government site inconsistency |
| Circulars Indexed | 21 seed circulars (cbic-gst.gov.in resets connection from current network) |
| Eval Contamination | 200-pair eval drawn from same synthetic distribution as training — real-world MRR will differ |
| Render Cold Start | 30–60s cold start; 512MB RAM — embeddings load lazily; swap to `all-MiniLM-L6-v2` (~80MB) if OOM |
| Auth on Polling | OCR status/result endpoints are intentionally unauthenticated |
| Git History | Live API keys in commits `6146fa3`, `6020f4b` — rotate all credentials before production |

---

## Contact

- **GitHub:** [@meetmehta136](https://github.com/meetmehta136)
- **HuggingFace:** [meet136/indicbert-gst-classifier](https://huggingface.co/meet136/indicbert-gst-classifier)
- **Email:** meetmehta136@gmail.com
