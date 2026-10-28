"""Local model server: embeddings (sentence-transformers) + rerank (cross-encoder).

Used by the backend for retrieval vectors so no patient text leaves the
deployment for embedding. Chat/transcription still go through LiteLLM.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME", "BAAI/bge-base-en-v1.5"
)
CROSS_ENCODER_MODEL = os.environ.get(
    "CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)


class EmbedRequest(BaseModel):
    texts: list[str]


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sentence_transformers import CrossEncoder, SentenceTransformer

    app.state.embedder = SentenceTransformer(
        EMBEDDING_MODEL_NAME, trust_remote_code=True
    )
    app.state.reranker = CrossEncoder(CROSS_ENCODER_MODEL)
    yield


app = FastAPI(title="Virtual MDT model server", lifespan=lifespan)


@app.get("/health")
def health():
    embedder = app.state.embedder
    return {
        "status": "ok",
        "embedding_model": EMBEDDING_MODEL_NAME,
        "embedding_dim": (getattr(embedder, "get_embedding_dimension", None) or getattr(embedder, "get_sentence_embedding_dimension", None))(),
        "rerank_model": CROSS_ENCODER_MODEL,
    }


@app.post("/embed")
def embed(data: EmbedRequest):
    if not data.texts:
        raise HTTPException(status_code=400, detail="No texts provided")
    if len(data.texts) > 256:
        raise HTTPException(status_code=400, detail="At most 256 texts per request")
    vectors = app.state.embedder.encode(
        data.texts, normalize_embeddings=True, show_progress_bar=False
    )
    return {"vectors": vectors.tolist(), "dim": vectors.shape[1]}


@app.post("/rerank")
def rerank(data: RerankRequest):
    """Cross-encoder relevance scores for (query, document) pairs.

    Not wired into retrieval yet — available for a retrieve-then-rerank pass.
    """
    if not data.documents:
        raise HTTPException(status_code=400, detail="No documents provided")
    pairs = [[data.query, doc] for doc in data.documents]
    scores = app.state.reranker.predict(pairs, show_progress_bar=False)
    return {"scores": [float(s) for s in scores]}
