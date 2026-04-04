# VyapaarBandhu 🤝
> AI-Powered GST Compliance Assistant for Indian Small Businesses

[![Live API](https://img.shields.io/badge/API-Live-success)](https://vyapaar-bandhu-h53q.onrender.com/docs)
[![Dashboard](https://img.shields.io/badge/Dashboard-Live-blue)](https://vyapaar-bandhu.vercel.app)
[![HuggingFace](https://img.shields.io/badge/Model-HuggingFace-yellow)](https://huggingface.co/meet136/indicbert-gst-classifier)
[![Built Solo](https://img.shields.io/badge/Built-Solo%208%20Weeks-orange)]()

## 🎯 Problem
8 crore Indian SMEs spend ₹2,000–₹5,000/month on basic GST compliance. Missing a deadline = ₹50/day penalty. Most shopkeepers don't have an accountant on payroll.

## 💡 Solution
WhatsApp-native GST compliance — photograph an invoice, get ITC calculated + AI-classified instantly. No app to install. Zero learning curve.

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
│   │   ├── pages/            # Dashboard, Clients, Invoices, AIInsights, Admin
│   │   ├── components/       # UI components, charts, sidebar
│   │   └── lib/              # API client
│   └── package.json
```

## ✨ Features

### 📱 WhatsApp Bot
- Invoice OCR in under 20 seconds
- **AI classification shown in confirmation message** — user sees category, confidence %, and ITC amount *before* confirming
- Duplicate invoice detection
- Bank PDF parser (HDFC, SBI, ICICI, Axis, Kotak)
- Monthly GST summary on demand
- Deadline reminders at 7, 3, 1 days

### 🧠 AI Classification Engine
- Fine-tuned **IndicBERT** on 1,995 real Indian SME transactions
- 7 GST categories: Food, Capital Goods, Services, Exempt, Blocked, Mixed, Other
- **Section 17(5) blocked category detection** — flags ineligible ITC automatically
- Confidence score returned with every classification
- Keyword extraction shown to user ("Detected: SUGAR, KATTA, 50KG")
- **User correction loop** — low-confidence invoices show correction dropdown; corrections stored for future model improvement
- Classification runs at scan time, not after save — zero added latency to confirmation

### 📊 CA Dashboard
- **AI Classification Breakdown card** — ITC by category, avg confidence, blocked vs eligible
- **Confidence bar per invoice** — visual indicator on every row
- **AI reasoning display** — keywords that triggered the classification
- ITC Trend chart (monthly, from real data)
- Client Risk Distribution (pie chart)
- WhatsApp Activity Feed
- AI Deadline Risk predictor
- ITC Leakage Report (Section 17(5) analysis)
- Supplier GSTIN risk analysis
- Invoice Anomaly Detection (2.5x avg value flagging)
- Admin Panel — revenue metrics, all users, system health

### ⚖️ Compliance Engine
- 100% pure Python, zero AI calls, hardcoded from GST Act
- GSTR-3B and GSTR-1 deadline calculation
- ITC eligibility rules enforcement
- RCM (Reverse Charge Mechanism) detection

## 🤖 ML Stack
| Component | Model | Purpose |
|---|---|---|
| OCR | nvidia/nemotron-nano-12b-v2-vl | Invoice field extraction |
| Classification (v1) | facebook/bart-large-mnli | Zero-shot baseline |
| Classification (v2) | [meet136/indicbert-gst-classifier](https://huggingface.co/meet136/indicbert-gst-classifier) | Fine-tuned on 1,995 Indian SME transactions |

## 📊 Performance
- OCR Accuracy: **87.5%** on real blurry Indian invoices
- Classifier F1: **1.00** across all 7 GST categories (validation set)
- WhatsApp response: **< 20 seconds** end-to-end
- Cost per user: **₹24/month**
- Gross margin: **92%** at 500 users

## 🛠️ Tech Stack
- **Backend:** FastAPI, PostgreSQL, SQLAlchemy, Pydantic, ReportLab, APScheduler
- **Frontend:** React, TypeScript, Tailwind, Recharts, Vercel
- **AI/ML:** OpenRouter VLM, HuggingFace Inference API, IndicBERT (fine-tuned)
- **Infra:** Render, Vercel, Twilio WhatsApp API

## 🗄️ Database Schema
8 ACID-compliant PostgreSQL tables:
`users` · `invoices` · `gst_ledger` · `filing_history` · `alerts` · `ca_partners` · `transactions` · `gstr2b_cache`

Invoice table includes AI fields: `ai_category` · `ai_confidence` · `ai_keywords` · `user_corrected`

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


## 📬 Contact
- GitHub: [@meetmehta136](https://github.com/meetmehta136)
- HuggingFace: [meet136](https://huggingface.co/meet136)
- Model: [meet136/indicbert-gst-classifier](https://huggingface.co/meet136/indicbert-gst-classifier)