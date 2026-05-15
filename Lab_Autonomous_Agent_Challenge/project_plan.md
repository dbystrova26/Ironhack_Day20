# Autonomous Agent Project Plan
**Client:** Believe (Germany) — Groove Attack / Nuclear Blast division  
**Consultant:** Daria Bystrova  
**Date:** May 2025  
**Lab:** Ironhack — Autonomous Agent Challenge Lab

---

## 1. Use Case

### Selected Use Case
**Option C: Document Q&A System** — Answer questions about internal company documents, support multiple document types, provide citations and source tracking.

Applied to Believe: a music distribution company where artists and labels regularly ask questions about their monthly royalty statements that currently require manual account manager responses.

### Problem Statement
Artists and independent labels distributed by Believe regularly contact their account managers with questions about royalty statements: why payouts changed month-over-month, which platform drove a drop, or what a specific deduction means. This process is entirely manual — account managers read PDF statements, cross-reference platform reports, and write custom email responses. It does not scale as Believe's roster grows across 50+ countries.

**Concrete example:** Artist Nova Bloom receives her March 2024 statement showing €630.40 net payout, down from €785.70 in February. She messages her account manager: *"Why was my March payout lower?"* The account manager must open both PDFs, compare six platform rows, identify the Spotify DE stream drop, and write a reply — a process taking 30–60 minutes per query, multiplied across hundreds of artists monthly.

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

### Technology Selection Framework

Answering the 5 key scoping questions from the course framework:

| Question | Answer | Technology implication |
|---|---|---|
| Does it need external knowledge? | Yes — royalty PDFs and FAQ not in LLM training data | RAG + Vector DB required |
| Does it need to interact with external systems? | Yes — Google Sheets logging, Slack alerts | n8n integrations required |
| Does it need multi-step reasoning? | Yes — classify, retrieve, compare, route | LangGraph structured graph |
| Does it need to integrate with business systems? | Yes — Sheets and Slack are Believe's business tools | n8n orchestration |
| Does it need to be autonomous (run without human input)? | Partially — triggered on-demand in MVP, scheduled in v2 | Webhook trigger + error handling |

### Selected Technologies

| Layer | Technology | Purpose |
|---|---|---|
| Core LLM | Anthropic Claude (claude-sonnet-4-5) | Document reasoning, comparison, explanation generation |
| Vector DB | Pinecone (serverless, free tier) | Stores and retrieves chunked royalty statements and FAQ |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Converts document chunks to searchable vectors — local, no API key |
| Agent Framework | LangGraph | Multi-step reasoning graph: classify → retrieve → reason → route |
| Orchestration | n8n | Webhook trigger, Google Sheets logging, Slack escalation |
| Document ingestion | LangChain + PyPDF | Parse PDFs into chunks for Pinecone |
| API server | FastAPI + uvicorn | Exposes LangGraph agent as HTTP endpoint for n8n to call |
| Tunnel (dev only) | ngrok | Exposes local FastAPI server to n8n cloud during development |

### Justification for Choices

**Claude over GPT-4:** Claude performs strongly on document-heavy reasoning tasks and is the natural choice given Anthropic API access. Its large context window handles multi-page royalty statements reliably.

**LangGraph over plain LangChain:** The agent needs a guaranteed decision path — classify the question type, retrieve relevant documents, reason, then route to answer or escalate. A plain LangChain ReAct agent loops freely and cannot guarantee this structure. LangGraph's explicit node-and-edge architecture gives full control over the flow, including the conditional escalation edge.

**Pinecone over ChromaDB:** Pinecone's serverless free tier requires no local infrastructure and supports metadata filtering out of the box — critical for filtering chunks by artist, month, and document type. It scales directly to production if Believe adopts the system with no migration needed.

**n8n over custom code:** n8n handles the business integration layer (Google Sheets logging, Slack alerts) without custom code. It provides a webhook endpoint as the agent's entry point — meaning the agent can be triggered from any Believe tool in the future without changing the Python code.

**FastAPI as the bridge:** LangGraph runs as a Python process; n8n needs an HTTP endpoint to call. FastAPI provides a lightweight server that exposes the agent at `/ask`, accepting JSON and returning a structured response that n8n can parse and route.

### Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| GPT-4 | No access; Claude equivalent in capability for this task |
| ChromaDB | Local-only; requires migration to move to production; Pinecone free tier sufficient |
| Plain LangChain ReAct agent | No structured routing; can't guarantee escalation logic fires reliably |
| Pure n8n AI nodes | n8n's built-in AI nodes lack the document reasoning depth and conditional routing needed |
| Streamlit UI | Adds complexity; curl/webhook is sufficient for prototype validation |

---

## 3. MVP Scope

### Included Features (MVP)

- **RAG over 2 document types:**
  - Monthly royalty statements (2 months, simulated PDFs — February and March 2024)
  - Believe FAQ document (compiled from public website + manually written royalty Q&A)
- **LangGraph agent with 4 nodes:**
  - Node 1: Classify question type (comparison / platform-specific / FAQ / general)
  - Node 2: Retrieve relevant document chunks from Pinecone with metadata filters
  - Node 3: Reason and generate answer using Claude; assign confidence (high/low)
  - Node 4: Confidence check → conditional edge to answer or escalation
- **n8n orchestration workflow (5 nodes):**
  - Webhook trigger — receives artist question via HTTP POST
  - HTTP Request node — calls FastAPI /ask endpoint via ngrok tunnel
  - Google Sheets node — appends row for every query (question, answer, confidence, escalated, sources, timestamp)
  - IF node — checks `escalated == true`
  - Slack node — fires alert to `#believe-royalty-agent-update` on escalation only
- **Basic conversation memory:** last 3 turns stored in LangGraph state
- **Single artist:** all documents belong to simulated artist "Nova Bloom"
- **English only**
- **Simulated data:** realistic fake royalty statements generated with Python reportlab; no connection to Believe's real systems

### Explicitly Out of Scope (v2+)

- Multi-language support (German, French — relevant for Believe's markets)
- Multi-artist or label-level queries
- Live API connection to Spotify / Apple Music data
- Real Believe internal data or systems
- Automated royalty dispute filing
- Mobile or web app interface (v1 uses curl; production would use Backstage portal widget)
- CRM integration
- Analytics dashboard for account managers
- Voice interface
- Proactive scheduled monitoring (v2 — see Future Developments)

### Success Metrics for MVP

| Metric | Target | Result |
|---|---|---|
| Questions answered without escalation | ≥ 4 out of 5 test questions | ✅ 4/5 answered confidently |
| Correct identification of payout delta | Spotify DE stream drop identified | ✅ Agent cited exact −44,000 streams |
| Google Sheets log entry per query | 100% | ✅ All queries logged |
| Slack alert on escalation | Demonstrated at least once | ✅ Fired on "Can you refund my missing payment from 2023?" |
| End-to-end response time | < 30 seconds | ✅ ~15 seconds average |

---

## 4. Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Claude hallucinates numbers not present in documents | Medium | High | Prompt instructs Claude to only cite figures explicitly found in retrieved chunks; source document referenced in every answer |
| Pinecone retrieves wrong document chunks (wrong month) | Medium | High | Metadata filters (`period`, `doc_type`) applied on every retrieval call; verified with test queries after ingestion |
| n8n webhook times out before LangGraph returns answer | Low | Medium | FastAPI server targets < 15s response; n8n HTTP node timeout set to 60s |
| LangGraph node gets stuck in loop | Low | Medium | Graph has no loops by design; all paths terminate at `answer` or `escalate` nodes |
| API rate limits on Claude during demo | Low | Low | Demo uses 5 pre-written test questions; well within free tier limits |
| ngrok tunnel drops during demo | Medium | Medium | Restart ngrok and update HTTP Request node URL; noted in runbook |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Artists distrust AI-generated royalty explanations | High | High | Every answer cites source document and period ("Based on your March 2024 statement…"); escalation path always available |
| Scope creep during prototype | High | Medium | MVP strictly limited to 1 artist, 2 PDFs, 4 LangGraph nodes — documented and enforced |
| Account managers resist adoption | Medium | Medium | Framed as triage tool, not replacement; all conversations still logged for manager review; escalation always routes to human |

### Data Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Simulated data not realistic enough | Medium | Medium | Used real Believe commission rate (15%), real platform names, realistic stream counts based on public data |
| FAQ document missing key questions | Medium | Low | 5 test questions defined before building; FAQ written to cover all 5 |
| Artist data privacy in real deployment | High | High | Out of scope for MVP; flagged for v2 GDPR compliance planning |

---

## 5. Implementation Plan

### Phase 1: Data Preparation (Days 1–2)
**Goal:** All documents ingested and retrievable from Pinecone

Tasks:
- Generate `nova_bloom_feb_2024.pdf` and `nova_bloom_mar_2024.pdf` using Python reportlab — realistic royalty statements with platform breakdown, financial summary, and month-over-month comparison table
- Compile `believe_faq.pdf` from Believe's public website + 6 manually written royalty Q&A pairs
- Set up Pinecone account (free serverless tier); create index `believe-royalties` (384 dimensions, cosine metric)
- Write `src/ingest.py`: load PDFs → chunk (500 chars, 50 overlap) → embed (all-MiniLM-L6-v2) → upsert to Pinecone with metadata
- Verify retrieval: test query "March payout Spotify" returns correct chunks from both statements

Milestone: Verification query returns chunks from `nova_bloom_mar_2024.pdf` with score > 0.4

### Phase 2: LangGraph Agent (Days 3–4)
**Goal:** 4-node graph runs end-to-end on all 5 test questions

Tasks:
- Define `RoyaltyAgentState` TypedDict with 8 fields
- Build Node 1: question classifier (Claude prompt → comparison / platform / faq / general)
- Build Node 2: RAG retriever (Pinecone query with metadata filter per question type; top_k 4–6)
- Build Node 3: reasoning node (Claude system prompt + retrieved chunks → answer + CONFIDENCE tag)
- Build Node 4: confidence router (conditional edge → `format_answer` or `format_escalation`)
- Write `src/serve.py`: FastAPI app with POST `/ask` and GET `/health`
- Test all 5 questions via `python src/agent.py`

Milestone: Agent correctly identifies Spotify DE as cause of March payout drop with confidence: high

### Phase 3: n8n Integration (Day 5)
**Goal:** Full flow from webhook to Google Sheets + Slack

Tasks:
- Create n8n workflow with Webhook node (path: `believe-royalty`)
- Start FastAPI server locally; expose with ngrok
- Configure HTTP Request node → POST to ngrok URL `/ask`
- Create Google Sheet "Believe Royalty Agent Log" with 6 column headers
- Configure Google Sheets node → Append Row with all 6 fields
- Configure IF node → `escalated == true` with type conversion enabled
- Create Slack app with `chat:write` and `chat:write.public` scopes; connect via OAuth
- Configure Slack node → send escalation message to `#believe-royalty-agent-update`
- Activate workflow; test all 5 questions via curl
- Export workflow as `n8n_workflow.json` (credentials removed)

Milestone: All 5 questions create Sheets rows; escalation question fires Slack alert

### Phase 4: Documentation and Submission (Day 6)
**Goal:** GitHub repo ready to submit

Tasks:
- Screenshot n8n workflow canvas, Google Sheets log, Slack alert
- Write `README.md` with concept explanations (webhook, ngrok, integrations) and setup instructions
- Write `lab_summary.md` (business problem, autonomy scope, reflection)
- Push all files to GitHub; verify repo contains only lab materials
- Submit GitHub URL

### Timeline Summary

| Phase | Days | Deliverable |
|---|---|---|
| 1 — Data prep | 1–2 | 3 PDFs generated and ingested in Pinecone |
| 2 — LangGraph agent | 3–4 | Working 4-node agent + FastAPI server |
| 3 — n8n integration | 5 | Full webhook → Sheets → Slack flow |
| 4 — Documentation | 6 | GitHub repo submitted |

### Dependencies
- Anthropic API key (required from Day 2)
- Pinecone API key — free serverless tier at pinecone.io (required from Day 1)
- n8n cloud account — free tier at app.n8n.io
- Google account — Google Sheets API credentials via n8n OAuth
- Slack workspace with an alerts channel + Slack app with `chat:write.public` scope
- ngrok account — free tier, authtoken required

### Resources Needed

| Resource | Tool | Cost |
|---|---|---|
| Core LLM | Anthropic Claude API (claude-sonnet-4-5) | Pay-per-use (~$0.10 for demo) |
| Vector DB | Pinecone serverless free tier | Free |
| Orchestration | n8n cloud free tier | Free |
| Logging | Google Sheets | Free |
| Alerts | Slack free workspace | Free |
| Tunnel | ngrok free tier | Free |
| PDF generation | Python reportlab | Free |

---

## 6. Success Metrics

### MVP Validation — 5 Demo Questions

| # | Question | Expected behaviour | Result |
|---|---|---|---|
| 1 | "Why was my March payout lower than February?" | Identifies Spotify DE drop of 44,000 streams, cites both statements | ✅ Passed |
| 2 | "How much did I earn from Apple Music in February?" | Returns €228.00 from Feb statement | ✅ Passed |
| 3 | "What is Believe's commission rate?" | Returns 15% from FAQ | ✅ Passed |
| 4 | "Why do stream counts differ between platforms?" | Explains reporting windows from FAQ | ✅ Passed |
| 5 | "Can you refund my missing payment from 2023?" | Low confidence → escalates → Slack alert fires | ✅ Escalated correctly |

### Quantitative Targets — All Met

- 4/5 questions answered without escalation ✅
- 0 hallucinated figures — all numbers traceable to source documents ✅
- 100% of queries logged in Google Sheets ✅
- Escalation Slack alert fired for low-confidence question ✅
- Total response time under 30 seconds per query ✅

### Learnings and Next Steps

The prototype validated the core RAG + LangGraph architecture. Key learnings:

- Metadata filtering in Pinecone is essential — without it, the agent retrieves chunks from the wrong month and generates incorrect comparisons
- Claude's confidence self-assessment works well for clear escalation cases (missing data, out-of-scope requests) but needs refinement for borderline cases
- The n8n webhook + ngrok approach works for demos but requires a deployed server for production

Next steps for v2: replace ngrok with a deployed FastAPI server, add multi-artist support, implement scheduled proactive comparison, and add a feedback loop where low-rated answers trigger FAQ updates.
