"""Embedding generation with provider dispatch (OpenAI + Gemini).

Provider is selected via config.EMBEDDING_PROVIDER or the `provider` kwarg.
Each provider has its own API key, SDK, and task-type handling for
document vs. query embeddings.
"""
import json
import os
import time
import numpy as np
from typing import List, Dict, Optional
from pathlib import Path

import config


# Per-provider API key overrides (set via set_api_key).
_api_keys: Dict[str, Optional[str]] = {"openai": None, "gemini": None}


def set_api_key(key: str, provider: Optional[str] = None):
    """Override the API key for a specific provider.

    If `provider` is omitted, the current default provider is used.
    """
    name = provider or config.EMBEDDING_PROVIDER
    if name not in _api_keys:
        raise ValueError(f"Unknown provider: {name}")
    _api_keys[name] = key


def _resolve_api_key(provider: str) -> str:
    env_var = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]
    key = _api_keys.get(provider) or os.environ.get(env_var, "")
    if not key:
        raise ValueError(
            f"API key for provider '{provider}' not set. "
            f"Pass --api-key, set {env_var} env var, "
            f"or configure {provider}_api_key in "
            f".claude/fablers-agentic-rag.local.md"
        )
    return key


def _build_embedding_text(chunk: Dict) -> str:
    """Prepend the heading (if present) so hierarchical context rides along."""
    prefix = chunk.get("heading", "")
    return f"{prefix}\n\n{chunk['text']}" if prefix else chunk["text"]


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def _embed_openai(texts: List[str], batch_size: int,
                  purpose: str) -> List[List[float]]:
    # OpenAI's text-embedding-3-* models have no task-type parameter;
    # `purpose` is accepted for API parity with Gemini and ignored here.
    del purpose
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "OpenAI SDK not installed. Install it with:\n"
            "    pip install openai"
        ) from e
    client = OpenAI(api_key=_resolve_api_key("openai"))
    model = config.PROVIDERS["openai"]["model"]

    all_embeddings: List[List[float]] = []
    total_batches = (len(texts) - 1) // batch_size + 1 if texts else 0
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"  [openai] batch {i // batch_size + 1}/{total_batches} "
              f"({len(batch)} items)...")
        try:
            response = client.embeddings.create(model=model, input=batch)
            all_embeddings.extend(item.embedding for item in response.data)
        except Exception as e:
            if "rate_limit" in str(e).lower():
                print("  Rate limited, waiting 60s...")
                time.sleep(60)
                response = client.embeddings.create(model=model, input=batch)
                all_embeddings.extend(item.embedding for item in response.data)
            else:
                raise
    return all_embeddings


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _embed_gemini(texts: List[str], batch_size: int,
                  purpose: str) -> List[List[float]]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise ImportError(
            "Google GenAI SDK not installed. Install it with:\n"
            "    pip install google-genai"
        ) from e

    client = genai.Client(api_key=_resolve_api_key("gemini"))
    model = config.PROVIDERS["gemini"]["model"]
    task_type = "RETRIEVAL_DOCUMENT" if purpose == "document" else "RETRIEVAL_QUERY"

    all_embeddings: List[List[float]] = []
    total_batches = (len(texts) - 1) // batch_size + 1 if texts else 0
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"  [gemini] batch {i // batch_size + 1}/{total_batches} "
              f"({len(batch)} items)...")
        try:
            result = client.models.embed_content(
                model=model,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            all_embeddings.extend(e.values for e in result.embeddings)
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                print("  Rate limited, waiting 60s...")
                time.sleep(60)
                result = client.models.embed_content(
                    model=model,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                all_embeddings.extend(e.values for e in result.embeddings)
            else:
                raise
    return all_embeddings


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {"openai": _embed_openai, "gemini": _embed_gemini}


def generate_embeddings(chunks: List[Dict],
                        provider: Optional[str] = None,
                        batch_size: Optional[int] = None) -> np.ndarray:
    """Embed all chunks via the selected provider (task_type=document).

    Returns:
        numpy array of shape (num_chunks, embedding_dim), dtype float32.
    """
    name = provider or config.EMBEDDING_PROVIDER
    cfg = config.get_provider_config(name)
    batch_size = batch_size or cfg["batch_size"]
    texts = [_build_embedding_text(c) for c in chunks]
    embeddings = _DISPATCH[name](texts, batch_size, purpose="document")
    return np.array(embeddings, dtype=np.float32)


def embed_query(query: str,
                provider: Optional[str] = None) -> np.ndarray:
    """Embed a single query string (task_type=query)."""
    name = provider or config.EMBEDDING_PROVIDER
    cfg = config.get_provider_config(name)
    embeddings = _DISPATCH[name]([query], cfg["batch_size"], purpose="query")
    return np.array(embeddings[0], dtype=np.float32)


# ---------------------------------------------------------------------------
# Index files — embeddings + metadata + self-describing meta
# ---------------------------------------------------------------------------

def write_index_meta(meta_path: Path, provider: str, n_vectors: int):
    """Write self-describing metadata next to an embeddings.npz.

    Enables search.py to detect model/dimension mismatches with the current
    config before doing a broken retrieval.
    """
    cfg = config.get_provider_config(provider)
    meta = {
        "provider": provider,
        "model": cfg["model"],
        "dimension": cfg["dimension"],
        "n_vectors": n_vectors,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def read_index_meta(meta_path: Path) -> Optional[dict]:
    if not meta_path.exists():
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_embeddings(embeddings: np.ndarray,
                    metadata: List[Dict],
                    embeddings_path: Path,
                    metadata_path: Path,
                    provider: Optional[str] = None,
                    meta_path: Optional[Path] = None):
    """Save embeddings + chunk metadata, and (if meta_path given) index meta."""
    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(embeddings_path, embeddings=embeddings)

    trimmed = [{k: v for k, v in chunk.items() if k != "text"}
               for chunk in metadata]
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=2, ensure_ascii=False)

    if meta_path is not None:
        write_index_meta(meta_path,
                         provider or config.EMBEDDING_PROVIDER,
                         len(embeddings))


def load_embeddings(embeddings_path: Path, metadata_path: Path):
    """Load embeddings + metadata from disk.

    Returns:
        (embeddings: np.ndarray, metadata: List[Dict])
    """
    data = np.load(embeddings_path)
    embeddings = data["embeddings"]
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    return embeddings, metadata
