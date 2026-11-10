import numpy as np
import pytest

from src.retriever.search import Retriever
from src.providers.fake import FakeChatProvider
from src.retriever.query_expander import QueryExpander


def make_retriever(metadata: list[dict]) -> Retriever:
    retriever = object.__new__(Retriever)
    retriever.metadata = metadata
    retriever._disease_set = sorted(
        {
            document.get("metadata", {}).get("disease", "")
            for document in metadata
        }
        - {""}
    )
    return retriever


@pytest.mark.unit
def test_rrf_formula_missing_rank_and_category_filter_are_preserved(monkeypatch) -> None:
    retriever = make_retriever([{}, {}, {}, {}])

    class FakeIndex:
        ntotal = 4

        def search(self, query_vector, n_search):
            assert query_vector.dtype == np.float32
            assert query_vector.shape == (1, 2)
            assert n_search == 4
            return (
                np.array([[0.9, 0.8, 0.7, -1.0]], dtype="float32"),
                np.array([[2, 0, 1, -1]], dtype="int64"),
            )

    class FakeBM25:
        def get_scores(self, tokens):
            assert tokens == ["query"]
            return np.array([0.2, 0.5, 0.0, 0.9])

    retriever.index = FakeIndex()
    retriever.bm25 = FakeBM25()
    monkeypatch.setattr(
        retriever,
        "embed_query",
        lambda query: np.array([0.25, 0.75], dtype="float32"),
    )
    monkeypatch.setattr(retriever, "normalize_and_tokenize", lambda query: ["query"])

    scores = retriever._hybrid_score(
        "query",
        top_k=1,
        valid_indices={0, 1, 2},
        w_vector=0.3,
        w_bm25=0.7,
    )

    assert scores == pytest.approx(
        {
            0: 0.3 / 62 + 0.7 / 62,
            1: 0.3 / 63 + 0.7 / 61,
            2: 0.3 / 61 + 0.7 / 1061,
        }
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("query", "expected_weights"),
    [
        ("chi phí niềng răng", (0.3, 0.7)),
        ("đau răng khi uống lạnh", (0.5, 0.5)),
    ],
)
def test_pipeline_preserves_dynamic_weights_top_k_overview_and_metadata(
    monkeypatch,
    query: str,
    expected_weights: tuple[float, float],
) -> None:
    metadata = [
        {
            "title": "Điều trị chi tiết",
            "section": "Các bước",
            "content": "regular",
            "metadata": {"disease": "sâu răng", "source": "a.json"},
        },
        {
            "title": "Sâu răng là gì",
            "section": "Tổng quan",
            "content": "overview",
            "metadata": {"disease": "sâu răng", "source": "b.json"},
        },
        {
            "title": "Unrelated",
            "section": "Other",
            "content": "excluded by top_k",
            "metadata": {"disease": "viêm nướu", "source": "c.json"},
        },
    ]
    retriever = make_retriever(metadata)
    calls = []

    def fake_hybrid_score(
        expanded_query,
        top_k,
        valid_indices,
        w_vector,
        w_bm25,
        query_label="",
    ):
        calls.append(
            (
                expanded_query,
                top_k,
                valid_indices,
                w_vector,
                w_bm25,
                query_label,
            )
        )
        return {0: 0.9, 1: 0.8, 2: 0.7}

    monkeypatch.setattr(retriever, "_hybrid_score", fake_hybrid_score)

    results = retriever.search(
        query,
        top_k=2,
        categories=["răng sâu"],
        expanded_queries=[query],
    )

    assert calls == [(query, 2, {0, 1}, *expected_weights, "original")]
    assert results == [metadata[1], metadata[0]]
    assert results[0] is metadata[1]
    assert set(results[0]) == {"title", "section", "content", "metadata"}


@pytest.mark.unit
def test_query_expansion_format_and_fallback_are_preserved() -> None:
    retriever = make_retriever([])
    provider = FakeChatProvider(
        completions=["- biến thể một\nbiến thể hai\nbiến thể bị bỏ qua"]
    )
    retriever._query_expander = QueryExpander(provider)

    assert retriever.expand_queries("câu hỏi gốc") == [
        "câu hỏi gốc",
        "biến thể một",
        "biến thể hai",
    ]

    provider.completions.clear()
    assert retriever.expand_queries("câu hỏi gốc") == ["câu hỏi gốc"]


@pytest.mark.unit
def test_empty_expanded_query_list_keeps_legacy_auto_expand_behavior(monkeypatch) -> None:
    retriever = make_retriever([{"title": "Only", "metadata": {}}])
    monkeypatch.setattr(retriever, "expand_queries", lambda query: [query, "auto variant"])
    seen = []

    def fake_hybrid_score(query, *args, **kwargs):
        seen.append(query)
        return {0: 1.0}

    monkeypatch.setattr(retriever, "_hybrid_score", fake_hybrid_score)

    assert retriever.search("original", expanded_queries=[]) == retriever.metadata
    assert seen == ["original", "auto variant"]
