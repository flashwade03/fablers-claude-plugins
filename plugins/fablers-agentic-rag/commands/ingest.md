---
name: ingest
description: Ingest a document (PDF, TXT, or Markdown) into the RAG index.
argument-hint: "<file-path>"
---

# /ingest Command

Ingest a document into the RAG pipeline to create searchable chunks, embeddings, and BM25 index.

## Steps

### 1. Check Dependencies

Verify required Python packages are installed. The embedding SDK depends on the configured `embedding_provider` (default: `gemini`):

```bash
# Always required
python3 -c "import pdfplumber, numpy, rank_bm25" 2>/dev/null

# Provider-specific — check whichever the user has selected:
python3 -c "import google.genai" 2>/dev/null   # if provider = gemini (default)
python3 -c "import openai" 2>/dev/null          # if provider = openai
```

If missing, inform the user:
> Install required packages: `pip install pdfplumber numpy rank_bm25 google-genai openai`
> (Only the provider you actually use is needed — `google-genai` for Gemini, `openai` for OpenAI.)

### 2. Read Configuration

Read `${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md` and extract:
- `rag_data_path` — default output directory
- `embedding_provider` — `gemini` (default) or `openai`
- The matching API key: `gemini_api_key` or `openai_api_key`

### 3. Execute Ingestion

Run the ingestion script with the settings file path. It auto-resolves `embedding_provider` and the matching API key:

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && \
python3 ingest.py \
  --document "$ARGUMENTS" \
  --output-dir "<rag_data_path or ./data>" \
  --settings "${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md"
```

If the user didn't specify an output directory, use the `rag_data_path` from the settings file, or default to `./data`.

To ingest the same document with a different provider for comparison, pass `--provider openai` (or `gemini`) explicitly. `chunks.json` and `bm25_corpus.json` are reused across providers — only the per-provider `embeddings/{provider}/` folder is rebuilt.

### 4. Report Results

After ingestion completes, report:
- Number of pages extracted
- Number of chunks created
- Provider used for embeddings
- Output directory path (point out that embeddings live under `embeddings/{provider}/`)
- If a legacy `embeddings.npz` warning was emitted, relay it to the user verbatim

Remind the user to update `rag_data_path` in `.claude/fablers-agentic-rag.local.md` if needed.
