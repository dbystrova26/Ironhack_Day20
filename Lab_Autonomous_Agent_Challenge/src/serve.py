"""
serve.py
Thin FastAPI wrapper around the LangGraph agent.
n8n calls POST /ask with the artist's question and conversation history.

Start the server:
    uvicorn src.serve:app --port 8000 --reload

For n8n running locally, expose with ngrok:
    ngrok http 8000
    → copy the https://xxxxx.ngrok.io URL into n8n's HTTP Request node

Endpoints:
    POST /ask      — main agent endpoint
    GET  /health   — liveness check for n8n or monitoring
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import traceback

from src.agent import ask  # LangGraph agent

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Believe Royalty Q&A Agent",
    description="Answers artist royalty questions using RAG over Believe statements and FAQ.",
    version="1.0.0",
)

# ── Request / Response schemas ────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    role: str     # "user" or "assistant"
    content: str


class AskRequest(BaseModel):
    question: str
    history: Optional[list[ConversationTurn]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Why was my March payout lower than February?",
                "history": [],
            }
        }


class AskResponse(BaseModel):
    answer: str
    confidence: str           # "high" or "low"
    escalated: bool           # True = account manager notified
    escalation_reason: str    # non-empty only when escalated
    sources: list[str]        # document filenames cited
    question_type: str        # comparison | platform | faq | general


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """
    n8n can poll this endpoint to verify the agent is running.
    Returns 200 OK when the server is up.
    """
    return {"status": "ok", "service": "believe-royalty-agent"}


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest):
    """
    Main endpoint called by n8n's HTTP Request node.

    n8n workflow:
      Webhook (artist question)
        → HTTP Request POST /ask  ← this endpoint
        → Google Sheets (log full response)
        → IF escalated == true
            → Slack alert to account manager

    The full JSON response is returned so n8n can:
      - Log question + answer + confidence + sources to Google Sheets
      - Check the `escalated` field with an IF node
      - Pass `escalation_reason` to the Slack message body
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    # Convert Pydantic models to plain dicts for the agent
    history_dicts = [
        {"role": turn.role, "content": turn.content}
        for turn in (request.history or [])
    ]

    try:
        result = ask(
            question=request.question.strip(),
            history=history_dicts,
        )
    except Exception as e:
        # Log the full traceback server-side; return a safe error to n8n
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}. Check server logs for details.",
        )

    return AskResponse(**result)


# ── n8n integration notes (printed on startup) ────────────────────────────────

@app.on_event("startup")
def print_startup_info():
    print("\n" + "="*55)
    print("  Believe Royalty Q&A Agent — server started")
    print("="*55)
    print("  POST http://localhost:8000/ask")
    print("  GET  http://localhost:8000/health")
    print("\n  n8n HTTP Request node config:")
    print("    Method:       POST")
    print("    URL:          <ngrok-url>/ask")
    print("    Body type:    JSON")
    print("    Body:")
    print('      {')
    print('        "question": "{{ $json.question }}",')
    print('        "history":  []')
    print('      }')
    print("\n  Response fields available in n8n:")
    print("    {{ $json.answer }}            → send to artist")
    print("    {{ $json.escalated }}         → IF node condition")
    print("    {{ $json.escalation_reason }} → Slack message body")
    print("    {{ $json.confidence }}        → log to Sheets")
    print("    {{ $json.sources }}           → log to Sheets")
    print("    {{ $json.question_type }}     → log to Sheets")
    print("="*55 + "\n")
