# VyapaarBandhu 🤝
> AI-Powered GST Compliance Assistant for Indian Small Businesses

## 🏗️ Architecture
```
WhatsApp → Twilio Webhook → FastAPI Backend → PostgreSQL
                         ↓
              OpenRouter VLM (invoice OCR)
              HuggingFace IndicBERT (GST classifier)
              Compliance Engine (Pure Python)
                         ↓
              CA Dashboard (React + Vite + Tailwind)
```

## 📁 Project Structure
```
vyapaar-bandhu/
├── backend/              # FastAPI Python app
│   ├── app/
│   │   ├── main.py      # FastAPI entry point
│   │   ├── routes/      # API routes (auth, whatsapp, ocr, upload, compliance, dashboard)
│   │   ├── models/      # SQLAlchemy models
│   │   ├── services/    # OCR, classification, compliance engine
│   │   └── core/        # Database, auth utils
│   ├── requirements.txt
│   └── Dockerfile
├── vyapaarbandhu-ca-elite/  # React frontend (CA Dashboard)
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml   # Orchestrates all services
└── .env                 # Environment variables (copy from .env.example)
```

## 🚀 Quick Start (Docker - Recommended)

### Prerequisites
- Docker Desktop installed and running
- Docker Compose v2+

### 1. Setup Environment
```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your API keys (see section below)
```

### 2. Start All Services
```bash
docker-compose up --build
```

This starts:
- **PostgreSQL** on port `5433`
- **FastAPI Backend** on port `8000`
- **React Frontend** on port `3000`

### 3. Access the Applications
- **CA Dashboard**: http://localhost:3000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

## 🔧 Manual Setup (Without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables (or create .env file)
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/vyapaar_bandhu"
export OPENROUTER_API_KEY="your_key"
export HF_API_KEY="your_key"

# Run
cd backend
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd vyapaarbandhu-ca-elite
npm install
npm run dev
```

## 🔑 Required API Keys

| Service | Purpose | Get Key From |
|---------|---------|--------------|
| OpenRouter | Invoice OCR (VLM) | https://openrouter.ai/keys |
| HuggingFace | GST Classification | https://huggingface.co/settings/tokens |
| Twilio | WhatsApp Bot | https://console.twilio.com/ |

## 📱 Testing WhatsApp Flow Locally

### 1. Setup Twilio Sandbox
1. Go to https://console.twilio.com/ → Messaging → Try it out → Send a WhatsApp message
2. Join the sandbox by sending the code to the WhatsApp number shown
3. Note your Twilio phone number (starts with `whatsapp:+141...`)

### 2. Configure Webhook
1. In Twilio Console → Messaging → Settings → WhatsApp Sandbox Settings
2. Set "When a message comes in" webhook to: `https://your-ngrok-url/whatsapp/webhook`
   
   **For local testing, use ngrok:**
   ```bash
   # In a new terminal
   ngrok http 8000
   # Copy the https URL and add /whatsapp/webhook
   ```

### 3. Test the Flow
1. Send "hello" to the Twilio WhatsApp number
2. Send an invoice photo
3. Bot replies with extracted GST data and compliance result
4. View the invoice in the CA Dashboard at http://localhost:3000

## 📊 CA Dashboard Features

- **Dashboard**: ITC trends, client risk distribution, WhatsApp activity feed
- **Clients**: List all clients with compliance status (pass/fail/warning)
- **Client Detail**: View uploaded invoices per client with GST data
- **Invoices**: All invoices with AI classification and compliance status
- **Alerts**: Filing deadline alerts and ITC leakage warnings
- **Admin**: System stats and user management

## 🔗 API Endpoints

### Auth
- `POST /auth/signup` - Register CA account
- `POST /auth/login` - Login
- `GET /auth/me` - Get current CA profile

### OCR & Upload
- `POST /ocr/` - OCR invoice image (base64)
- `POST /upload/` - Upload invoice image file
- `POST /upload/compliance-check` - Quick compliance check without saving

### WhatsApp
- `POST /whatsapp/webhook` - Twilio webhook endpoint

### Compliance
- `GET /compliance/itc/{category}` - Check ITC eligibility
- `GET /compliance/deadlines/{period}` - Get filing deadlines
- `POST /compliance/liability` - Calculate GST liability

### Dashboard
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/clients` - List all clients
- `GET /api/clients/{id}` - Get client detail with invoices
- `GET /api/invoices` - List all invoices
- `POST /api/invoices/{id}/approve` - Approve invoice
- `POST /api/invoices/{id}/reject` - Reject invoice

## �️ Database Schema

Tables auto-created on startup:
- `users` - WhatsApp users
- `ca_partners` - CA accounts
- `invoices` - Extracted invoice data
- `gst_ledger` - Monthly ITC tracking
- `filing_history` - GST return filings
- `alerts` - Deadline alerts
- `transactions` - Bank statement transactions

## 🛠️ Troubleshooting

### Database connection failed
```bash
# Check if Postgres is running
docker-compose ps

# View logs
docker-compose logs db
```

### OCR not working
- Verify `OPENROUTER_API_KEY` is set correctly
- Check backend logs: `docker-compose logs backend`

### WhatsApp messages not received
- Verify Twilio webhook URL is accessible
- Check ngrok is running for local testing
- Verify `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`

### Frontend can't connect to backend
- Ensure backend is running on port 8000
- Check `VITE_API_URL` environment variable
- Check browser console for CORS errors

## 🤖 ML Stack

| Component | Model | Purpose |
|---|---|---|
| OCR | nvidia/nemotron-nano-12b-v2-vl | Invoice field extraction |
| Classification | facebook/bart-large-mnli | Zero-shot GST category detection |
| Fine-tuned | meet136/indicbert-gst-classifier | Custom GST classifier v1 |
| Fine-tuned | meet136/muril-gst-classifier-v2 | Custom GST classifier v2 (MuRIL) |

**Note on classifier metrics:** F1=1.00 reported on the validation set is a known data
artifact — the training data is synthetically generated. This does not reflect
real-world performance. The v2 classifier has been replaced by the GSTMind RAG
pipeline for production use. See Known Limitations below.

## Known Limitations
- IndicBERT v1 / MuRIL v2 classifiers were trained on synthetic data.
  Reported F1 scores reflect the training distribution, not real-world performance.
  These are being replaced by GSTMind for production use.
- CBIC URL scraper may fail on a subset of circulars due to government site
  inconsistency. This is acknowledged in the data pipeline.
- Embedding evaluation uses held-out pairs from the same synthetic distribution.
  Real-world MRR will differ.
- Render free tier has cold start latency of 30-60 seconds on first request
  and 512MB RAM — insufficient for loading large embedding models inline.
  GSTMind degrades gracefully when memory is constrained.

## 📬 Contact
- GitHub: [@meetmehta136](https://github.com/meetmehta136)
- Model: [meet136/indicbert-gst-classifier](https://huggingface.co/meet136/indicbert-gst-classifier)

