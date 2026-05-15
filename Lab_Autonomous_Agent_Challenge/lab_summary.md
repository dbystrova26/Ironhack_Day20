# Lab Summary

## Reflection

The hardest part of planning this project was resisting scope creep at the MVP definition stage — it was tempting to add multi-artist support, a proper web interface, and live Spotify API data, all of which would have made the prototype undeliverable in the time available. The decision to simulate data with two realistic fake royalty PDFs was the right call: it let the focus stay on the agent architecture rather than data engineering. If I were doing this again, I would define the five test questions *before* building anything, not after — having concrete questions upfront would have shaped the LangGraph node design and the FAQ document content from the start, rather than retrofitting them. The biggest open question is how LangGraph's confidence routing would hold up on genuinely ambiguous real-world questions where the answer partially exists in the documents but is incomplete — the current design treats confidence as binary (high/low), but in practice it likely needs a middle tier that attempts a partial answer while still flagging the account manager.

## Repository Map

```
/
├── project_plan.md          # Full 6-section project plan (main deliverable)
├── lab_summary.md           # This file — reflection paragraph
├── README.md                # Setup instructions and file map
├── data/
│   ├── nova_bloom_feb_2024.pdf    # Simulated royalty statement — February
│   ├── nova_bloom_mar_2024.pdf    # Simulated royalty statement — March
│   └── believe_faq.pdf            # Compiled FAQ document
├── src/
│   ├── ingest.py            # PDF → ChromaDB ingestion script
│   ├── agent.py             # LangGraph agent (4 nodes)
│   └── serve.py             # FastAPI server exposing agent to n8n webhook
└── screenshots/
    ├── n8n_workflow.png     # n8n workflow screenshot
    ├── sheets_log.png       # Google Sheets conversation log
    └── slack_alert.png      # Slack escalation alert example
```
