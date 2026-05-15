"""
agent.py
LangGraph agent with 4 nodes:
  1. classify  — what type of question is this?
  2. retrieve  — fetch relevant chunks from Pinecone
  3. reason    — Claude compares docs and builds an answer
  4. route     — high confidence → answer | low confidence → escalate

Usage (direct):
    python src/agent.py

Requirements:
    pip install langgraph langchain-anthropic pinecone-client sentence-transformers
"""

import os
from typing import TypedDict, Literal

from anthropic import Anthropic
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langgraph.graph import StateGraph, END
from pinecone import Pinecone

# ── Config ────────────────────────────────────────────────────────────────────

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
INDEX_NAME = "believe-royalties"
MODEL = "claude-sonnet-4-20250514"

# Initialise clients once at module load (reused across requests)
_pc = Pinecone(api_key=PINECONE_API_KEY)
_index = _pc.Index(INDEX_NAME)
_embedder = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
_claude = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── State schema ──────────────────────────────────────────────────────────────

class RoyaltyAgentState(TypedDict):
    question: str               # original artist question
    history: list[dict]         # last 3 turns [{"role": ..., "content": ...}]
    question_type: str          # filled by Node 1: comparison|platform|faq|general
    retrieved_docs: list[dict]  # filled by Node 2: list of {text, metadata}
    reasoning: str              # filled by Node 3: Claude's internal reasoning
    answer: str                 # filled by Node 3: final answer text
    confidence: str             # filled by Node 3: "high" or "low"
    escalation_reason: str      # filled by Node 4 if confidence is low
    sources: list[str]          # filled by Node 3: which docs were cited

# ── Node 1: Classify ──────────────────────────────────────────────────────────

def classify_question(state: RoyaltyAgentState) -> dict:
    """
    Classify the question into one of four types so the retriever
    can apply the right metadata filter.

    comparison   → needs both royalty statements (compare months)
    platform     → needs one royalty statement (specific platform query)
    faq          → needs the FAQ document
    general      → needs all documents
    """
    prompt = f"""You are classifying an artist's question about their music royalties.

Classify the question into exactly one of these types:
- comparison: asks about differences between two time periods or months
- platform: asks about a specific streaming platform (Spotify, Apple Music, etc.)
- faq: asks about how Believe works, commission rates, processes, or policies
- general: anything else about royalties or payouts

Question: "{state['question']}"

Reply with just the single word type. No explanation."""

    response = _claude.messages.create(
        model=MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    question_type = response.content[0].text.strip().lower()

    # Fallback to general if Claude returns something unexpected
    if question_type not in ("comparison", "platform", "faq", "general"):
        question_type = "general"

    print(f"[Node 1] Question type: {question_type}")
    return {"question_type": question_type}


# ── Node 2: Retrieve ──────────────────────────────────────────────────────────

def retrieve_documents(state: RoyaltyAgentState) -> dict:
    """
    Query Pinecone with a metadata filter matched to the question type.
    Returns the top-k most relevant chunks as {text, metadata} dicts.
    """
    question_type = state["question_type"]
    question = state["question"]

    # Build the right filter for each question type
    filter_map = {
        "comparison": {"doc_type": {"$eq": "royalty_statement"}},
        "platform":   {"doc_type": {"$eq": "royalty_statement"}},
        "faq":        {"doc_type": {"$eq": "faq"}},
        "general":    {},  # no filter — search everything
    }
    pinecone_filter = filter_map.get(question_type, {})

    # For comparisons we want more chunks (both months)
    top_k = 6 if question_type == "comparison" else 4

    query_embedding = _embedder.embed_query(question)
    results = _index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=pinecone_filter if pinecone_filter else None,
    )

    retrieved_docs = [
        {
            "text": match["metadata"].get("text", ""),
            "metadata": {k: v for k, v in match["metadata"].items() if k != "text"},
            "score": match["score"],
        }
        for match in results["matches"]
    ]

    print(f"[Node 2] Retrieved {len(retrieved_docs)} chunks (filter: {pinecone_filter})")
    return {"retrieved_docs": retrieved_docs}


# ── Node 3: Reason ────────────────────────────────────────────────────────────

def reason_and_answer(state: RoyaltyAgentState) -> dict:
    """
    Send the retrieved chunks + conversation history to Claude.
    Claude reasons over the documents and produces:
      - A clear answer for the artist
      - A confidence rating (high / low)
      - The list of source documents cited
    """
    # Format retrieved docs for the prompt
    docs_text = ""
    source_names = []
    for i, doc in enumerate(state["retrieved_docs"]):
        meta = doc["metadata"]
        label = f"[Doc {i+1}: {meta.get('source', 'unknown')} | {meta.get('period', '')}]"
        docs_text += f"\n{label}\n{doc['text']}\n"
        source_names.append(meta.get("source", "unknown"))

    # Build conversation history (last 3 turns)
    history_text = ""
    for turn in state.get("history", []):
        role = "Artist" if turn["role"] == "user" else "Agent"
        history_text += f"{role}: {turn['content']}\n"

    system_prompt = """You are a helpful royalty assistant for Believe, a music distribution company.
You answer questions from artists and labels about their royalty statements and payouts.

Rules:
- Only use information explicitly present in the provided documents.
- Never invent or estimate numbers. If a figure is not in the documents, say so.
- Always cite which document and time period your answer comes from.
- Be clear, friendly, and concise. Artists are not finance experts.
- If the question cannot be answered confidently from the documents, say so honestly.

At the end of your response, on a new line, write exactly:
CONFIDENCE: high
or
CONFIDENCE: low

Use "low" if: the documents do not contain enough information to answer fully,
the question requires data not present in the retrieved chunks,
or the question involves actions (like filing a dispute) that need human involvement."""

    user_message = f"""Conversation so far:
{history_text if history_text else "(no previous turns)"}

Retrieved documents:
{docs_text}

Artist's question: {state['question']}

Please answer the question based only on the documents above."""

    response = _claude.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    full_response = response.content[0].text.strip()

    # Parse confidence from the last line
    confidence = "low"  # safe default
    answer = full_response
    if "CONFIDENCE:" in full_response:
        parts = full_response.rsplit("CONFIDENCE:", 1)
        answer = parts[0].strip()
        confidence_raw = parts[1].strip().lower()
        confidence = "high" if "high" in confidence_raw else "low"

    # Deduplicate sources
    sources = list(dict.fromkeys(source_names))

    print(f"[Node 3] Confidence: {confidence} | Sources: {sources}")
    return {
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "reasoning": full_response,
    }


# ── Node 4: Route ─────────────────────────────────────────────────────────────

def route(state: RoyaltyAgentState) -> dict:
    """
    Decides whether to return the answer or flag for escalation.
    This node only sets the escalation_reason — the conditional edge
    below determines which branch the graph takes next.
    """
    if state["confidence"] == "low":
        reason = (
            "The agent could not find sufficient information in the available "
            "documents to answer this question confidently. "
            f"Original question: '{state['question']}'"
        )
        print("[Node 4] → Escalating to account manager")
        return {"escalation_reason": reason}

    print("[Node 4] → Returning answer to artist")
    return {"escalation_reason": ""}


def should_escalate(state: RoyaltyAgentState) -> Literal["escalate", "answer"]:
    """Conditional edge: reads confidence to pick the next node."""
    return "escalate" if state["confidence"] == "low" else "answer"


# ── Terminal nodes ─────────────────────────────────────────────────────────────

def format_answer(state: RoyaltyAgentState) -> dict:
    """High-confidence path: package the answer for the API response."""
    return state  # answer already set by Node 3


def format_escalation(state: RoyaltyAgentState) -> dict:
    """Low-confidence path: append an escalation note to the answer."""
    escalation_note = (
        "\n\n---\n"
        "I wasn't able to answer this fully from your documents. "
        "Your Believe account manager has been notified and will follow up with you shortly."
    )
    return {"answer": state["answer"] + escalation_note}


# ── Build the graph ───────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(RoyaltyAgentState)

    # Register nodes
    graph.add_node("classify", classify_question)
    graph.add_node("retrieve", retrieve_documents)
    graph.add_node("reason",   reason_and_answer)
    graph.add_node("route",    route)
    graph.add_node("answer",   format_answer)
    graph.add_node("escalate", format_escalation)

    # Linear edges
    graph.set_entry_point("classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "reason")
    graph.add_edge("reason",   "route")

    # Conditional edge after route
    graph.add_conditional_edges(
        "route",
        should_escalate,
        {"answer": "answer", "escalate": "escalate"},
    )

    # Both terminal nodes end the graph
    graph.add_edge("answer",   END)
    graph.add_edge("escalate", END)

    return graph.compile()


# ── Public interface ──────────────────────────────────────────────────────────

# Compile once at import time
_graph = build_graph()


def ask(question: str, history: list[dict] | None = None) -> dict:
    """
    Main entry point called by serve.py.

    Args:
        question: The artist's question string.
        history:  List of previous turns [{"role": "user"|"assistant", "content": "..."}]
                  Pass the last 3 turns maximum.

    Returns:
        {
            "answer":           str,   # response text for the artist
            "confidence":       str,   # "high" or "low"
            "escalated":        bool,  # True if routed to account manager
            "escalation_reason": str,  # non-empty only when escalated
            "sources":          list,  # document filenames cited
            "question_type":    str,   # classification from Node 1
        }
    """
    initial_state: RoyaltyAgentState = {
        "question":         question,
        "history":          (history or [])[-6:],  # keep last 3 turns (6 messages)
        "question_type":    "",
        "retrieved_docs":   [],
        "reasoning":        "",
        "answer":           "",
        "confidence":       "",
        "escalation_reason": "",
        "sources":          [],
    }

    final_state = _graph.invoke(initial_state)

    return {
        "answer":            final_state["answer"],
        "confidence":        final_state["confidence"],
        "escalated":         final_state["confidence"] == "low",
        "escalation_reason": final_state["escalation_reason"],
        "sources":           final_state["sources"],
        "question_type":     final_state["question_type"],
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_questions = [
        "Why was my March payout lower than February?",
        "How much did I earn from Apple Music in February?",
        "What is Believe's commission rate?",
        "Why do stream counts differ between platforms?",
        "Can you file a dispute on my behalf?",
    ]

    history = []
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"QUESTION: {q}")
        print("="*60)

        result = ask(q, history)

        print(f"ANSWER:\n{result['answer']}")
        print(f"\nType: {result['question_type']} | "
              f"Confidence: {result['confidence']} | "
              f"Escalated: {result['escalated']}")
        print(f"Sources: {result['sources']}")

        # Append to history for next turn (simulates conversation memory)
        history.append({"role": "user",      "content": q})
        history.append({"role": "assistant", "content": result["answer"]})
        history = history[-6:]  # keep last 3 turns
