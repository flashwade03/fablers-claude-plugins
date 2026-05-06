---
rag_data_path: /path/to/data
embedding_provider: gemini
gemini_api_key: YOUR_GEMINI_API_KEY
openai_api_key: YOUR_OPENAI_API_KEY
---

# Fablers Agentic RAG Configuration

## Settings

### `rag_data_path` (required)

Absolute path to the data directory containing the RAG indexes:
- `chunks.json` — chunked document text (provider-independent)
- `bm25_corpus.json` — BM25 keyword index (provider-independent)
- `embeddings/{provider}/embeddings.npz` — vector embeddings, one folder per provider
- `embeddings/{provider}/index.meta.json` — model/dimension metadata for compatibility checks

Example:
```yaml
rag_data_path: /Volumes/FablersBackup/Projects/fablers-rag/data
```

### `embedding_provider` (optional, default: `gemini`)

Which embedding backend to use for ingestion and query:
- `gemini` — Google `gemini-embedding-001` (3072 dim). Stronger multilingual retrieval. Requires `gemini_api_key`.
- `openai` — OpenAI `text-embedding-3-small` (1536 dim). Requires `openai_api_key`.

```yaml
embedding_provider: gemini
```

You can ingest the same document with both providers and compare retrieval quality — each provider's vectors live in its own subdirectory under `embeddings/`.

### `gemini_api_key` (required if provider=gemini)

Google API key for Gemini embeddings. Get one at https://aistudio.google.com/.

```yaml
gemini_api_key: AIza...
```

### `openai_api_key` (required if provider=openai)

OpenAI API key for embeddings. Only needed when `embedding_provider: openai`.

```yaml
openai_api_key: sk-...
```

## How it works

The `/rag-ask <question>` command runs a streamlined 3-agent pipeline with complexity branching:

**Simple questions** (1 agent call):
1. Skill generates 2 search queries directly
2. `search.py` runs hybrid search (vector + BM25)
3. **Answer Synthesizer** produces a cited answer

**Complex questions** (up to 3 agent calls):
1. **Query Analyst** — Rewrites your question into optimized search queries
2. `search.py` runs hybrid search on the data at `rag_data_path`
3. **Evaluator** — Scores top 5 passages + CRAG validation (sufficient? retry? insufficient?)
4. **Answer Synthesizer** — Produces a cited answer with `[Source N]` references

Additional commands:
- `/rag-search <query>` — Run a direct hybrid search and see raw results
- `/ingest <file>` — Index a new document (PDF, TXT, or Markdown)
