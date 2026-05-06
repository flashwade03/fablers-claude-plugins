#!/usr/bin/env python3
"""Hybrid search script for the fablers-agentic-rag plugin.

Usage:
    python3 search.py --data-dir /path/to/data --queries "q1" "q2" \\
        [--top-k 20] [--per-query-min 2] [--provider gemini|openai]

Provider-specific embeddings are loaded from:
    {data_dir}/embeddings/{provider}/embeddings.npz

chunks.json and bm25_corpus.json live at {data_dir}/ (provider-independent).

Requires: numpy, rank_bm25, and the provider's SDK (openai or google-genai).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

import config
import embedder


# --- Config ---
HYBRID_ALPHA = 0.6  # vector weight (1 - alpha = BM25 weight)
DEFAULT_TOP_K = 20


# --- Vector Search ---
def vector_search(query_embedding: np.ndarray, embeddings: np.ndarray,
                  chunks: list, top_k: int) -> list:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normalized = embeddings / norms

    query_norm = np.linalg.norm(query_embedding)
    if query_norm == 0:
        return []
    query_normalized = query_embedding / query_norm

    similarities = np.dot(normalized, query_normalized)
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    results = []
    for idx in top_indices:
        chunk = chunks[idx]
        results.append({
            "chunk_id": chunk["chunk_id"],
            "score": float(similarities[idx]),
        })
    return results


# --- BM25 Search ---
def bm25_search(query: str, bm25_data: dict, top_k: int) -> list:
    corpus_tokens = bm25_data["corpus_tokens"]
    chunk_ids = bm25_data["chunk_ids"]
    bm25 = BM25Okapi(corpus_tokens)

    query_tokens = re.sub(r'[^\w\s]', ' ', query.lower()).split()
    scores = bm25.get_scores(query_tokens)
    top_indices = scores.argsort()[-top_k:][::-1]

    return [(chunk_ids[i], float(scores[i])) for i in top_indices]


# --- Hybrid Search ---
def hybrid_search(query: str, embeddings: np.ndarray, chunks: list,
                  bm25_data: dict, top_k: int,
                  provider: str) -> list:
    query_embedding = embedder.embed_query(query, provider=provider)

    vector_results = vector_search(query_embedding, embeddings, chunks, top_k * 2)
    vector_scores = {r["chunk_id"]: r["score"] for r in vector_results}

    bm25_results = bm25_search(query, bm25_data, top_k * 2)
    bm25_scores = dict(bm25_results)

    if bm25_scores:
        max_bm25 = max(bm25_scores.values())
        if max_bm25 > 0:
            bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}

    all_chunk_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
    combined = {}
    for cid in all_chunk_ids:
        vs = vector_scores.get(cid, 0)
        bs = bm25_scores.get(cid, 0)
        combined[cid] = HYBRID_ALPHA * vs + (1 - HYBRID_ALPHA) * bs

    sorted_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)

    chunk_map = {c["chunk_id"]: c for c in chunks}
    results = []
    for cid in sorted_ids[:top_k]:
        chunk = chunk_map.get(cid)
        if chunk:
            result = {
                "chunk_id": cid,
                "text": chunk["text"],
                "score": round(combined[cid], 4),
                "matched_query": query,
            }
            for key in ("heading", "heading_level", "page_range", "source_file",
                        "chapter_number", "chapter_title", "section_title"):
                if key in chunk:
                    result[key] = chunk[key]
            results.append(result)
    return results


def _read_settings(settings_path_override: str = "") -> dict:
    """Read the plugin settings file and return parsed frontmatter values."""
    candidates = []
    if settings_path_override:
        candidates.append(Path(settings_path_override))
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        candidates.append(Path(project_dir) / ".claude" / "fablers-agentic-rag.local.md")
    candidates.append(Path.cwd() / ".claude" / "fablers-agentic-rag.local.md")

    wanted = ("embedding_provider", "openai_api_key", "gemini_api_key")
    result: dict = {}
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        for line in parts[1].strip().splitlines():
            line = line.strip()
            for key in wanted:
                if line.startswith(f"{key}:"):
                    value = line.split(":", 1)[1].strip()
                    if value and not value.startswith("YOUR_"):
                        result.setdefault(key, value)
        break
    return result


def main():
    parser = argparse.ArgumentParser(description="Hybrid search over RAG index")
    parser.add_argument("--data-dir", required=True, help="Path to data directory")
    parser.add_argument("--queries", nargs="+", required=True, help="Search queries")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--per-query-min", type=int, default=2,
                        help="Minimum unique results guaranteed per query")
    parser.add_argument("--provider", default="",
                        help="Embedding provider (openai|gemini). "
                             "Falls back to settings file or config default.")
    parser.add_argument("--api-key", default="", help="API key for the selected provider")
    parser.add_argument("--settings", default="", help="Path to settings file")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    settings = _read_settings(args.settings)

    # Resolve provider: --provider > settings > config default
    provider = (args.provider
                or settings.get("embedding_provider", "")
                or config.EMBEDDING_PROVIDER)
    try:
        config.get_provider_config(provider)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    # Resolve API key for that provider
    api_key = args.api_key or settings.get(f"{provider}_api_key", "")
    env_var = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]
    api_key = api_key or os.environ.get(env_var, "")
    if not api_key:
        print(json.dumps({
            "error": f"{env_var} not set. Pass --api-key, set the env var, "
                     f"or configure {provider}_api_key in the settings file."
        }))
        sys.exit(1)
    embedder.set_api_key(api_key, provider=provider)

    # Validate index files
    chunks_file = data_dir / "chunks.json"
    bm25_file = data_dir / "bm25_corpus.json"
    embeddings_dir = config.get_embedding_dir(data_dir, provider)
    embeddings_file = embeddings_dir / "embeddings.npz"

    missing = [str(f) for f in (chunks_file, bm25_file, embeddings_file) if not f.exists()]
    if missing:
        legacy = data_dir / "embeddings.npz"
        parts = [
            f"Missing index files for provider={provider}:",
            *[f"  - {p}" for p in missing],
        ]
        if legacy.exists():
            parts.extend([
                "",
                f"Legacy embeddings.npz detected at {legacy}.",
                f"To migrate, re-run ingestion so the index lands under "
                f"embeddings/{provider}/. The legacy file's provider/model is "
                f"unknown, so re-ingestion is the safe path.",
            ])
        else:
            parts.append(
                f"Run ingestion first: python3 ingest.py --document <path> "
                f"--output-dir {data_dir} --provider {provider}"
            )
        print(json.dumps({"error": "\n".join(parts)}))
        sys.exit(1)

    # Validate index meta against current provider/model
    meta = embedder.read_index_meta(embeddings_dir / "index.meta.json")
    expected = config.get_provider_config(provider)
    if meta is None:
        # Index without self-describing metadata — likely manually-moved legacy.
        # Don't block, but warn loudly so dimension mismatch isn't silent.
        print(
            f"⚠  No index.meta.json at {embeddings_dir}. "
            f"Cannot verify model/dimension match current config "
            f"(provider={provider}, model={expected['model']}, "
            f"dim={expected['dimension']}). Re-ingest to add metadata "
            f"and silence this warning.",
            file=sys.stderr,
        )
    elif meta.get("model") != expected["model"] or meta.get("dimension") != expected["dimension"]:
        print(json.dumps({
            "error": (
                f"Index at {embeddings_dir} was built with "
                f"model={meta.get('model')} dim={meta.get('dimension')}, "
                f"but current config expects model={expected['model']} "
                f"dim={expected['dimension']}. Re-ingest with "
                f"--provider {provider} to rebuild."
            )
        }))
        sys.exit(1)

    # Load data
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    embeddings = np.load(embeddings_file)["embeddings"]
    with open(bm25_file, "r", encoding="utf-8") as f:
        bm25_data = json.load(f)

    # Run searches per query
    per_query_results = {}
    for query in args.queries:
        per_query_results[query] = hybrid_search(
            query, embeddings, chunks, bm25_data, args.top_k, provider
        )

    # Phase 1: guarantee per_query_min unique results per query
    per_query_min = args.per_query_min
    seen_chunk_ids = set()
    guaranteed = []
    for query, results in per_query_results.items():
        count = 0
        for r in results:
            if r["chunk_id"] not in seen_chunk_ids and count < per_query_min:
                seen_chunk_ids.add(r["chunk_id"])
                guaranteed.append(r)
                count += 1

    # Phase 2: fill remaining slots by score
    remaining = []
    for results in per_query_results.values():
        for r in results:
            if r["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(r["chunk_id"])
                remaining.append(r)
    remaining.sort(key=lambda x: x["score"], reverse=True)

    merged_results = (guaranteed + remaining)[:args.top_k]

    print("RETRIEVAL_RESULTS:")
    print(json.dumps(merged_results, indent=2, ensure_ascii=False))
    print(f"\nTotal unique chunks retrieved: {len(merged_results)}")


if __name__ == "__main__":
    main()
