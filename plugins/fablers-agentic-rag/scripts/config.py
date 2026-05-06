"""Central configuration for the RAG ingestion pipeline."""
from pathlib import Path
from typing import Optional

# === Chunking ===
CHUNK_MAX_TOKENS = 800          # Max tokens per chunk
CHUNK_OVERLAP_SENTENCES = 2     # Sentence overlap between split chunks
CHARS_PER_TOKEN = 4             # Approximate chars per token (English)

# === Embedding ===
# Default provider for new indexes. Existing indexes keep their own provider
# (recorded in index.meta.json) regardless of this value.
EMBEDDING_PROVIDER = "gemini"

# Per-provider embedding configuration. Adding a new provider means adding a
# new entry here, plus a dispatch branch in embedder.py / search.py.
PROVIDERS = {
    "openai": {
        "model": "text-embedding-3-small",
        "dimension": 1536,
        "batch_size": 100,
    },
    "gemini": {
        "model": "gemini-embedding-2-preview",
        "dimension": 3072,
        "batch_size": 100,
    },
}


def get_provider_config(provider: Optional[str] = None) -> dict:
    """Return the config dict for the given provider (or the default)."""
    name = provider or EMBEDDING_PROVIDER
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown embedding provider: '{name}'. "
            f"Supported: {', '.join(PROVIDERS.keys())}"
        )
    return PROVIDERS[name]


def get_embedding_dir(data_dir: Path, provider: Optional[str] = None) -> Path:
    """Return the per-provider embedding directory under data_dir.

    Layout: {data_dir}/embeddings/{provider}/
    Embeddings and index.meta.json live here. chunks.json and bm25_corpus.json
    stay at the data_dir root — they are provider-independent.
    """
    name = provider or EMBEDDING_PROVIDER
    return Path(data_dir) / "embeddings" / name


# === Backward-compatible aliases ===
# These point at the current default provider's config. Kept so older callers
# still work; new code should use get_provider_config() directly.
EMBEDDING_MODEL = PROVIDERS[EMBEDDING_PROVIDER]["model"]
EMBEDDING_DIMENSION = PROVIDERS[EMBEDDING_PROVIDER]["dimension"]
EMBEDDING_BATCH_SIZE = PROVIDERS[EMBEDDING_PROVIDER]["batch_size"]
