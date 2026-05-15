# Autonomous Agent Project Plan
**Client:** Believe (Germany) — Groove Attack / Nuclear Blast division  
**Consultant:** Daria Bystrova  
**Date:** May 2025

---

## 1. Use Case

### Problem Statement
Artists and independent labels distributed by Believe regularly contact their account managers with questions about royalty statements: why payouts changed month-over-month, which platform drove a drop, or what a specific deduction means. This process is entirely manual — account managers read PDF statements, cross-reference platform reports, and write custom email responses. It does not scale as Believe's roster grows.

### Target Users
- Independent artists distributed via Believe Label & Artist Solutions
- Small label managers (1–5 person operations)
- Internally: account managers who currently handle these queries

### Current Process (Manual)
1. Artist emails or messages account manager with a royalty question
2. Account manager opens the relevant monthly PDF statement
3. Manager compares current and previous periods manually
4. Manager drafts a written explanation
5. Response sent within 1–3 business days

### Success Criteria
- Agent answers at least 80% of common royalty questions without human intervention
- Response time reduced from 1–3 days to under 60 seconds
- Escalation rate (questions requiring human follow-up) below 20%
- All conversations logged for account manager review

### Why an Autonomous Agent (not just a chatbot)
A static chatbot with pre-written answers cannot compare two months of data, identify the specific platform causing a drop, or decide whether a question is too complex to answer without human review. These require multi-step reasoning over documents — which requires an agent architecture.

---

## 2. Technology Stack

### Selected Technologies

| Layer | Technology | Purpose |
|---|---|---|
| Core LLM | Anthropic Claude (claude-sonnet) | Document reasoning, comparison, explanation generation |
| Vector DB | Pinecone (serverless, free tier) | Stores and retrieves chunked royalty statements and FAQ |
| Embeddings | Anthropic / sentence-transformers | Converts document chunks to searchable vectors |
| Agent Framework | LangGraph | Multi-step reasoning graph: classify → retrieve → reason → route |
| Orchestration | n8n | Trigger agent via webhook, log to Google Sheets, Slack escalation |
| Document ingestion | LangChain document loaders | Parse PDFs into chunks for the vector DB |
| Interface | n8n form (webhook trigger) | Artist submits question; result returned via n8n |

### Justification for Choices

**Claude over GPT-4:** Claude performs strongly on document-heavy reasoning tasks and is the natural choice given Anthropic access. Its large context window handles multi-page royalty statements without chunking issues.

**LangGraph over plain LangChain:** The agent needs a guaranteed decision path — classify the question type, retrieve relevant documents, reason, then route to answer or escalate. A plain LangChain ReAct agent loops freely and cannot guarantee this structure. LangGraph's explicit node-and-edge architecture gives us control.

**Pinecone over ChromaDB:** Pinecone's serverless free tier requires no local infrastructure and supports metadata filtering out of the box — critical for filtering chunks by artist, month, and document type. It also scales directly to production if Believe adopts the system, with no migration needed.

**n8n over custom scheduler:** n8n handles the business integration layer (Google Sheets logging, Slack alerts) without custom code. It also provides a webhook endpoint that acts as the agent's entry point — meaning the agent can be triggered from any Believe tool in the future.

### Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| GPT-4 | No access; Claude equivalent in capability |
| ChromaDB | Local-only; requires migration to move to production; Pinecone free tier sufficient |
| Plain LangChain agent | No structured routing; can't guarantee escalation logic |
| Pure n8n (no LangGraph) | n8n AI nodes lack the document reasoning depth needed |

---

## 3. MVP Scope

### Included Features (MVP)

- **RAG over 2 document types:**
  - Monthly royalty statements (2 months, simulated PDFs — February and March 2024)
  - Believe FAQ document (compiled from public website + manually written royalty Q&A)
- **LangGraph agent with 4 nodes:**
  - Node 1: Classify question type (comparison / platform-specific / FAQ / general)
  - Node 2: Retrieve relevant document chunks from Pinecone
  - Node 3: Reason and generate answer using Claude
  - Node 4: Confidence check → route to answer or escalation
- **n8n orchestration:**
  - Webhook trigger (artist submits question via n8n form)
  - Google Sheets logging (question, answer, timestamp, escalation flag)
  - Slack alert to account manager when escalation is triggered
- **Basic conversation memory:** last 3 turns stored in LangGraph state
- **Single artist:** all documents belong to simulated artist "Nova Bloom"
- **English only**
- **Simulated data:** realistic fake royalty statements; no connection to Believe's real systems

### Explicitly Out of Scope (v2+)

- Multi-language support (German, French — relevant for Believe's markets)
- Multi-artist or label-level queries
- Live API connection to Spotify / Apple Music data
- Real Believe internal data or systems
- Automated royalty dispute filing
- Mobile or web app interface
- CRM integration
- Analytics dashboard for account managers
- Voice interface

### Success Metrics for MVP

| Metric | Target |
|---|---|
| Questions answered without escalation | ≥ 4 out of 5 test questions |
| Correct identification of the payout delta between months | Yes (Spotify DE stream drop) |
| Google Sheets log entry created per query | 100% |
| Slack alert triggered on low-confidence answer | Demonstrated at least once |
| End-to-end response time (webhook → answer) | < 30 seconds |

---

## 4. Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Claude hallucinates numbers not present in documents | Medium | High | Prompt instructs Claude to only cite figures explicitly found in retrieved chunks; include source chunk in answer |
| Pinecone retrieves wrong document chunks (wrong month) | Medium | High | Include month and artist name as metadata filters on every retrieval call; verify with test queries after ingestion |
| n8n webhook times out before LangGraph returns answer | Low | Medium | Set n8n HTTP node timeout to 60s; LangGraph targets < 15s response |
| LangGraph node gets stuck in loop | Low | Medium | Set max_iterations = 5 on the graph; add fallback edge to escalation node |
| API rate limits on Claude during demo | Low | Low | Demo uses 5 pre-written test questions; well within free tier limits |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Artists distrust AI-generated royalty explanations | High | High | Always show source document reference ("Based on your March 2024 statement…"); escalation path always available |
| Scope creep during prototype (adding features) | High | Medium | MVP strictly limited to 1 artist, 2 PDFs, 4 LangGraph nodes |
| Account managers resist adoption (fear of replacement) | Medium | Medium | Frame agent as triage tool, not replacement; escalation always routes to human |

### Data Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Simulated data not realistic enough for meaningful demo | Medium | Medium | Use real Believe commission rate (15%), real platform names, realistic stream counts |
| FAQ document missing key questions testers ask | Medium | Low | Pre-define 5 test questions before building; ensure FAQ covers all 5 |
| Artist data privacy in real deployment | High | High | Out of scope for MVP; noted for v2 compliance planning |

---

## 5. Implementation Plan

### Phase 1: Data Preparation (Days 1–2)
**Goal:** All documents ingested and retrievable from Pinecone

Tasks:
- Create `nova_bloom_february_2024.pdf` (simulated royalty statement)
- Create `nova_bloom_march_2024.pdf` (simulated royalty statement — lower Spotify payout)
- Compile `believe_faq.pdf` (public website content + 6 manual Q&A pairs)
- Set up Pinecone account (free serverless tier); create index `believe-royalties`
- Write ingestion script: load PDFs → chunk → embed → upsert to Pinecone with metadata (artist, month, doc_type)
- Verify retrieval: run 3 test queries with metadata filters, confirm correct chunks returned

Milestone: `retrieval_test.py` returns correct chunks for "March payout" and "Spotify streams"

### Phase 2: LangGraph Agent (Days 3–4)
**Goal:** 4-node graph runs end-to-end on test questions

Tasks:
- Define `RoyaltyAgentState` TypedDict
- Build Node 1: question classifier (Claude prompt, returns question_type)
- Build Node 2: RAG retriever (Pinecone query filtered by metadata)
- Build Node 3: reasoning node (Claude compares docs, generates explanation)
- Build Node 4: confidence router (conditional edge → answer or escalate)
- Connect nodes into LangGraph graph
- Test with 5 predefined questions; verify routing works correctly

Milestone: Agent correctly identifies Spotify DE as cause of March payout drop

### Phase 3: n8n Integration (Day 5)
**Goal:** Full flow from webhook to Google Sheets + Slack

Tasks:
- Create n8n workflow with webhook trigger node
- Add HTTP Request node → calls LangGraph agent (Python running locally or on ngrok)
- Add Google Sheets node → appends row (question, answer, timestamp, escalation flag)
- Add IF node → checks escalation flag
- Add Slack node → sends alert message to account manager channel on escalation
- Test full flow end-to-end with all 5 test questions

Milestone: All 5 questions create a Sheets row; escalation question triggers Slack message

### Phase 4: Documentation and Submission (Day 6)
**Goal:** GitHub repo ready to submit

Tasks:
- Write `README.md` with file map and setup instructions
- Write `lab_summary.md` (reflection paragraph)
- Screenshot n8n workflow, Sheets log, Slack alert
- Record or document 2–3 example agent interactions
- Push all files to GitHub

### Timeline Summary

| Phase | Days | Deliverable |
|---|---|---|
| 1 — Data prep | 1–2 | 3 PDFs ingested in Pinecone |
| 2 — LangGraph agent | 3–4 | Working 4-node agent |
| 3 — n8n integration | 5 | Full webhook → Sheets → Slack flow |
| 4 — Documentation | 6 | GitHub repo submitted |

### Dependencies
- Anthropic API key (required from Day 2)
- Pinecone API key (free serverless tier at pinecone.io — required from Day 1)
- n8n installed locally or via n8n.io cloud (free tier sufficient)
- Google Sheets API credentials (via n8n OAuth)
- Slack workspace with a channel for alerts

### Resources Needed

| Resource | Tool | Cost |
|---|---|---|
| LLM | Anthropic Claude API | Pay-per-use (minimal for prototype) |
| Vector DB | Pinecone (serverless free tier) | Free |
| Orchestration | n8n (self-hosted or cloud free tier) | Free |
| Logging | Google Sheets | Free |
| Alerts | Slack | Free |
| Document creation | Any PDF editor or Python (reportlab) | Free |

---

## 6. Success Metrics

### MVP Validation (Demo Day)

Run these 5 test questions through the full system:

| # | Question | Expected behaviour |
|---|---|---|
| 1 | "Why was my March payout lower than February?" | Agent compares both statements, identifies Spotify DE stream drop, answers confidently |
| 2 | "How much did I earn from Apple Music in February?" | Agent retrieves Feb statement, returns €228.00 |
| 3 | "What is Believe's commission rate?" | Agent retrieves FAQ, returns 15% |
| 4 | "Why do stream counts differ between platforms?" | Agent retrieves FAQ explanation about reporting schedules |
| 5 | "Can you file a dispute on my behalf?" | Agent cannot find answer, escalates to account manager → Slack alert fires |

### Quantitative Targets

- 4/5 questions answered without escalation
- 0 hallucinated figures (all numbers traceable to source documents)
- 100% of queries logged in Google Sheets
- Escalation Slack alert fires for Question 5
- Total response time under 30 seconds per query
