# GSTMind Build Progress
Last session completed: 1
Current session: 1

## Session 1 — README Honesty Fix
**Status**: Completed
**Date**: 2026-05-25

### Key Actions
- Added "Note on classifier metrics" below ML Stack table — warns that F1=1.00 is a synthetic data artifact
- Added "Known Limitations" section (4 items: classifiers, CBIC scraper, eval set, Render 512MB)
- Added meet136/muril-gst-classifier-v2 to ML Stack table

### Warnings / To-dos
- None

### Next Session
- Session 2: Compliance engine tests (pytest, 20+ tests, 60%+ coverage)

---

## Session State

| Session | Status | Date | Key Outputs | Notes |
|---------|--------|------|-------------|-------|
| 0 | Completed | 2026-05-25 | .gitignore fix, docs/PROGRESS.md | Keys in git history — rotate! |
| 1 | Completed | 2026-05-25 | README — Known Limitations section | — |
| 2 | Pending | — | — | Compliance engine tests |
| 2 | Pending | — | — | Compliance engine tests |
| 3 | Pending | — | — | CBIC data pipeline |
| 4 | Pending | — | — | Legal chunker |
| 5 | Pending | — | — | Embedding fine-tuning (Colab) |
| 6 | Pending | — | — | ChromaDB + RAG pipeline |
| 7 | Pending | — | — | GSTMind API integration |
| 8 | Pending | — | — | GST-QA benchmark |
| 9 | Pending | — | — | Model card + README update |
| 10 | Pending | — | — | Async OCR + Redis cache |
| 11 | Pending | — | — | Security hardening |
| 12 | Pending | — | — | Alembic migrations |
| 13 | Pending | — | — | GitHub Actions CI |
| 14 | Pending | — | — | Structured logging |
| 15 | Pending | — | — | Final README rewrite |

## Global Constraints
- Render free tier: 512MB RAM — GSTMind must degrade gracefully if OOM
- All API keys stored in backend/.env (now gitignored; keys still in git history — rotate!)
- CBIC scraper: best-effort, seed manually if site changes
- Session expiry: always read this file first, mark current session, continue
