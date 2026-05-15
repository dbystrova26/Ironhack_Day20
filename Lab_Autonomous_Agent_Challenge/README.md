# Believe Royalty Q&A Agent
**Ironhack — Autonomous Agent Challenge Lab**  
Consultant: Daria Bystrova | May 2025

A RAG-powered autonomous agent that answers artist royalty questions by reasoning over Believe royalty statements and FAQ documents, orchestrated via n8n with Google Sheets logging and Slack escalation.

---

## File Map

| File / Folder | Description |
|---|---|
| `project_plan.md` | Main deliverable — full 6-section project plan |
| `lab_summary.md` | Reflection paragraph at repo root (required by lab) |
| `requirements.txt` | Python dependencies |
| `n8n_workflow.json` | Exportable n8n workflow — import directly into n8n |
| `data/nova_bloom_feb_2024.pdf` | Simulated royalty statement — February 2024 |
| `data/nova_bloom_mar_2024.pdf` | Simulated royalty statement — March 2024 |
| `data/believe_faq.pdf` | Compiled FAQ — Believe policies and royalty explanations |
| `src/ingest.py` | Ingests PDFs into Pinecone vector database |
| `src/agent.py` | LangGraph agent — 4 nodes: classify, retrieve, reason, route |
| `src/serve.py` | FastAPI server exposing the agent to n8n via HTTP POST |
| `screenshots/n8n_workflow.png` | n8n canvas screenshot |
| `screenshots/sheets_log.png` | Google Sheets conversation log |
| `screenshots/slack_alert.png` | Slack escalation alert example |

---

## What Problem This Solves

Independent artists distributed by Believe regularly contact their account managers with questions like *"Why was my March payout lower than February?"* or *"What is Believe's commission rate?"*. Today this is handled manually — an account manager opens the relevant PDF statement, reads it, and writes a reply. This does not scale as Believe's roster grows across 50+ countries.

This agent automates the first line of support: it reads the artist's royalty PDFs and FAQ documents, reasons over them using Claude, and returns a plain-language answer in under 30 seconds. If the question requires human action (e.g. filing a dispute), the agent flags it automatically and alerts the account manager on Slack — so nothing falls through the cracks.

---

## How the System Works — Concept

### The webhook — how a question enters the system

A webhook is a URL that listens for incoming HTTP requests. In this project, n8n generates a webhook URL (e.g. `https://your-n8n-instance/webhook/believe-royalty`). Whenever someone sends a POST request to that URL with a question in the body, n8n wakes up and starts the workflow.

In a real Believe product, this webhook would be called by a chat widget in the Believe Backstage artist portal, a WhatsApp Business integration, or a support form on believe.com. For this prototype, the webhook is triggered manually using a `curl` command in the terminal — simulating exactly what the artist's interface would send.

```bash
# This simulates an artist submitting a question
curl -X POST "https://your-n8n-instance/webhook/believe-royalty" \
  -H "Content-Type: application/json" \
  -d '{"question": "Why was my March payout lower than February?"}'
```

### ngrok — connecting n8n (cloud) to the local Python agent

The LangGraph agent runs as a Python server on your laptop (`localhost:8000`). n8n runs in the cloud. By default, cloud services cannot reach `localhost` because it is only accessible from your own machine.

ngrok solves this by creating a secure tunnel: it gives your local server a public URL (e.g. `https://paver-study-ramble.ngrok-free.dev`) that the internet can reach, and forwards all traffic to your local port 8000. In the n8n HTTP Request node, you paste this ngrok URL instead of `localhost`.

```
Artist question
      ↓
n8n (cloud) → POST https://xxxx.ngrok-free.dev/ask
                              ↓  (ngrok tunnel)
                    FastAPI server on localhost:8000
                              ↓
                    LangGraph agent + Pinecone + Claude
```

ngrok is only needed for local development. In production, the Python agent would be deployed to a cloud server (e.g. Railway, Render, AWS) with a permanent public URL, and ngrok would not be needed.

### The LangGraph agent — how it reasons

The agent does not simply search for keywords. It processes every question through 4 structured steps:

1. **Classify** — Claude reads the question and decides: is this a comparison between months, a platform-specific query, an FAQ question, or something general?
2. **Retrieve** — Pinecone searches the vector database using the right metadata filter. For a comparison question it fetches chunks from both the February and March PDFs. For an FAQ question it only searches the FAQ document.
3. **Reason** — Claude reads the retrieved chunks and generates a plain-language answer, citing specific figures from the documents. It also assigns a confidence level (high or low).
4. **Route** — if confidence is high the answer is returned. If confidence is low (the documents do not contain enough information), the question is flagged for escalation.

### Google Sheets — logging every conversation

Every question that passes through the system — whether answered or escalated — is logged as a new row in a Google Sheet called "Believe Royalty Agent Log". The n8n Google Sheets node appends the row automatically after every execution.

The sheet records: question, answer, confidence, escalated (TRUE/FALSE), sources (which PDFs were cited), and timestamp. This gives Believe's team a full audit trail and a way to review agent performance over time.

**Business need:** Believe's account managers need visibility into what artists are asking, even when the agent handles it autonomously. The Sheets log is their oversight tool — they can spot patterns, identify gaps in the FAQ, and review any escalated cases.

### Slack — escalation alerts to account managers

The n8n IF node checks the `escalated` field from the agent response. If it is `true`, the Slack node fires a message to the `#believe-royalty-agent-update` channel with the question, the reason it could not be answered, and a timestamp. The account manager then follows up with the artist directly.

**Business logic:** the agent answers routine questions (commission rates, stream explanations, payout comparisons). It escalates anything that requires human action — disputes, refunds, payment investigations from prior years, or any question where the documents are insufficient. This keeps humans in the loop for decisions that matter, while removing them from repetitive information retrieval.

```
Every question → Google Sheets log (always)
                      ↓
              escalated == TRUE?
              YES → Slack alert to account manager
              NO  → workflow ends, artist has their answer
```

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Anthropic API key (console.anthropic.com)
- Pinecone API key — free serverless tier (app.pinecone.io)
- n8n account (app.n8n.io free tier or self-hosted)
- Google account (for Google Sheets via n8n OAuth)
- Slack workspace with a channel for alerts
- ngrok account — free tier (ngrok.com)

### 1. Clone the repo and install dependencies

```bash
git clone https://github.com/your-username/believe-royalty-agent
cd believe-royalty-agent
pip install -r requirements.txt
```

### 2. Create a .env file at the project root

```
ANTHROPIC_API_KEY=your_anthropic_key_here
PINECONE_API_KEY=your_pinecone_key_here
```

### 3. Ingest documents into Pinecone

```bash
python src/ingest.py
```

Loads the 3 PDFs from `/data`, splits them into 500-character chunks, embeds them with `all-MiniLM-L6-v2`, and upserts them into a Pinecone index called `believe-royalties` with metadata tags (`doc_type`, `period`, `artist`) for filtered retrieval.

Expected output:
```
Done. Index 'believe-royalties' is ready for the agent.
```

### 4. Test the agent directly (no n8n needed)

```bash
python src/agent.py
```

Runs all 5 demo questions through the LangGraph graph and prints answers to the terminal. Verify the agent works before connecting n8n.

### 5. Start the FastAPI server

```bash
uvicorn src.serve:app --port 8000
```

Test it immediately:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Believe commission rate?"}'
```

### 6. Expose the local server with ngrok

```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL. This is what you paste into n8n's HTTP Request node as the agent URL.

### 7. Import and configure the n8n workflow

1. Open n8n → **New Workflow** → **Import from file**
2. Import `n8n_workflow.json` from this repo
3. Open the **HTTP Request node** → update URL to `your-ngrok-url/ask`
4. Open the **Google Sheets node** → connect your Google account via OAuth → select your sheet
5. Open the **Slack node** → connect your Slack app via OAuth → select your alerts channel
6. **Activate** the workflow using the toggle in the top right corner
7. Send a test question via curl (see below)

### 8. Test the full end-to-end flow

```bash
# Routine question — answer returned, row logged in Sheets
curl -X POST "https://your-n8n-url/webhook/believe-royalty" \
  -H "Content-Type: application/json" \
  -d '{"question": "Why was my March payout lower than February?"}'

# Escalation question — row logged in Sheets AND Slack alert fires
curl -X POST "https://your-n8n-url/webhook/believe-royalty" \
  -H "Content-Type: application/json" \
  -d '{"question": "Can you refund my missing payment from 2023?"}'
```

### 5 demo test questions

| # | Question | Expected behaviour |
|---|---|---|
| 1 | Why was my March payout lower than February? | Identifies Spotify DE stream drop (−44,000), answers confidently |
| 2 | How much did I earn from Apple Music in February? | Returns €228.00 from Feb statement |
| 3 | What is Believe's commission rate? | Returns 15% from FAQ |
| 4 | Why do stream counts differ between platforms? | Explains reporting windows from FAQ |
| 5 | Can you refund my missing payment from 2023? | Low confidence → escalates → Slack alert fires |

---

## Architecture

```
Artist question (curl / form / chat widget)
        ↓
n8n Webhook  (POST /webhook/believe-royalty)
        ↓
n8n HTTP Request → ngrok tunnel → FastAPI /ask (localhost:8000)
        ↓
LangGraph Agent
  ┌──────────────────────────────────┐
  │ Node 1: Classify question type   │
  │ Node 2: Retrieve from Pinecone   │ ← 3 PDFs (Feb, Mar, FAQ)
  │ Node 3: Reason with Claude       │ ← Anthropic API
  │ Node 4: Route (high/low conf.)   │
  └──────────────────────────────────┘
        ↓                   ↓
  High confidence      Low confidence
  → Return answer      → Flag escalation
        ↓                   ↓
  Google Sheets log    Google Sheets log
  (answer logged)      + Slack alert to
                         account manager
```

---

## Simulated Data

All data is fictional and created for demonstration purposes only. No real artist or Believe financial data is used.

- **Artist:** Nova Bloom (fictional)
- **February 2024:** €785.70 net payout — Spotify DE at 142,000 streams (editorial playlist active)
- **March 2024:** €630.40 net payout — Spotify DE dropped to 98,000 streams (playlist rotated out)
- **FAQ:** Compiled from Believe's public website + manually written royalty Q&A covering commission rates, platform reporting schedules, and dispute processes
