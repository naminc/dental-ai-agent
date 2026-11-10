from __future__ import annotations

import logging
import time
from collections.abc import Callable

from src.retriever.bm25_searcher import BM25Searcher
from src.retriever.category_matcher import CategoryMatcher
from src.retriever.query_expander import QueryExpander
from src.retriever.rrf_ranker import RRFRanker
from src.retriever.vector_searcher import VectorSearcher

logger = logging.getLogger(__name__)

ScoreQuery = Callable[[str, int, set[int] | None, float, float, str], dict[int, float]]


class RetrievalService:
    """Coordinates category filtering, expansion, search, merge, and ranking."""

    KEYWORD_HEAVY_SIGNALS = [
        "chi phí",
        "bảng giá",
        "giá bao nhiêu",
        "bao nhiêu tiền",
        "giá cả",
        "giá tiền",
        "phí",
        "quy trình",
        "các bước",
        "trình tự",
        "thứ tự",
        "mất bao lâu",
        "thời gian",
    ]

    def __init__(
        self,
        metadata: list[dict],
        category_matcher: CategoryMatcher,
        query_expander: QueryExpander,
        ranker: RRFRanker,
        vector_searcher: VectorSearcher | None = None,
        bm25_searcher: BM25Searcher | None = None,
        score_query: ScoreQuery | None = None,
    ) -> None:
        self.metadata = metadata
        self.category_matcher = category_matcher
        self.query_expander = query_expander
        self.ranker = ranker
        self.vector_searcher = vector_searcher
        self.bm25_searcher = bm25_searcher
        self._score_query_override = score_query

    def is_keyword_heavy(self, query: str) -> bool:
        query_lower = query.lower()
        return any(signal in query_lower for signal in self.KEYWORD_HEAVY_SIGNALS)

    def score_query(
        self,
        query: str,
        top_k: int,
        valid_indices: set[int] | None,
        vector_weight: float,
        bm25_weight: float,
        query_label: str = "",
    ) -> dict[int, float]:
        if self._score_query_override is not None:
            return self._score_query_override(
                query,
                top_k,
                valid_indices,
                vector_weight,
                bm25_weight,
                query_label,
            )
        if self.vector_searcher is None or self.bm25_searcher is None:
            raise RuntimeError("RetrievalService searchers are not configured")

        vector_ranked = self.vector_searcher.search(
            query, top_k, valid_indices, query_label
        )
        bm25_ranked = self.bm25_searcher.search(
            query, top_k, valid_indices, query_label
        )
        return self.ranker.score(
            vector_ranked,
            bm25_ranked,
            vector_weight,
            bm25_weight,
        )

    def search(
        self,
        query: str,
        top_k: int,
        categories: list[str] | None = None,
        expanded_queries: list[str] | None = None,
    ) -> list[dict]:
        if not self.metadata:
            return []

        started = time.perf_counter()
        logger.info("[TIME-LOG] === RETRIEVAL START ===")
        valid_indices = self.category_matcher.match(categories)
        vector_weight, bm25_weight = (
            (0.3, 0.7) if self.is_keyword_heavy(query) else (0.5, 0.5)
        )
        queries = (
            expanded_queries
            if expanded_queries
            else self.query_expander.expand(query)
        )

        score_sets = []
        for index, expanded_query in enumerate(queries):
            label = "original" if index == 0 else f"variant_{index}"
            score_sets.append(
                self.score_query(
                    expanded_query,
                    top_k,
                    valid_indices,
                    vector_weight,
                    bm25_weight,
                    label,
                )
            )

        merged = self.ranker.merge(score_sets)
        if not merged:
            return []

        ranked = sorted(merged.items(), key=lambda item: item[1], reverse=True)
        results = [self.metadata[index] for index, _ in ranked[:top_k]]
        logger.info(
            "[TIME-LOG] === RETRIEVAL END === Tổng: %.2fs",
            time.perf_counter() - started,
        )
        return self.ranker.boost_overview(results)
