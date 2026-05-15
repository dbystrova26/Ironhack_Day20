"""
ingest.py
Loads the 3 PDF documents from /data, chunks them, embeds them,
and stores them in a Pinecone index called 'believe-royalties'.

Run once before starting the agent:
    python src/ingest.py

Requirements:
    pip install pinecone-client langchain langchain-community
                langchain-anthropic pypdf sentence-transformers
"""

import os
from pathlib import Path
from time import sleep

from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

# ── Config ────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"

PINECONE_API_KEY  = os.environ["PINECONE_API_KEY"]   # export PINECONE_API_KEY=...
PINECONE_CLOUD    = "aws"                             # free tier: aws
PINECONE_REGION   = "us-east-1"                      # free tier region
INDEX_NAME        = "believe-royalties"
EMBEDDING_DIM     = 384                               # all-MiniLM-L6-v2 output size

# Documents to ingest — metadata travels with every chunk so the agent
# can filter by artist, period, or doc_type at retrieval time.
DOCUMENTS = [
    {
        "path": DATA_DIR / "nova_bloom_feb_2024.pdf",
        "metadata": {
            "artist":   "Nova Bloom",
            "month":    "February",
            "year":     "2024",
            "period":   "2024-02",
            "doc_type": "royalty_statement",
        },
    },
    {
        "path": DATA_DIR / "nova_bloom_mar_2024.pdf",
        "metadata": {
            "artist":   "Nova Bloom",
            "month":    "March",
            "year":     "2024",
            "period":   "2024-03",
            "doc_type": "royalty_statement",
        },
    },
    {
        "path": DATA_DIR / "believe_faq.pdf",
        "metadata": {
            "artist":   "all",
            "month":    "all",
            "year":     "2024",
            "period":   "all",
            "doc_type": "faq",
        },
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_or_create_index(pc: Pinecone) -> object:
    """Create the Pinecone index if it doesn't exist, then return it."""
    existing = [idx.name for idx in pc.list_indexes()]

    if INDEX_NAME not in existing:
        print(f"Creating index '{INDEX_NAME}' ...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        # Wait until the index is ready
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            print("  Waiting for index to be ready ...")
            sleep(2)
        print("  Index ready.")
    else:
        print(f"Index '{INDEX_NAME}' already exists — reusing.")

    return pc.Index(INDEX_NAME)


def chunk_document(path: Path) -> list:
    """Load a PDF and return a list of chunked Document objects."""
    loader  = PyPDFLoader(str(path))
    pages   = loader.load()
    print(f"  Pages loaded: {len(pages)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "],
    )
    return splitter.split_documents(pages)


def batch(iterable, size=100):
    """Yield successive slices of size `size` from iterable."""
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


# ── Main ingestion ─────────────────────────────────────────────────────────────

def ingest():
    print("Initialising Pinecone ...")
    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = get_or_create_index(pc)

    print("\nLoading embedding model (all-MiniLM-L6-v2) ...")
    embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    vectors_to_upsert = []

    for doc_config in DOCUMENTS:
        path          = doc_config["path"]
        base_metadata = doc_config["metadata"]

        if not path.exists():
            print(f"\nWARNING: {path.name} not found — skipping.")
            continue

        print(f"\nProcessing: {path.name}")
        chunks = chunk_document(path)
        print(f"  Chunks created: {len(chunks)}")

        texts      = [c.page_content for c in chunks]
        embeddings = embedder.embed_documents(texts)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = f"{path.stem}_chunk_{i}"
            metadata  = {
                **base_metadata,
                "source":      path.name,
                "chunk_index": i,
                "text":        chunk.page_content,  # stored so agent can retrieve raw text
            }
            vectors_to_upsert.append((vector_id, embedding, metadata))

    if not vectors_to_upsert:
        print("\nNo vectors to upsert. Check your /data folder.")
        return

    # Upsert in batches of 100 (Pinecone limit per request)
    print(f"\nUpserting {len(vectors_to_upsert)} vectors to Pinecone ...")
    for b in batch(vectors_to_upsert, size=100):
        index.upsert(vectors=b)
    print("Upsert complete.")

    # ── Verification ──────────────────────────────────────────────────────────
    print("\nVerification — test query: 'March payout Spotify'")
    test_embedding = embedder.embed_query("March payout Spotify")
    results = index.query(
        vector=test_embedding,
        top_k=2,
        include_metadata=True,
        filter={"doc_type": {"$eq": "royalty_statement"}},
    )
    for i, match in enumerate(results["matches"]):
        meta         = match["metadata"]
        text_preview = meta.get("text", "")[:120]
        print(f"  Result {i+1} [score={match['score']:.3f}] [{meta['period']}]: {text_preview}...")

    print(f"\nDone. Index '{INDEX_NAME}' is ready for the agent.")


if __name__ == "__main__":
    ingest()
