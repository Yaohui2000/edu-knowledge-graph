import math
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from .embed import embed

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

_chunks: list[dict] = []   # {text, source, chapter, page_start}
_faiss_index = None        # faiss.IndexFlatIP
_bm25: BM25Okapi | None = None


def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _rebuild_bm25():
    global _bm25
    tokenized = [list(c["text"]) for c in _chunks]  # char-level for Chinese
    _bm25 = BM25Okapi(tokenized) if tokenized else None


def build_index(chapters: list[dict], source: str) -> None:
    global _faiss_index
    texts, metas = [], []
    for ch in chapters:
        for chunk in _chunk(ch["content"]):
            texts.append(chunk)
            metas.append({"source": source, "chapter": ch["title"],
                          "page_start": ch.get("page_start", 0)})
    if not texts:
        return
    embeddings = embed(texts)
    vecs = np.array(embeddings, dtype="float32")
    faiss.normalize_L2(vecs)

    if _faiss_index is None or _faiss_index.d != vecs.shape[1]:
        _faiss_index = faiss.IndexFlatIP(vecs.shape[1])

    for text, meta in zip(texts, metas):
        _chunks.append({**meta, "text": text})
    _faiss_index.add(vecs)
    _rebuild_bm25()


def search(query: str, top_k: int = 5) -> list[dict]:
    if not _chunks or _faiss_index is None:
        return []

    # Vector search
    q_vec = np.array(embed([query]), dtype="float32")
    faiss.normalize_L2(q_vec)
    scores, indices = _faiss_index.search(q_vec, min(top_k * 2, len(_chunks)))
    vec_hits = {int(idx): float(scores[0][i]) for i, idx in enumerate(indices[0]) if idx >= 0}

    # BM25 search
    bm25_hits = {}
    if _bm25:
        q_tokens = list(query)
        bm25_scores = _bm25.get_scores(q_tokens)
        top_bm25 = np.argsort(bm25_scores)[::-1][:top_k * 2]
        max_bm25 = bm25_scores[top_bm25[0]] if len(top_bm25) else 1
        for idx in top_bm25:
            if bm25_scores[idx] > 0:
                bm25_hits[int(idx)] = float(bm25_scores[idx]) / max(max_bm25, 1e-9)

    # Merge: union, re-rank by combined score (0.7 vec + 0.3 bm25)
    all_ids = set(vec_hits) | set(bm25_hits)
    ranked = sorted(all_ids,
                    key=lambda i: 0.7 * vec_hits.get(i, 0) + 0.3 * bm25_hits.get(i, 0),
                    reverse=True)

    results = []
    for idx in ranked[:top_k]:
        c = _chunks[idx]
        combined = round(0.7 * vec_hits.get(idx, 0) + 0.3 * bm25_hits.get(idx, 0), 4)
        results.append({"text": c["text"], "source": c["source"],
                        "chapter": c["chapter"], "page_start": c["page_start"],
                        "score": combined})
    return results


def index_stats() -> dict:
    sources = list({c["source"] for c in _chunks})
    return {"sources": len(sources), "chunks": len(_chunks), "source_list": sources}


def load_index_from_chapters(chapters: list[dict], source: str) -> None:
    global _chunks, _faiss_index
    # Remove existing entries for this source
    keep = [c for c in _chunks if c["source"] != source]
    if len(keep) != len(_chunks):
        # Rebuild faiss from scratch with remaining chunks
        _chunks = []
        _faiss_index = None
        if keep:
            # Re-embed kept chunks
            texts = [c["text"] for c in keep]
            embeddings = embed(texts)
            vecs = np.array(embeddings, dtype="float32")
            faiss.normalize_L2(vecs)
            _faiss_index = faiss.IndexFlatIP(vecs.shape[1])
            _faiss_index.add(vecs)
            _chunks = keep
    build_index(chapters, source)
