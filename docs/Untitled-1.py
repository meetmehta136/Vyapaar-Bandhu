cat > /home/claude/session_plan.md << 'DOCEOF'
# VyapaarBandhu: Complete Session-by-Session Execution Plan
### 1 Month | OpenCode + DeepSeek V4 Flash | No False Hope

---

## Status Check

Session 1 (Fork Resolution): DONE — manual git steps.
Session 2 (Old ML classifier): SCRAPPED — synthetic data, F1=1.00, no interview value.

Remaining: 14 sessions split across two tracks.
GSTMind (ML track): Sessions 2–8 → your interview differentiator.
Backend upgrades (SDE track): Sessions 9–15 → production credibility.

Total work time: ~14 focused days.
Remaining ~16 days: deep study of every line built + interview Q&A prep.

**Honest warning:** GSTMind Sessions 2–4 involve Colab, not OpenCode. You run them
in Google Colab on a T4 GPU. OpenCode cannot access GPU. Do not try to run embedding
fine-tuning locally — it will take 8 hours on CPU. Colab T4 takes 45 minutes free.

**Model switching rule:**
DeepSeek V4 Flash (free): Sessions 9–15 (backend, tests, CI, README).
Switch to Claude Sonnet in OpenCode: Sessions 4, 5, 6 (ML pipeline code).
Wrong code in those three sessions silently breaks your entire RAG system.

---

## TRACK 1: GSTMind (ML Differentiator)

---

### SESSION 2 — CBIC Data Pipeline
**Time:** 3–4 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**What you're building:** A Python scraper that downloads all 250 CBIC circulars as
PDFs, parses the CGST Act, and saves structured JSON for each document.

**OpenCode Prompt (copy-paste exactly):**

```
I'm building a GST legal intelligence RAG system. I need a data ingestion pipeline.

Create the following Python scripts in ml/data_pipeline/:

SCRIPT 1 — scraper.py:
Download all CBIC GST circulars from cbic-gst.gov.in.
The circular PDFs follow this URL pattern:
https://cbic-gst.gov.in/pdf/Circular-No-{N}-{YEAR}.pdf
for N from 1 to 250.
Also try pattern: https://cbic-gst.gov.in/pdf/cgst-circular-{N}.pdf

For each circular:
- Download PDF to ml/data/raw_circulars/circular_{N}.pdf
- Extract text using pdfplumber
- Extract the circular date (regex: "dated \d{2}[./-]\d{2}[./-]\d{4}")
- Extract section references (regex: [Ss]ection\s+\d+(\(\d+\))*(\([a-zA-Z]\))*)
- Save metadata to ml/data/metadata/circular_{N}.json with fields:
  circular_number, date, pdf_path, sections_referenced, raw_text

Handle HTTP errors gracefully — skip 404s, log failures to ml/data/failed_downloads.txt.
Add 1 second delay between requests to avoid rate limiting.

SCRIPT 2 — parse_cgst_act.py:
Download CGST Act from: https://cbic-gst.gov.in/pdf/CGST-Act-Updated-30012024.pdf
Save to ml/data/raw_acts/cgst_act.pdf
Extract text using pdfplumber.
Parse into sections using this regex for section headers:
^\s*(\d+)\.\s+([A-Z][^.]+)\.-

For each section found:
- Extract the full section text until the next section header
- Save as ml/data/parsed_acts/cgst_section_{N}.json with fields:
  section_number, section_title, full_text, page_start

SCRIPT 3 — build_citation_graph.py:
Load all circular metadata JSONs from ml/data/metadata/
Build a citation graph as a dictionary:
{section_number: [list of circular numbers that reference this section]}
Save to ml/data/citation_graph.json

Run all three scripts in sequence. Print progress. Show me the final file counts.
```

**After session — what to study (30 minutes):**
- Read the citation_graph.json. Find Section 17. Count how many circulars reference it.
- Open one circular PDF and one parsed section JSON. Verify the text looks correct.
- Understand what pdfplumber is and why it's better than PyPDF2 for structured text.

**What to say in interview:** "I built a PDF ingestion pipeline that scrapes 250 CBIC
circulars and the full CGST Act, parses section references using regex, and builds a
citation graph linking each circular to the sections it clarifies. This citation graph
is what enables multi-hop retrieval — when you query Section 17(5), the system
automatically pulls the related circulars."

---

### SESSION 3 — Legal-Hierarchy-Aware Chunker
**Time:** 3–4 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**What you're building:** The core novel contribution. A chunker that preserves legal
structure so no clause is separated from its parent section context.

**OpenCode Prompt:**

```
I'm building legal-hierarchy-aware chunking for the CGST Act. Normal RAG chunking
(split every 512 tokens) destroys legal meaning because a clause like
"food and beverages, outdoor catering" has no meaning without its parent context
"ITC shall not be available in respect of the following."

Create ml/data_pipeline/legal_chunker.py:

The CGST Act has this hierarchy:
Chapter (e.g., "CHAPTER V - INPUT TAX CREDIT")
  Section (e.g., "17. Apportionment of credit and blocked credits")
    Sub-section (e.g., "(5) Notwithstanding anything contained...")
      Clause (e.g., "(a) motor vehicles...")
        Sub-clause (e.g., "(i) for transportation of persons...")
      Proviso (starts with "Provided that...")
      Explanation (starts with "Explanation.—")

Build a LegalChunker class with method chunk_cgst_act(sections_dir) that:

1. Loads each cgst_section_{N}.json from ml/data/parsed_acts/
2. For each section, creates chunks at the SUB-SECTION level
   - Each chunk = parent section header + section number + sub-section text
   - Never cut a chunk in the middle of a proviso or explanation
   - Maximum chunk size: 800 tokens (use tiktoken for counting)
   - If sub-section is longer than 800 tokens, split at clause boundaries only

3. Each chunk must have metadata:
   {
     "chunk_id": "cgst_s17_ss5_c_a",
     "citation": "CGST Act, 2017 - Section 17(5)(a)",
     "chapter": 5,
     "section": 17,
     "sub_section": "5",
     "clause": "a",
     "parent_context": "Section 17: Apportionment of credit and blocked credits",
     "text": "...(parent header)...\n\n...(full clause text)...",
     "source_type": "cgst_act",
     "token_count": 245
   }

4. Also create chunks for CBIC circulars from ml/data/metadata/:
   - Each circular becomes one chunk (they're short, 2-5 pages)
   - Metadata includes circular_number, date, sections_referenced

5. Save all chunks to ml/data/processed/all_chunks.jsonl (one JSON per line)
6. Print summary: total chunks, average token count, chunks per section

Also create ml/data_pipeline/validate_chunks.py that:
- Loads all_chunks.jsonl
- Checks no chunk exceeds 800 tokens
- Checks every chunk has all required metadata fields
- Prints validation report

Run both. Show me the output.
```

**After session — what to study (45 minutes):**
- Open all_chunks.jsonl. Find the Section 17(5) chunks. Count them.
- Verify that chunk for Section 17(5)(a) has the parent context in its text.
- Understand what tiktoken is and how token counting works.
- Know the difference between character-splitting and token-splitting.

**Critical interview question you must answer cold:**
"Why didn't you just use LangChain's RecursiveCharacterTextSplitter?"
Answer: "RecursiveCharacterTextSplitter splits on character count without understanding
legal document structure. It would split 'Provided that ITC is available if the motor
vehicle is used for...' away from its parent blocking clause, making the chunk legally
meaningless. My chunker preserves the Section → Sub-section → Clause hierarchy by
splitting only at legal structural boundaries, not character boundaries."

---

### SESSION 4 — Embedding Model Fine-tuning
**Time:** 2 hours (Colab) | **Model:** NOT OpenCode | **Platform:** Google Colab T4

This session is NOT in OpenCode. It runs in Google Colab because it needs a GPU.

**Step 1:** Open Google Colab → Runtime → Change runtime type → T4 GPU.

**Step 2:** Create a new Colab notebook. Paste this code in cells:

**CELL 1 — Install:**
```python
!pip install sentence-transformers datasets wandb pdfplumber tiktoken -q
!pip install accelerate -q
```

**CELL 2 — Generate training pairs (uses your real chunks as positive passages):**
```python
import json, random
from anthropic import Anthropic

client = Anthropic()  # Set ANTHROPIC_API_KEY in Colab secrets

# Load your chunks from all_chunks.jsonl
# Upload the file to Colab first via Files panel
chunks = []
with open('all_chunks.jsonl') as f:
    for line in f:
        chunks.append(json.loads(line))

# Filter to ITC-relevant chunks (Section 16, 17, 18)
itc_chunks = [c for c in chunks if c.get('section') in [16, 17, 18, 9, 10]]
print(f"ITC-relevant chunks: {len(itc_chunks)}")

training_pairs = []

for chunk in itc_chunks[:150]:  # Process 150 chunks, 4 queries each = 600 pairs
    prompt = f"""Generate 4 natural language questions that would be answered by this 
    legal text. Include 2 in English and 2 in Hinglish (mix of Hindi and English).
    
    Legal text: {chunk['text'][:500]}
    
    Return only a JSON array of 4 question strings. No explanation."""
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    
    try:
        questions = json.loads(response.content[0].text)
        for q in questions:
            training_pairs.append({
                "query": q,
                "positive": chunk['text'],
                "citation": chunk['citation']
            })
    except:
        pass

print(f"Generated {len(training_pairs)} training pairs")

with open('gst_training_pairs.json', 'w') as f:
    json.dump(training_pairs, f, ensure_ascii=False)
```

**CELL 3 — Fine-tune the embedding model:**
```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from sentence_transformers.evaluation import InformationRetrievalEvaluator
from torch.utils.data import DataLoader
import wandb, random

wandb.init(project="gst-embeddings", name="multilingual-e5-gst-v1")

model = SentenceTransformer('intfloat/multilingual-e5-base')

with open('gst_training_pairs.json') as f:
    pairs = json.load(f)

random.shuffle(pairs)
train_pairs = pairs[:500]
eval_pairs = pairs[500:]

train_examples = [
    InputExample(texts=[p['query'], p['positive']]) 
    for p in train_pairs
]

train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
train_loss = losses.MultipleNegativesRankingLoss(model)

# Build eval dict
queries = {str(i): p['query'] for i, p in enumerate(eval_pairs)}
corpus = {str(i): p['positive'] for i, p in enumerate(eval_pairs)}
relevant_docs = {str(i): {str(i)} for i in range(len(eval_pairs))}

evaluator = InformationRetrievalEvaluator(queries, corpus, relevant_docs, 
                                           name='gst-eval')

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=5,
    warmup_steps=50,
    evaluator=evaluator,
    evaluation_steps=100,
    output_path='gst-legal-embeddings-v1',
    show_progress_bar=True
)

print("Training complete. Model saved to gst-legal-embeddings-v1/")
```

**CELL 4 — Evaluate and log:**
```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load both models for comparison
base_model = SentenceTransformer('intfloat/multilingual-e5-base')
finetuned_model = SentenceTransformer('gst-legal-embeddings-v1')

# Test on 20 held-out pairs
test_pairs = pairs[-20:]

def compute_mrr(model, test_pairs, all_passages):
    query_embeddings = model.encode([p['query'] for p in test_pairs])
    passage_embeddings = model.encode(all_passages)
    
    mrr_scores = []
    for i, qe in enumerate(query_embeddings):
        sims = cosine_similarity([qe], passage_embeddings)[0]
        ranked = np.argsort(sims)[::-1]
        rank = np.where(ranked == i)[0][0] + 1
        mrr_scores.append(1.0 / rank)
    
    return np.mean(mrr_scores)

all_passages = [p['positive'] for p in test_pairs]
base_mrr = compute_mrr(base_model, test_pairs, all_passages)
finetuned_mrr = compute_mrr(finetuned_model, test_pairs, all_passages)

print(f"Base model MRR@20: {base_mrr:.4f}")
print(f"Fine-tuned model MRR@20: {finetuned_mrr:.4f}")
print(f"Improvement: {((finetuned_mrr - base_mrr) / base_mrr * 100):.1f}%")

wandb.log({"base_mrr": base_mrr, "finetuned_mrr": finetuned_mrr})
```

**CELL 5 — Upload to HuggingFace:**
```python
from huggingface_hub import login
login(token="YOUR_HF_TOKEN")  # Get from huggingface.co/settings/tokens

finetuned_model.save_pretrained('gst-legal-embeddings-v1')
finetuned_model.push_to_hub('meet136/gst-legal-embeddings-v1')
print("Model uploaded to HuggingFace!")
```

**After session — what to study (1 hour — this is the most important study session):**
- Understand Multiple Negatives Ranking Loss: why is it used for embedding training?
  Short answer: treats all OTHER passages in a batch as negatives automatically.
  No explicit negative sampling needed. Scales with batch size.
- Understand MRR (Mean Reciprocal Rank): if the correct document is ranked 3rd,
  MRR contribution = 1/3. If ranked 1st, contribution = 1/1. Mean over all queries.
- Understand contrastive learning: embeddings are pushed together for (query, relevant
  passage) pairs and pushed apart from all other passages in the batch.
- Know your actual MRR numbers from Cells 4 output. Memorize them.

**Interview answer for "Explain your fine-tuning approach":**
"I fine-tuned intfloat/multilingual-e5-base on 500 (query, passage) pairs using
Multiple Negatives Ranking Loss. Queries were generated using an LLM conditioned
on real CBIC legal text — so synthetic queries, real corpus. This improved retrieval
MRR from [your base number] to [your finetuned number] on a held-out eval set,
a [X]% improvement. I tracked experiments in W&B and the model is at
meet136/gst-legal-embeddings-v1 on HuggingFace."

---

### SESSION 5 — ChromaDB Vector Store + RAG Pipeline
**Time:** 4 hours | **Model:** Claude Sonnet (switch in OpenCode) | **Platform:** OpenCode

Switch model to Claude Sonnet before starting this session. Wrong retrieval code
silently returns garbage results with no error.

**OpenCode Prompt:**

```
I'm building the retrieval pipeline for GSTMind, a legal RAG system for Indian GST.

I have:
- ml/data/processed/all_chunks.jsonl: 800+ legal chunks with citation metadata
- ml/models/gst-legal-embeddings-v1/: fine-tuned sentence-transformers model
- ml/data/citation_graph.json: {section_number: [circular_numbers]}

Create backend/app/gstmind/retriever.py:

CLASS: GSTMindRetriever

__init__(self, chunks_path, model_path, citation_graph_path):
  - Load all chunks from JSONL
  - Load the fine-tuned sentence-transformers model
  - Load citation graph
  - Build ChromaDB collection named "gst_legal_corpus"
  - Index all chunks: embed text, store with full metadata
  - Use persistent ChromaDB storage at ml/data/chromadb/

retrieve(self, query: str, top_k: int = 20) -> List[Dict]:
  Step 1 - Semantic search:
    Embed the query using the fine-tuned model.
    Query ChromaDB for top_k nearest chunks.
    
  Step 2 - Citation graph expansion:
    For each retrieved chunk, check its section_number in citation_graph.
    If the section has related circulars, retrieve those circular chunks too.
    Add them to results if not already present. Cap total at top_k + 10.
    
  Step 3 - Cross-encoder reranking:
    Load cross-encoder/ms-marco-MiniLM-L-6-v2 for reranking.
    Score all retrieved chunks against the query using cross-encoder.
    Return top 5 highest-scored chunks.
    
  Step 4 - Conflict detection:
    Among the top 5 chunks, check if any contain contradictory signals:
    - Two chunks referencing the same section but with opposite ITC conclusions
    - Two AAR chunks from different states on the same issue
    Set conflict_detected = True if found, include both conflicting chunks.
    
  Returns: {
    "chunks": [top 5 reranked chunks with metadata],
    "conflict_detected": bool,
    "conflicting_pairs": [[chunk_a, chunk_b]] if conflicts found
  }

Also create backend/app/gstmind/responder.py:

CLASS: GSTMindResponder

generate_response(self, query: str, retrieval_result: dict) -> GSTMindResponse:
  Build a prompt for the Anthropic API that:
  - Provides the query
  - Provides retrieved chunks WITH their citation metadata
  - If conflict_detected=True: instructs LLM to surface BOTH rulings and recommend CA consultation
  - If conflict_detected=False: instructs LLM to provide a direct cited answer
  - Instructs LLM to always end with: "Section cited: [exact citation]"
  
  Response format (Pydantic model):
  class GSTMindResponse(BaseModel):
    answer: str
    citations: List[str]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    conflict_detected: bool
    conflicting_rulings: Optional[List[str]]
    source_chunks: List[str]  # chunk_ids used

Create a test script ml/test_retriever.py that:
- Initializes GSTMindRetriever
- Tests these 5 queries:
  1. "Is ITC available on motor vehicle purchase?"
  2. "Can I claim ITC on office renovation expenses?"
  3. "Is group health insurance for employees ITC eligible?"
  4. "AC repair karne par ITC milega?"  (Hinglish)
  5. "What is reverse charge mechanism under Section 9(3)?"
- Prints retrieved chunks and citations for each
- Prints whether conflict was detected

Run the test and show me output.
```

**After session — what to study (45 minutes):**
- Run each test query manually. Read the retrieved chunks. Do they make sense?
- Understand what ChromaDB is: a vector database that stores embeddings and lets you
  query by similarity. Each chunk = one vector. Query = one vector. Return nearest.
- Understand what a cross-encoder is vs bi-encoder: bi-encoder (your fine-tuned model)
  encodes query and passage independently then compares. Cross-encoder takes both as
  input together — more accurate but slower, used only for reranking top-20 to top-5.
- Know your retrieval results: which query triggered conflict detection?

---

### SESSION 6 — GSTMind Integration + CA Dashboard Feature
**Time:** 3 hours | **Model:** Claude Sonnet | **Platform:** OpenCode

**OpenCode Prompt:**

```
I have GSTMindRetriever and GSTMindResponder in backend/app/gstmind/.
Now integrate GSTMind into two places:

INTEGRATION 1 — Compliance Engine Fallback:
Find the compliance engine file (search for "itc_eligible" or "Section 17" in
backend/app/).

Modify the ITC calculation function to:
1. Run deterministic rules first (keep existing logic)
2. If the result has confidence != "HIGH" (or if the transaction category is
   not one of the 7 standard categories), call GSTMindRetriever
3. Attach citations and conflicts from GSTMind to the ITCResult
4. Log which path was taken (deterministic vs RAG) using structlog

Make sure the GSTMind call is wrapped in try/except — if RAG fails,
fall back to deterministic result with a log warning. Never break invoice
processing because GSTMind is unavailable.

INTEGRATION 2 — New API endpoint:
Create backend/app/routes/gstmind.py with these endpoints:

POST /api/gstmind/query
Request: {"question": str, "language": "en" | "hi" | "gu"}
Response: GSTMindResponse (from Session 5 Pydantic model)
Rate limit: 20 requests per minute per user (use the slowapi limiter)
Auth: require JWT token (same as other /api/ routes)

GET /api/gstmind/health
Returns: {"status": "ok", "chunks_indexed": int, "model": str}

Also add the GSTMind query to the WhatsApp webhook:
If a user's WhatsApp message starts with "?" or "query:" or "sawaal:",
route it to GSTMind instead of the invoice OCR pipeline.
Example: User sends "? AC repair pe ITC milega kya?"
→ Route to GSTMind
→ Reply with cited answer

Write one integration test in backend/tests/test_gstmind_integration.py
that mocks the ChromaDB retriever and tests the API endpoint.

Show me all changes before applying.
```

**After session — what to study (30 minutes):**
- Test the /api/gstmind/query endpoint manually with Postman or curl.
- Ask it: "Is ITC available on AC repair?"
- Read the response. Is the Section 17(5) citation correct?
- Understand what happens when GSTMind fails: the invoice processing continues,
  just without the RAG answer. This is graceful degradation.

---

### SESSION 7 — GST-QA Benchmark + HuggingFace Dataset Upload
**Time:** 2 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode + manual

**OpenCode Prompt:**

```
Create the GST-QA evaluation benchmark for GSTMind.

Create ml/evaluation/create_benchmark.py that builds a JSON file with 100 questions.

Build the questions manually in code as a Python list. I'll give you the structure,
generate the content:

50 ITC eligibility questions covering:
- Motor vehicles (clear blocked — Section 17(5)(a))
- Food and beverages (clear blocked — Section 17(5)(b))
- Capital goods (clear eligible — Section 16)
- Input services (clear eligible — Section 16)
- Club memberships (clear blocked — Section 17(5)(b))
- Health insurance (conflicting AARs — mark difficulty="conflicting")
- Office renovation (gray area — mark difficulty="ambiguous")
- Employee canteen (gray area — mark difficulty="ambiguous")

20 RCM questions covering Section 9(3) and 9(4)
15 GST rate questions
15 Place of supply questions

Each entry format:
{
  "id": "q001",
  "question": "Is ITC available on purchase of a car for MD's use?",
  "question_hi": "MD ke liye car kharidne par ITC milega kya?",
  "ground_truth_section": "Section 17(5)(a) of CGST Act, 2017",
  "ground_truth_circular": null,
  "expected_answer": "blocked",
  "difficulty": "clear",
  "category": "itc_eligibility"
}

Also create ml/evaluation/evaluate_gstmind.py that:
- Loads the benchmark
- Runs each question through GSTMindRetriever
- Checks if ground_truth_section appears in any of the top-5 retrieved chunks
- Computes MRR@10 and Precision@5
- Saves results to ml/evaluation/benchmark_results.json

Also create ml/evaluation/upload_to_hf.py that uploads:
1. The benchmark JSON as HuggingFace dataset meet136/gst-qa-benchmark
2. The parsed circulars as meet136/cbic-circulars-parsed

Show me the benchmark file before uploading.
```

**Manual step after:** Run evaluate_gstmind.py. Note the MRR@10 number. Add it to
your README and HuggingFace model card. This is the number you quote in interviews.

---

### SESSION 8 — HuggingFace Model Card + README Update for GSTMind
**Time:** 1.5 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Update the HuggingFace model card for meet136/gst-legal-embeddings-v1 and
update the project README to include GSTMind.

MODEL CARD — write to ml/models/gst-legal-embeddings-v1/README.md:

Include:
- Model description: fine-tuned intfloat/multilingual-e5-base on Indian GST legal text
- Base model: intfloat/multilingual-e5-base
- Languages: English, Hindi, Gujarati (Hinglish)
- Training data: [X] query-passage pairs generated from real CBIC corpus
- Training method: Multiple Negatives Ranking Loss, 5 epochs, batch 16
- Evaluation results table:
  | Metric | Base Model | Fine-tuned |
  | MRR@20 | [base_number] | [finetuned_number] |
- Intended use: Indian GST compliance legal retrieval
- Limitations: trained on synthetic queries; real CBIC text corpus
- Citation

README update — add a "GSTMind — Legal Intelligence Engine" section after
the system architecture section. Include:

- What GSTMind is (2 sentences)
- The architecture: chunking → embedding → ChromaDB → citation graph → reranking → response
- Sample queries and responses (create 3 example Q&As showing real section citations)
- Benchmark results: MRR@10 = X on the gst-qa-benchmark dataset
- Link to: meet136/gst-legal-embeddings-v1 and meet136/gst-qa-benchmark on HuggingFace
- Known limitations of GSTMind

Also update the Engineering Decisions table in README to add GSTMind decisions:
| Fine-tuned embeddings vs generic | Generic embeddings miss "RCM", "Section 9(3)" | Fine-tuned improves MRR by X% |
| RAG vs LLM fine-tuning | LLM fine-tuning costs $$$, stale after new circulars | RAG is updatable, cheap, citeable |
| ChromaDB vs Pinecone/Weaviate | Pinecone has free tier limits | ChromaDB is fully local/free |
```

---

## TRACK 2: Backend Upgrades (SDE Credibility)

Switch back to DeepSeek V4 Flash for all backend sessions.

---

### SESSION 9 — Compliance Engine Test Suite
**Time:** 3 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Find the GST compliance engine in this project (search for files containing
"Section 17" or "itc_eligible" or "blocked" in backend/app/).
Show me its location and main class/function names before proceeding.

Then create backend/tests/test_compliance_engine.py with comprehensive pytest tests.

Requirements:
- Test every Section 17(5) blocked category with its section reference
- Test every eligible category (capital goods, input services, raw materials)
- Test RCM detection and liability = amount * 0.18
- Test GSTIN validation: "29ABCDE1234F1Z5" should pass, "INVALID" should raise ValueError
- Use parametrize for: amount=0, amount=1, amount=100000, amount=9999999
- Each test must have a docstring citing the GST section it tests
- Group tests in classes: TestSection17_5_Blocked, TestEligibleCategories, TestRCM, TestGSTINValidation

Run: pytest backend/tests/test_compliance_engine.py -v --tb=short

Fix all failures until all tests pass. Show final output with test count.
Then run with coverage:
pytest backend/tests/test_compliance_engine.py --cov=app.compliance --cov-report=term-missing
```

**After session — memorize:** The test count and coverage percentage. "My compliance
engine has X tests covering 100% of the Section 17(5) blocked categories and all
eligible categories. Coverage is Y% because [reason for any gaps]."

---

### SESSION 10 — Async OCR + Redis Caching
**Time:** 3 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Find the WhatsApp webhook handler in backend/app/ (search for Twilio or MediaUrl).
Show me the current webhook function before making any changes.

Make two changes:

CHANGE 1 — Async OCR:
The current webhook calls OCR synchronously. Twilio has a 15-second response timeout.
Refactor to:
- Immediately send acknowledgment to Twilio: "Processing your invoice... Reply STOP to cancel."
- Use FastAPI BackgroundTasks to run OCR + classification + DB write asynchronously
- After async processing, send result via Twilio API
- If async processing fails, send error message: "Invoice processing failed. Please send the photo again."
- Log all steps using Python logging with the job_id

CHANGE 2 — Redis caching for OCR:
Add Redis caching. Cache key = SHA-256 hash of image bytes. TTL = 7 days.
If cache hit → skip OCR API call.
If cache miss → call OCR → store result in cache.

Add Redis to docker-compose.yml with health check if not already present.
Add redis-py to requirements.txt.
Add REDIS_URL to .env.example.

Show me the diff of changed files. Do NOT break the existing OCR flow.
Test by showing me the function signature and key logic. Run any existing tests.
```

---

### SESSION 11 — Security + Rate Limiting
**Time:** 2 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Add two security features to the FastAPI backend:

FEATURE 1 — Twilio Signature Verification:
Add a FastAPI Depends() function verify_twilio_signature(request: Request) that:
- Gets TWILIO_AUTH_TOKEN from environment
- Validates X-Twilio-Signature header using twilio.request_validator.RequestValidator
- Raises HTTPException(403) if signature invalid
- Apply as a dependency to the WhatsApp webhook endpoint ONLY

FEATURE 2 — Rate limiting via slowapi:
Add rate limits:
- WhatsApp webhook: 20/minute per IP
- POST /api/gstmind/query: 20/minute per user (use JWT user_id as key)
- Auth endpoints: 5/minute per IP
- All other /api/ routes: 60/minute per IP

Handle RateLimitExceeded with JSON response: {"error": "rate_limit_exceeded", "retry_after": X}

Add slowapi and twilio to requirements.txt if not present.
Show me changes before applying. Run existing tests to confirm nothing broke.
```

---

### SESSION 12 — Alembic Migrations + Database Indexes
**Time:** 2 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Set up Alembic for database migration versioning.

Step 1: Install alembic, add to requirements.txt
Step 2: Run alembic init alembic
Step 3: Configure alembic/env.py to use DATABASE_URL from environment and
        import the SQLAlchemy Base from backend/app/database.py (find it)
Step 4: Generate initial migration: alembic revision --autogenerate -m "initial_schema"
Step 5: Add these to the Invoice model (or main transaction table, find it):
  - Index on user_id column
  - Index on invoice_date column
  - Composite index on (user_id, invoice_date) named idx_invoice_user_date
  - deleted_at DateTime column (nullable=True, default=None)
Step 6: Update all hard-delete queries to soft-delete (set deleted_at = now())
Step 7: Add WHERE deleted_at IS NULL to all SELECT queries on the invoice table
Step 8: Generate migration for new indexes: alembic revision --autogenerate -m "add_indexes_softdelete"

Show me the migration files. Explain each index choice in a comment in the file.
```

---

### SESSION 13 — GitHub Actions CI Pipeline
**Time:** 1.5 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Create .github/workflows/ci.yml for automated testing.

Two jobs: test and lint.

TEST job:
- ubuntu-latest, Python 3.11
- Services: postgres:15 (health check: pg_isready) and redis:7-alpine (health check: redis-cli ping)
- Install from backend/requirements.txt
- Run: pytest backend/tests/ -v --cov=app --cov-report=xml --cov-fail-under=55
- Upload coverage to Codecov

LINT job:
- Install ruff
- Run: ruff check backend/app/ --select E,F,I,N
- Run: ruff format --check backend/app/

Environment variables for test job:
DATABASE_URL: postgresql://postgres:testpass@localhost/vyapaar_test
REDIS_URL: redis://localhost:6379
TESTING: "true"
TWILIO_AUTH_TOKEN: "test_token_for_ci"
OPENROUTER_API_KEY: "test_key_for_ci"

Also create ruff.toml:
line-length = 88
select = ["E", "F", "I", "N"]
ignore = ["E501"]

Add CI badge to README: [![CI](https://github.com/meetmehta136/vyapaar-bandhu/actions/workflows/ci.yml/badge.svg)]

Show me the YAML before creating it.
```

---

### SESSION 14 — Structured Logging + Health Endpoint
**Time:** 1.5 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Add structured logging and a health endpoint.

LOGGING:
Install structlog, add to requirements.txt.
Configure in backend/app/main.py:
- JSON output format
- Include: timestamp (ISO), log_level, request_id (UUID per request)
- HTTP middleware: log request_started and request_completed with duration_ms
- Replace any print() statements in backend/app/ with structlog calls

In OCR service: log cache_hit/cache_miss with image_hash (first 8 chars only — privacy)
In GSTMind: log query_received, retrieval_completed (chunks_found, conflict_detected), response_generated

HEALTH ENDPOINT:
Add GET /health to main.py:
- Check DB: execute SELECT 1
- Check Redis: ping
- Check GSTMind: verify ChromaDB collection exists and has > 0 chunks
Returns:
{
  "status": "healthy" | "degraded" | "unhealthy",
  "database": "connected" | "error",
  "redis": "connected" | "error",
  "gstmind": {"status": "ready", "chunks_indexed": int},
  "version": "2.0.0"
}
Return 503 if database is error. Return 200 with degraded if only Redis or GSTMind fails.

Show changes before applying.
```

---

### SESSION 15 — Final README Rewrite
**Time:** 2 hours | **Model:** DeepSeek V4 Flash | **Platform:** OpenCode

**OpenCode Prompt:**

```
Completely rewrite README.md. Engineering-focused. No emojis except in section headers.

EXACT STRUCTURE — follow this order, no deviation:

1. Title: VyapaarBandhu — GST Compliance Automation + Legal Intelligence for Indian SMEs
   Badges: CI, Codecov, HuggingFace model badge, HuggingFace dataset badge

2. Problem Statement (keep existing content)

3. System Architecture — ASCII diagram:
   WhatsApp → Twilio Webhook (sig verified, rate limited)
   → FastAPI (async, BackgroundTasks)
   → Redis Cache (OCR result cache, 7-day TTL)
   → [MISS] OpenRouter VLM OCR → IndicBERT Classifier → Compliance Engine
   → [EDGE CASE] GSTMind RAG (fine-tuned embeddings + CitationGraph + ChromaDB)
   → PostgreSQL (8 tables, Alembic migrations, indexed)
   → WhatsApp Reply + CA Dashboard

4. GSTMind — Legal Intelligence Engine (new section)
   What it is, architecture, 2 sample Q&As with real citations, benchmark results

5. ML Pipeline
   3-tier classification table (keyword baseline, BART zero-shot, IndicBERT)
   GSTMind embedding model metrics table (base vs fine-tuned MRR)

6. Key Engineering Decisions Table (8 rows minimum)

7. Performance Metrics Table

8. Known Limitations (honest: synthetic training queries, free tier Render cold starts, etc.)

9. What I Would Do at Scale (Celery, SageMaker, Kubernetes)

10. Local Dev: docker-compose up instructions (should work from just .env file)

11. Running Tests: pytest command + expected output

12. Cost Model: line-by-line breakdown of ₹/month per user

Remove all: generic feature lists, marketing language, unverified claims.
```

---

## POST-SESSIONS: Deep Study Schedule (Days 15–30)

This is the most important part. 14 sessions of building means nothing if you cannot
explain the code in an interview. Use the remaining 16 days as follows.

**Days 15–17: GSTMind deep study**
Re-read every line of retriever.py and responder.py without looking at AI output.
Answer these without notes:
- What is ChromaDB collection? How does it store embeddings?
- What is the difference between semantic search and keyword search?
- Why is cross-encoder reranking more accurate than bi-encoder comparison?
- Explain Multiple Negatives Ranking Loss to a 5-year-old.
- What happens when MRR@10 = 0.5? What does that mean in plain English?
- How does the citation graph enable multi-hop retrieval? Draw it on paper.

**Days 18–20: Backend deep study**
Re-read compliance engine tests. Be able to write TestSection17_5 tests from memory.
Understand why BackgroundTasks is sufficient here but Celery is better at scale.
Understand what Alembic upgrade/downgrade does to the database.

**Days 21–23: System design prep**
Draw the full VyapaarBandhu architecture from memory on paper.
Answer: "How would you scale GSTMind to 100,000 queries/day?"
Expected answer: Move ChromaDB to Qdrant hosted, SageMaker for embeddings, API Gateway.

**Days 24–26: ML theory prep**
Be able to explain without notes:
- Transformer architecture (encoder vs decoder, why BERT is encoder-only)
- What fine-tuning is vs pre-training vs in-context learning
- Why RAG beats fine-tuning for legal documents (freshness, traceability, cost)
- What embedding drift is and how you'd detect it in production

**Days 27–28: Mock interviews**
Ask a friend to ask you every interview question from the previous documents.
If you can't answer any question for 2 minutes without notes, flag it and study that.

**Days 29–30: Final polish**
Update HuggingFace model card with final metrics.
Verify CI pipeline is green on GitHub.
Verify live deployment on Render responds to /health with 200.
Record a 2-minute demo video: WhatsApp invoice → ITC result + GST query → cited answer.

---

## What You Can Drop If Time Runs Out (Priority Order)

Drop Session 14 (structured logging) first — least interview impact.
Drop Session 11 security details if pressed for time — mention the concept verbally.
NEVER drop Session 4 (embedding fine-tuning) — it is your core ML story.
NEVER drop Session 7 (benchmark + HuggingFace upload) — it is your published contribution.
NEVER drop Session 9 (compliance engine tests) — it is your engineering maturity signal.

---

## The North Star

When an interviewer asks "tell me about your ML work" you should be able to say:

"I built GSTMind — a legal RAG system for Indian GST that indexes 250 CBIC circulars
and the CGST Act using a fine-tuned multilingual embedding model I published on
HuggingFace. The key innovations are legal-hierarchy-aware chunking that preserves
Section → Clause → Proviso structure, and a citation graph enabling multi-hop
retrieval across circulars and AAR rulings. The system detects conflicting state-level
rulings and surfaces uncertainty rather than hallucinating confident answers. I
evaluated it on a 100-question GST-QA benchmark I published on HuggingFace Datasets —
MRR@10 of [your number]. It's integrated as a fallback in VyapaarBandhu's compliance
engine for edge cases that deterministic rules cannot handle."

That is 90 seconds. Every word in it is defensible because you built every line.

DOCEOF
echo "Done"
Output

Done    