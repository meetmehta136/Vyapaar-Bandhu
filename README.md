# VyapaarBandhu 🤝
> AI-Powered GST Compliance Assistant for Indian Small Businesses

[![Live API](https://img.shields.io/badge/API-Live-success)](https://vyapaar-bandhu-h53q.onrender.com/docs)
[![Dashboard](https://img.shields.io/badge/Dashboard-Live-blue)](https://vyapaar-bandhu.vercel.app)
[![HuggingFace](https://img.shields.io/badge/Model-HuggingFace-yellow)](https://huggingface.co/meet136/indicbert-gst-classifier)
[![Built Solo](https://img.shields.io/badge/Built-Solo%208%20Weeks-orange)]()

## 🎯 Problem
8 crore Indian SMEs spend ₹2,000–₹5,000/month on basic GST compliance. Missing a deadline = ₹50/day penalty. Most shopkeepers don't have an accountant on payroll.

## 💡 Solution
WhatsApp-native GST compliance — send an invoice photo, get ITC calculated instantly. No app to install. Zero learning curve.

## 🏗️ Architecture
```
WhatsApp → Twilio → FastAPI Backend → PostgreSQL
                         ↓
              OpenRouter VLM (OCR)
              meet136/indicbert-gst-classifier (Classification)
              Compliance Engine (Pure Python)
                         ↓
              CA Dashboard (React + Vercel)
```

## 📁 Repository Structure
```
Vyapaar-Bandhu/
├── backend/                  # FastAPI backend (deployed on Render)
│   ├── app/
│   │   ├── main.py           # App entry point + APScheduler
│   │   ├── routes/           # whatsapp, dashboard, auth, compliance
│   │   ├── services/         # OCR, classification, invoice, GSTIN validator
│   │   └── models/           # SQLAlchemy models
│   └── requirements.txt
├── vyapaarbandhu-ca-elite/   # React frontend (deployed on Vercel)
│   ├── src/
│   │   ├── pages/            # Dashboard, Clients, Invoices, Admin
│   │   ├── components/       # UI components, charts, sidebar
│   │   └── lib/              # API client
│   └── package.json
└── frontend/                 # Legacy frontend folder
```

## ✨ Features
- 📱 **WhatsApp Bot** — invoice OCR in under 20 seconds
- 🧠 **AI Classification** — Section 17(5) ITC eligibility detection
- ⚖️ **Compliance Engine** — 100% pure Python, zero AI calls, hardcoded from GST Act
- 🏦 **Bank PDF Parser** — HDFC, SBI, ICICI, Axis, Kotak
- 📊 **CA Dashboard** — traffic light system, AI insights, filing PDFs
- 🔍 **ITC Leakage Detection** — flags blocked category invoices automatically
- 🛡️ **Admin Panel** — revenue metrics, all users, system health

## 🤖 ML Stack
| Component | Model | Purpose |
|---|---|---|
| OCR | nvidia/nemotron-nano-12b-v2-vl | Invoice field extraction |
| Classification (v1) | facebook/bart-large-mnli | Zero-shot baseline |
| Classification (v2) | [meet136/indicbert-gst-classifier](https://huggingface.co/meet136/indicbert-gst-classifier) | Fine-tuned on 1995 Indian SME transactions |

## 📊 Performance
- OCR Accuracy: **87.5%** on real blurry Indian invoices
- Classifier F1: **1.00** across all 7 GST categories (validation set)
- WhatsApp response: **< 20 seconds**
- Cost per user: **₹24/month**
- Gross margin: **92%** at 500 users

## 🛠️ Tech Stack
- **Backend:** FastAPI, PostgreSQL, SQLAlchemy, Pydantic, ReportLab
- **Frontend:** React, TypeScript, Tailwind, Recharts, Vercel
- **AI/ML:** OpenRouter VLM, HuggingFace Inference API, XLM-RoBERTa
- **Infra:** Render, Vercel, Twilio WhatsApp API

## 🚀 Live Demo
- API Docs: https://vyapaar-bandhu-h53q.onrender.com/docs
- CA Dashboard: https://vyapaar-bandhu.vercel.app
- ML Model: https://huggingface.co/meet136/indicbert-gst-classifier

## 📦 Run Locally

**Backend:**
```bash
git clone https://github.com/meetmehta136/Vyapaar-Bandhu
cd backend
pip install -r requirements.txt
cp .env.example .env  # add your API keys
docker run --name vyapaar-postgres -e POSTGRES_PASSWORD=postgres -p 5433:5432 -d postgres
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd vyapaarbandhu-ca-elite
npm install
echo "VITE_API_URL=https://vyapaar-bandhu-h53q.onrender.com" > .env
npm run dev
```

## 🗄️ Database Schema
8 ACID-compliant PostgreSQL tables:
`users` · `invoices` · `gst_ledger` · `filing_history` · `alerts` · `ca_partners` · `transactions` · `gstr2b_cache`

## 💰 Business Model
| Plan | Target |
|---|---|
| Consumer | Individual SMEs |
| CA Partner | CA firms (40+ clients each) |

## 📬 Contact
- GitHub: [@meetmehta136](https://github.com/meetmehta136)
- HuggingFace: [meet136](https://huggingface.co/meet136)
- Model: [meet136/indicbert-gst-classifier](https://huggingface.co/meet136/indicbert-gst-classifier)