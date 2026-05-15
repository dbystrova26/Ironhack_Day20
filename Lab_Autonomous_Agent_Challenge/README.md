# Believe Royalty Q&A Agent
**Ironhack — Autonomous Agent Challenge Lab**  
Consultant: Daria Bystrova | May 2025

An autonomous agent that answers artist royalty questions by reasoning over simulated Believe royalty statements and FAQ documents, orchestrated via n8n with Google Sheets logging and Slack escalation.

---

## File Map

| File / Folder | Description |
|---|---|
| `project_plan.md` | Main deliverable — full 6-section project plan |
| `lab_summary.md` | Reflection paragraph (hardest part, lessons, open questions) |
| `data/` | Simulated royalty PDFs and FAQ document |
| `src/ingest.py` | Ingests PDFs into ChromaDB vector database |
| `src/agent.py` | LangGraph agent — 4 nodes: classify, retrieve, reason, route |
| `src/serve.py` | FastAPI server exposing the agent to n8n via HTTP |
| `screenshots/` | n8n workflow, Google Sheets log, Slack alert |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Anthropic API key
- n8n (local install or n8n.io free cloud account)
- Google Sheets API credentials (set up via n8n OAuth)
- Slack workspace with an alerts channel

### 1. Install dependencies

```bash
pip install langchain langgraph langchain-anthropic chromadb fastapi uvicorn pypdf
```

### 2. Set environment variable

```bash
export ANTHROPIC_API_KEY=your_key_here
```

### 3. Ingest documents into ChromaDB

```bash
python src/ingest.py
```

This loads the 3 PDFs from `/data`, chunks them, embeds them, and stores them in a local ChromaDB collection called `believe_royalties`.

### 4. Start the agent server

```bash
uvicorn src.serve:app --port 8000
```

The agent is now available at `http://localhost:8000/ask`

### 5. Expose to n8n (if running n8n locally)

```bash
ngrok http 8000
```

Copy the ngrok URL into the n8n HTTP Request node.

### 6. Import n8n workflow

- Open n8n
- Import the workflow from `screenshots/n8n_workflow.png` (manual recreation) or set up manually:
  - Webhook trigger → HTTP Request (agent) → Google Sheets (log) → IF (escalation flag) → Slack (alert)

### 7. Test with the 5 demo questions

```
1. "Why was my March payout lower than February?"
2. "How much did I earn from Apple Music in February?"
3. "What is Believe's commission rate?"
4. "Why do stream counts differ between platforms?"
5. "Can you file a dispute on my behalf?"
```

Expected: questions 1–4 answered autonomously, question 5 triggers Slack escalation alert.

---

## Architecture

```
Artist question (n8n webhook)
        ↓
  n8n HTTP Request
        ↓
  FastAPI /ask endpoint
        ↓
  LangGraph Agent
  ┌─────────────────────┐
  │ Node 1: Classify    │
  │ Node 2: Retrieve    │ ← ChromaDB (3 PDFs)
  │ Node 3: Reason      │ ← Claude API
  │ Node 4: Route       │
  └─────────────────────┘
        ↓           ↓
   Answer        Escalate
        ↓           ↓
  Google Sheets  Slack alert
     (log)      (account mgr)
```

---

## Simulated Data

All data is fictional and created for demonstration purposes only.

- **Artist:** Nova Bloom (fictional)
- **February 2024 statement:** €734.40 net payout
- **March 2024 statement:** €582.25 net payout (Spotify DE streams dropped by 44,000)
- **FAQ:** Compiled from Believe's public website + manually authored royalty Q&A
