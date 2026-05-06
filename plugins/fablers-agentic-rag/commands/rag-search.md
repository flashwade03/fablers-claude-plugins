---
name: rag-search
description: Run a direct hybrid search against the RAG index and return raw results.
argument-hint: "<query>"
---

# /rag-search Command

Run a direct hybrid search (vector + BM25) against the indexed document.

## Steps

### 1. Read Configuration

Read the settings file at `${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md`.

Extract from the YAML frontmatter:
- `rag_data_path` — absolute path to the data directory
- `embedding_provider` — `gemini` (default) or `openai`
- The matching API key: `gemini_api_key` or `openai_api_key`

If the file doesn't exist or required values are placeholders, stop and ask the user to configure it. `search.py` reads provider + key from the same file, so you do not need to pass `--api-key` or `--provider` on the CLI.

### 2. Execute Search

Run the search script directly:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/search.py \
  --data-dir "<rag_data_path>" \
  --queries "$ARGUMENTS" \
  --top-k 10
```

If `search.py` errors with "Missing index files" and mentions a legacy `embeddings.npz` at the data root, the index is pre-v3.1. Tell the user to re-run `/ingest` to rebuild under `embeddings/{provider}/`.

### 3. Return Results

Display the raw JSON results to the user. Include:
- Number of chunks retrieved
- Each chunk's `chunk_id`, `score`, `heading`, and a text preview (first 200 chars)
