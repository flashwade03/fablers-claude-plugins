#!/usr/bin/env python3
"""Multi-format document extraction and ingestion pipeline.

Supported formats: PDF, plain text, Markdown.

Usage:
    python3 ingest.py --document ./mybook.pdf --output-dir ./data
    python3 ingest.py --document ./notes.md --output-dir ./data/notes --skip-embeddings
    python3 ingest.py --document ./doc.pdf --output-dir ./data --provider openai

Provider-specific embeddings are written to:
    {output_dir}/embeddings/{provider}/embeddings.npz
    {output_dir}/embeddings/{provider}/metadata.json
    {output_dir}/embeddings/{provider}/index.meta.json

chunks.json and bm25_corpus.json are written at {output_dir}/ and are
shared across providers (re-ingesting with a different provider reuses them).
"""
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pdfplumber

import config


@dataclass
class DocumentPage:
    """A single page (or logical section) of extracted text."""
    text: str
    page_number: Optional[int] = None  # PDF only


@dataclass
class Document:
    """Extracted document with pages and metadata."""
    pages: List[DocumentPage]
    source_file: str
    format: str  # "pdf" | "txt" | "md"


def extract(file_path: str) -> Document:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".txt":
        return _extract_text(path)
    elif suffix in (".md", ".markdown"):
        return _extract_markdown(path)
    else:
        raise ValueError(
            f"Unsupported file format: '{suffix}'. "
            "Supported: .pdf, .txt, .md, .markdown"
        )


def _extract_pdf(path: Path) -> Document:
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(DocumentPage(
                    text=text.strip(),
                    page_number=i + 1,
                ))
    return Document(pages=pages, source_file=str(path), format="pdf")


def _extract_text(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    pages = [DocumentPage(text=text.strip())] if text.strip() else []
    return Document(pages=pages, source_file=str(path), format="txt")


def _extract_markdown(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    pages = [DocumentPage(text=text.strip())] if text.strip() else []
    return Document(pages=pages, source_file=str(path), format="md")


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
    parser = argparse.ArgumentParser(
        description="Ingest a document into the RAG pipeline "
                    "(extract -> chunk -> embed -> BM25 index)."
    )
    parser.add_argument("--document", required=True,
                        help="Path to the source document (PDF, TXT, or Markdown).")
    parser.add_argument("--output-dir", required=True,
                        help="Directory where chunks, embeddings, and indexes are saved.")
    parser.add_argument("--skip-embeddings", action="store_true",
                        help="Stop after chunking (skip embedding and BM25 index generation).")
    parser.add_argument("--provider", default="",
                        help="Embedding provider (openai|gemini). "
                             "Falls back to settings file or config default.")
    parser.add_argument("--api-key", default="",
                        help="API key for the selected provider. Falls back to settings or env.")
    parser.add_argument("--settings", default="",
                        help="Path to fablers-agentic-rag.local.md settings file.")
    args = parser.parse_args()

    doc_path = Path(args.document)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = _read_settings(args.settings)

    # Resolve provider: --provider > settings > config default
    provider = (args.provider
                or settings.get("embedding_provider", "")
                or config.EMBEDDING_PROVIDER)
    try:
        config.get_provider_config(provider)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Resolve API key for that provider
    env_var = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]
    api_key = (args.api_key
               or settings.get(f"{provider}_api_key", "")
               or os.environ.get(env_var, ""))

    # --- Step 1: Extract ---
    print(f"[1/4] Extracting text from {doc_path.name} ...")
    document = extract(str(doc_path))
    print(f"       Extracted {len(document.pages)} page(s), format={document.format}")

    # --- Step 2: Chunk ---
    print(f"[2/4] Chunking document ...")
    from chunker import chunk_document, save_chunks
    chunks = chunk_document(document)
    chunks_file = output_dir / "chunks.json"
    save_chunks(chunks, chunks_file)
    print(f"       Created {len(chunks)} chunks -> {chunks_file}")

    if args.skip_embeddings:
        print("[3/4] Skipped (--skip-embeddings)")
        print("[4/4] Skipped (--skip-embeddings)")
        print("\nDone! Chunks saved. Use without --skip-embeddings to generate embeddings.")
        return

    if not api_key:
        print(f"Error: {env_var} required for embeddings (provider={provider}).")
        print(f"Provide via --api-key, configure {provider}_api_key in "
              ".claude/fablers-agentic-rag.local.md, "
              f"or set {env_var} environment variable.")
        sys.exit(1)

    # --- Step 3: Embed ---
    print(f"[3/4] Generating embeddings (provider={provider}) ...")
    from embedder import generate_embeddings, save_embeddings, set_api_key
    set_api_key(api_key, provider=provider)
    embeddings = generate_embeddings(chunks, provider=provider)

    embeddings_dir = config.get_embedding_dir(output_dir, provider)
    embeddings_file = embeddings_dir / "embeddings.npz"
    metadata_file = embeddings_dir / "metadata.json"
    meta_file = embeddings_dir / "index.meta.json"
    save_embeddings(embeddings, chunks,
                    embeddings_file, metadata_file,
                    provider=provider, meta_path=meta_file)
    print(f"       Saved embeddings -> {embeddings_file}")
    print(f"       Saved index meta  -> {meta_file}")

    # --- Step 4: BM25 index (shared across providers) ---
    print(f"[4/4] Building BM25 index ...")
    corpus_tokens = []
    chunk_ids = []
    for chunk in chunks:
        tokens = re.sub(r"[^\w\s]", " ", chunk["text"].lower()).split()
        corpus_tokens.append(tokens)
        chunk_ids.append(chunk["chunk_id"])

    bm25_file = output_dir / "bm25_corpus.json"
    with open(bm25_file, "w", encoding="utf-8") as f:
        json.dump({"corpus_tokens": corpus_tokens, "chunk_ids": chunk_ids},
                  f, ensure_ascii=False)
    print(f"       Saved BM25 index -> {bm25_file}")

    # Legacy warning: old index format at data_dir root
    legacy_npz = output_dir / "embeddings.npz"
    legacy_meta = output_dir / "metadata.json"
    if legacy_npz.exists():
        print()
        print(f"⚠  Legacy index files detected at the data root:")
        print(f"     {legacy_npz}")
        if legacy_meta.exists():
            print(f"     {legacy_meta}")
        print(f"   These are from the pre-v3.1 layout (single-provider). The new")
        print(f"   layout stores embeddings per-provider under embeddings/<provider>/.")
        print(f"   Search no longer reads the legacy files. Once you verify the new")
        print(f"   index works, you can delete them:")
        print(f"     rm {legacy_npz}", end="")
        if legacy_meta.exists():
            print(f" {legacy_meta}")
        else:
            print()

    print(f"\nDone! Artifacts saved to {output_dir}/")
    print(f"  Embeddings (provider={provider}): {embeddings_dir}/")
    print(f"  Shared:                          {output_dir}/chunks.json, bm25_corpus.json")


if __name__ == "__main__":
    main()
