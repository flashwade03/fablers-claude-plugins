"""Mock-driven E2E tests for the embedding provider dispatch.

Patches embedder._DISPATCH with deterministic fakes so the full ingest -> search
pipeline can be exercised without API calls. Covers:

  1. ingest writes per-provider files at the new layout
  2. search round-trip with the same provider
  3. config drift: index.meta.json mismatch is rejected
  4. legacy embeddings.npz at root is detected with a migration hint
  5. settings file parser maps provider + per-provider keys
  6. dispatcher routes openai vs gemini correctly

Run from anywhere:
    python3 plugins/fablers-agentic-rag/__tests__/test_provider_dispatch.py
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "plugins" / "fablers-agentic-rag" / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.chdir(SCRIPTS)  # ingest/search use relative imports of chunker, embedder, config

import config       # noqa: E402
import embedder     # noqa: E402
import ingest       # noqa: E402
import search       # noqa: E402


# ----- Fakes ---------------------------------------------------------------

def _fake_embedder(dim: int):
    """Deterministic fake: vector seeded by text + purpose so doc ≠ query."""
    def _fn(texts, batch_size, purpose):
        out = []
        for t in texts:
            seed = abs(hash(t + purpose)) % (2**32)
            rng = np.random.default_rng(seed)
            out.append(rng.random(dim).astype(np.float32).tolist())
        return out
    return _fn


def _patch_dispatch():
    embedder._DISPATCH["gemini"] = _fake_embedder(config.PROVIDERS["gemini"]["dimension"])
    embedder._DISPATCH["openai"] = _fake_embedder(config.PROVIDERS["openai"]["dimension"])


def _run_main(module, argv):
    """Invoke a script's main() with argv; return (exit_code, stdout, stderr)."""
    saved = sys.argv
    sys.argv = argv
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                module.main()
                code = 0
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 0
        return code, out.getvalue(), err.getvalue()
    finally:
        sys.argv = saved


def _seed_doc(tmp: Path) -> Path:
    doc = tmp / "doc.txt"
    doc.write_text(
        "Game design is the art of applying design and aesthetics to create a game. "
        "It involves the design of gameplay, environment, storyline, and characters. "
        "\n\n"
        "Mechanics are the rules and procedures that guide the player. "
        "They define how the game works and what the player can do. "
        "\n\n"
        "The Elemental Tetrad describes four basic elements: mechanics, story, aesthetics, technology. "
    )
    return doc


# ----- Tests ---------------------------------------------------------------

def test_ingest_layout(tmp: Path) -> None:
    doc = _seed_doc(tmp)
    data = tmp / "data"

    code, _, _ = _run_main(ingest, [
        "ingest.py", "--document", str(doc), "--output-dir", str(data),
        "--provider", "gemini", "--api-key", "fake",
    ])
    assert code == 0, f"ingest exited {code}"
    assert (data / "chunks.json").exists(), "chunks.json missing at root"
    assert (data / "bm25_corpus.json").exists(), "bm25_corpus.json missing at root"

    embed_dir = data / "embeddings" / "gemini"
    assert (embed_dir / "embeddings.npz").exists(), "embeddings.npz missing under provider dir"
    assert (embed_dir / "metadata.json").exists(), "metadata.json missing under provider dir"
    assert (embed_dir / "index.meta.json").exists(), "index.meta.json missing"

    meta = json.loads((embed_dir / "index.meta.json").read_text())
    assert meta["provider"] == "gemini"
    assert meta["model"] == "gemini-embedding-2-preview"
    assert meta["dimension"] == 3072
    assert meta["n_vectors"] >= 1


def test_search_roundtrip(tmp: Path) -> None:
    doc = _seed_doc(tmp)
    data = tmp / "data"
    _run_main(ingest, [
        "ingest.py", "--document", str(doc), "--output-dir", str(data),
        "--provider", "gemini", "--api-key", "fake",
    ])

    code, stdout, _ = _run_main(search, [
        "search.py", "--data-dir", str(data),
        "--queries", "What is the elemental tetrad?",
        "--provider", "gemini", "--api-key", "fake", "--top-k", "3",
    ])
    assert code == 0, f"search exited {code} stdout={stdout!r}"
    assert "RETRIEVAL_RESULTS:" in stdout, "no retrieval marker in stdout"
    payload = stdout.split("RETRIEVAL_RESULTS:", 1)[1]
    json_blob = payload.split("\nTotal", 1)[0].strip()
    results = json.loads(json_blob)
    assert isinstance(results, list) and len(results) >= 1, "no results returned"
    assert "chunk_id" in results[0] and "text" in results[0]


def test_meta_mismatch_blocks_search(tmp: Path) -> None:
    doc = _seed_doc(tmp)
    data = tmp / "data"
    _run_main(ingest, [
        "ingest.py", "--document", str(doc), "--output-dir", str(data),
        "--provider", "gemini", "--api-key", "fake",
    ])

    # Corrupt the model in meta.json to simulate config drift
    meta_path = data / "embeddings" / "gemini" / "index.meta.json"
    meta = json.loads(meta_path.read_text())
    meta["model"] = "old-model-name"
    meta_path.write_text(json.dumps(meta))

    code, stdout, _ = _run_main(search, [
        "search.py", "--data-dir", str(data), "--queries", "anything",
        "--provider", "gemini", "--api-key", "fake",
    ])
    assert code == 1, f"expected exit 1 on meta mismatch, got {code}"
    err = json.loads(stdout.strip().splitlines()[-1])
    assert "old-model-name" in err["error"]
    assert "Re-ingest" in err["error"]


def test_legacy_embeddings_warning(tmp: Path) -> None:
    doc = _seed_doc(tmp)
    data = tmp / "data"
    _run_main(ingest, [
        "ingest.py", "--document", str(doc), "--output-dir", str(data),
        "--provider", "gemini", "--api-key", "fake",
    ])

    # Remove the new-layout file to force the missing-file path,
    # and drop a fake legacy embeddings.npz at the root.
    new_npz = data / "embeddings" / "gemini" / "embeddings.npz"
    new_npz.unlink()
    legacy = data / "embeddings.npz"
    np.savez_compressed(legacy, embeddings=np.zeros((1, 1), dtype=np.float32))

    code, stdout, _ = _run_main(search, [
        "search.py", "--data-dir", str(data), "--queries", "anything",
        "--provider", "gemini", "--api-key", "fake",
    ])
    assert code == 1
    err = json.loads(stdout.strip().splitlines()[-1])
    assert "Legacy embeddings.npz detected" in err["error"]
    assert "embeddings/gemini/" in err["error"]


def test_settings_parser(tmp: Path) -> None:
    settings = tmp / "fablers-agentic-rag.local.md"
    settings.write_text(
        "---\n"
        "rag_data_path: /some/where\n"
        "embedding_provider: openai\n"
        "openai_api_key: sk-test\n"
        "gemini_api_key: AIza-test\n"
        "---\n"
    )
    parsed = ingest._read_settings(str(settings))
    assert parsed.get("embedding_provider") == "openai"
    assert parsed.get("openai_api_key") == "sk-test"
    assert parsed.get("gemini_api_key") == "AIza-test"

    parsed_search = search._read_settings(str(settings))
    assert parsed_search == parsed, "ingest and search settings parsers diverged"


def test_dispatcher_routes_by_provider(tmp: Path) -> None:
    """Confirm provider arg actually selects the right dispatch function."""
    seen = {"openai": 0, "gemini": 0}

    def make_spy(name, dim):
        def _fn(texts, batch_size, purpose):
            seen[name] += 1
            return [[0.0] * dim for _ in texts]
        return _fn

    embedder._DISPATCH["openai"] = make_spy("openai", 1536)
    embedder._DISPATCH["gemini"] = make_spy("gemini", 3072)

    embedder.set_api_key("k", provider="openai")
    embedder.set_api_key("k", provider="gemini")

    embedder.embed_query("hi", provider="openai")
    embedder.embed_query("hi", provider="gemini")
    embedder.embed_query("hi", provider="gemini")

    assert seen == {"openai": 1, "gemini": 2}, f"dispatch routed wrong: {seen}"


# ----- Driver --------------------------------------------------------------

TESTS = [
    test_ingest_layout,
    test_search_roundtrip,
    test_meta_mismatch_blocks_search,
    test_legacy_embeddings_warning,
    test_settings_parser,
    test_dispatcher_routes_by_provider,
]


def main() -> int:
    failures = []
    for fn in TESTS:
        _patch_dispatch()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(Path(tmp))
                print(f"  PASS  {fn.__name__}")
            except AssertionError as e:
                print(f"  FAIL  {fn.__name__}: {e}")
                failures.append(fn.__name__)
            except Exception as e:
                print(f"  ERR   {fn.__name__}: {type(e).__name__}: {e}")
                failures.append(fn.__name__)
    print()
    if failures:
        print(f"{len(failures)} failure(s): {failures}")
        return 1
    print(f"All {len(TESTS)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
