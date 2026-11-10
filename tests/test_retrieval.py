import pytest

from src.retriever.search import Retriever


def build_retriever(metadata: list[dict]) -> Retriever:
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
def test_category_matching_filters_matching_diseases() -> None:
    retriever = build_retriever(
        [
            {"title": "A", "metadata": {"disease": "sâu răng"}},
            {"title": "B", "metadata": {"disease": "viêm nướu"}},
            {"title": "C", "metadata": {"disease": "niềng răng"}},
        ]
    )

    assert retriever._match_categories(["viêm nướu"]) == {1}
    assert retriever._match_categories(["răng sâu"]) == {0}
    assert retriever._match_categories(["không tồn tại"]) is None
    assert retriever._match_categories(None) is None


@pytest.mark.unit
def test_multi_query_scores_are_merged_and_ranked(monkeypatch) -> None:
    retriever = build_retriever(
        [
            {"title": "Document A", "metadata": {}},
            {"title": "Document B", "metadata": {}},
            {"title": "Document C", "metadata": {}},
        ]
    )
    scores = {
        "original question": {0: 0.20, 1: 0.30},
        "variant question": {0: 0.20, 2: 0.50},
    }

    def fake_hybrid_score(
        query,
        top_k,
        valid_indices,
        w_vector,
        w_bm25,
        query_label="",
    ):
        return scores[query]

    monkeypatch.setattr(retriever, "_hybrid_score", fake_hybrid_score)

    results = retriever.search(
        "original question",
        top_k=3,
        expanded_queries=["original question", "variant question"],
    )

    assert [document["title"] for document in results] == [
        "Document C",
        "Document A",
        "Document B",
    ]
