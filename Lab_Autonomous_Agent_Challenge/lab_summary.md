# Lab Summary

## Business Problem

This project addresses the **Document Q&A** use case from the lab options: Believe, a global music distribution company, receives hundreds of monthly queries from independent artists asking why their royalty payouts changed — for example, artist Nova Bloom asking *"Why was my March payout €155 lower than February?"* — a question that today requires an account manager to manually open two PDF statements, compare stream counts across six platforms, and write a custom email response, a process that takes hours and does not scale across Believe's roster of thousands of artists in 50+ countries.

## What the Agent Does

The Believe Royalty Q&A Agent answers questions from independent artists about their monthly royalty statements. When an artist submits a question — via a curl command in this prototype, and via a chat widget or support form in production — an n8n webhook receives it and triggers the workflow. The agent classifies the question type, retrieves the most relevant chunks from two simulated royalty PDFs and a Believe FAQ document stored in Pinecone, and passes them to Claude to reason over and generate a plain-language explanation. If Claude cannot answer with confidence — for example, if the question requires a human action such as filing a dispute — the agent flags the conversation for escalation, logs everything to Google Sheets, and fires a Slack alert to the account manager. The entire flow runs in under 30 seconds and requires no manual intervention from the Believe team for routine queries.

## Autonomy Scope

The agent is not fully autonomous by design. Following the scoping principle of delivering the smallest valuable scope, the MVP uses a human-triggered, on-demand architecture — the agent runs only when an artist submits a question. Full autonomy (proactive monitoring, scheduled statement analysis, self-initiated alerts) is scoped to v2 once the core RAG reasoning is validated. The LangGraph component demonstrates multi-step reasoning and conditional routing — the foundational agent capability — without the infrastructure risk of a fully autonomous deployment.

## Future Developments (v2)

- **n8n Schedule Trigger** — runs automatically every time a new royalty statement is uploaded to Google Drive, without an artist needing to ask anything
- **Proactive comparison** — agent detects the month-over-month delta autonomously and sends the artist a Slack or email summary unprompted
- **Drift detection** — monitors whether the escalation rate is climbing over time, which signals that the FAQ document needs updating
- **Feedback loop** — artist rates each answer; low ratings automatically trigger a review of the FAQ and retrieval quality

## Reflection

The hardest part of planning this project was resisting scope creep at the MVP definition stage — it was tempting to add multi-artist support, a proper web interface, and live Spotify API data, all of which would have made the prototype undeliverable in the time available. The decision to simulate data with two realistic fake royalty PDFs was the right call: it let the focus stay on the agent architecture rather than data engineering. If I were doing this again, I would define the five test questions *before* building anything, not after — having concrete questions upfront would have shaped the LangGraph node design and the FAQ document content from the start, rather than retrofitting them. The biggest open question is how LangGraph's confidence routing would hold up on genuinely ambiguous real-world questions where the answer partially exists in the documents but is incomplete — the current design treats confidence as binary (high/low), but in practice it likely needs a middle tier that attempts a partial answer while still flagging the account manager.

## Repository Map

```
/
├── project_plan.md               # Full 6-section project plan (main deliverable)
├── lab_summary.md                # This file — required narrative at repo root
├── README.md                     # Setup instructions, architecture, concept explanations
├── requirements.txt              # Python dependencies
├── n8n_workflow.json             # Importable n8n workflow (credentials removed)
├── data/
│   ├── nova_bloom_feb_2024.pdf   # Simulated royalty statement — February 2024
│   ├── nova_bloom_mar_2024.pdf   # Simulated royalty statement — March 2024
│   └── believe_faq.pdf           # Compiled FAQ document
├── src/
│   ├── ingest.py                 # PDF → Pinecone ingestion script
│   ├── agent.py                  # LangGraph agent (4 nodes)
│   └── serve.py                  # FastAPI server exposing agent to n8n
└── screenshots/
    ├── n8n_workflow.png          # n8n workflow canvas
    ├── sheets_log.png            # Google Sheets conversation log
    └── slack_alert.png           # Slack escalation alert
```
