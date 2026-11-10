import inspect
import json
from pathlib import Path

import pytest

from src.retriever.bm25_searcher import BM25Searcher
from src.retriever.index_store import IndexStore
from src.retriever.query_expander import QueryExpander
from src.retriever.retrieval_service import RetrievalService


@pytest.mark.unit
def test_index_store_reports_missing_index_clearly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="FAISS index not found") as error:
        IndexStore(tmp_path, "local")

    assert "src.retriever.ingest --engine local" in str(error.value)


@pytest.mark.unit
def test_index_store_reports_missing_metadata_before_reading_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "faiss.index").write_bytes(b"placeholder")
    read_calls = []
    monkeypatch.setattr(
        "src.retriever.index_store.faiss.read_index",
        lambda path: read_calls.append(path),
    )

    with pytest.raises(FileNotFoundError, match="Retriever metadata not found"):
        IndexStore(tmp_path, "local")

    assert read_calls == []


@pytest.mark.unit
def test_index_store_reuses_loaded_artifacts_in_same_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_path = tmp_path / "faiss.index"
    metadata_path = tmp_path / "metadata.json"
    index_path.write_bytes(b"placeholder")
    metadata_path.write_text(json.dumps([{"title": "A"}]), encoding="utf-8")
    fake_index = object()
    read_calls = []

    def fake_read_index(path: str):
        read_calls.append(path)
        return fake_index

    monkeypatch.setattr("src.retriever.index_store.faiss.read_index", fake_read_index)
    IndexStore.clear_cache()
    try:
        first = IndexStore(tmp_path, "local")
        second = IndexStore(tmp_path, "local")
    finally:
        IndexStore.clear_cache()

    assert len(read_calls) == 1
    assert first.index is second.index is fake_index
    assert first.metadata is second.metadata


@pytest.mark.unit
def test_bm25_corpus_keeps_summary_field_from_legacy_retriever() -> None:
    searcher = BM25Searcher(
        [
            {
                "title": "",
                "section": "",
                "summary": "implant zirconia",
                "content": "",
            },
            {
                "title": "Other",
                "section": "",
                "summary": "",
                "content": "unrelated",
            },
            {"title": "Third", "content": "orthodontics"},
            {"title": "Fourth", "content": "periodontics"},
        ]
    )

    assert searcher.search("implant zirconia", top_k=1, valid_indices=None) == [0]


@pytest.mark.unit
def test_retrieval_service_contains_no_openai_sdk_details() -> None:
    source = inspect.getsource(RetrievalService).lower()
    assert "openai" not in source
    assert "completions.create" not in source


@pytest.mark.unit
def test_query_expander_constructor_only_accepts_injected_client() -> None:
    constructor_source = inspect.getsource(QueryExpander.__init__).lower()
    assert "openai" not in constructor_source
    assert "provider" in inspect.signature(QueryExpander).parameters
