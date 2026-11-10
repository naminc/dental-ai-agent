"""Backward-compatible facade for the componentized retrieval pipeline."""

from __future__ import annotations

import numpy as np

from src.core.settings import get_settings
from src.retriever.bm25_searcher import BM25Searcher
from src.retriever.category_matcher import CategoryMatcher
from src.retriever.engines import EmbeddingEngine, create_engine
from src.retriever.index_store import IndexStore
from src.retriever.query_expander import QueryExpander
from src.retriever.retrieval_service import RetrievalService
from src.retriever.rrf_ranker import RRFRanker
from src.retriever.vector_searcher import VectorSearcher
from src.providers.factory import get_chat_provider
from src.providers.protocols import QueryExpansionProvider

settings = get_settings()


class Retriever:
    """Compatibility facade preserving the original Retriever interface."""

    _RRF_K = RRFRanker.RRF_K
    _RRF_MISS_RANK = RRFRanker.RRF_MISS_RANK
    _KEYWORD_HEAVY_SIGNALS = RetrievalService.KEYWORD_HEAVY_SIGNALS
    _OVERVIEW_SIGNALS = RRFRanker.OVERVIEW_SIGNALS

    def __init__(
        self,
        engine: str = settings.embedding_engine.value,
        llm_engine: str = settings.llm_engine.value,
        query_expander: QueryExpansionProvider | None = None,
    ) -> None:
        self.engine_name = engine
        store = IndexStore(settings.vector_db_dir / engine, engine)
        self.index = store.index
        self.metadata = store.metadata
        self._embedder: EmbeddingEngine = create_engine(engine)
        self._disease_set = sorted(
            {
                document.get("metadata", {}).get("disease", "")
                for document in self.metadata
            }
            - {""}
        )

        self._vector_searcher = VectorSearcher(self.index, self._embedder)
        self._bm25_searcher = BM25Searcher(self.metadata)
        # Preserve this public-ish attribute for existing callers/tests.
        self.bm25 = self._bm25_searcher.bm25
        self._category_matcher = CategoryMatcher(self.metadata)
        self._ranker = RRFRanker()

        self._query_expander = query_expander or QueryExpander(
            get_chat_provider(llm_engine)
        )
        self._service = RetrievalService(
            metadata=self.metadata,
            category_matcher=self._category_matcher,
            query_expander=self._query_expander,
            ranker=self._ranker,
            vector_searcher=self._vector_searcher,
            bm25_searcher=self._bm25_searcher,
        )

    def get_available_diseases(self) -> list[str]:
        return self._disease_set

    def normalize_text(self, text: str) -> str:
        return BM25Searcher.normalize_text(text)

    def normalize_and_tokenize(self, text: str) -> list[str]:
        return BM25Searcher.normalize_and_tokenize(text)

    def embed_query(self, query: str) -> np.ndarray:
        return self._embedder.embed_query(query)

    def expand_queries(self, query: str) -> list[str]:
        expander = getattr(self, "_query_expander", None)
        if expander is None:
            expander = QueryExpander(None)
        return expander.expand(query)

    def _match_categories(self, categories: list[str] | None) -> set[int] | None:
        matcher = getattr(self, "_category_matcher", None)
        if matcher is None:
            matcher = CategoryMatcher(self.metadata)
        return matcher.match(categories)

    def _is_keyword_heavy(self, query: str) -> bool:
        service = getattr(self, "_service", None)
        if service is not None:
            return service.is_keyword_heavy(query)
        return any(signal in query.lower() for signal in self._KEYWORD_HEAVY_SIGNALS)

    def _hybrid_score(
        self,
        query: str,
        top_k: int,
        valid_indices: set[int] | None,
        w_vector: float,
        w_bm25: float,
        query_label: str = "",
    ) -> dict[int, float]:
        vector_searcher = getattr(self, "_vector_searcher", None)
        bm25_searcher = getattr(self, "_bm25_searcher", None)
        ranker = getattr(self, "_ranker", None) or RRFRanker()

        if vector_searcher is None:
            vector_searcher = _LegacyVectorSearcher(self)
        if bm25_searcher is None:
            bm25_searcher = _LegacyBM25Searcher(self)

        vector_ranked = vector_searcher.search(
            query, top_k, valid_indices, query_label
        )
        bm25_ranked = bm25_searcher.search(query, top_k, valid_indices, query_label)
        return ranker.score(vector_ranked, bm25_ranked, w_vector, w_bm25)

    def _boost_overview(self, results: list[dict]) -> list[dict]:
        ranker = getattr(self, "_ranker", None) or RRFRanker()
        return ranker.boost_overview(results)

    def search(
        self,
        query: str,
        top_k: int = settings.top_k,
        categories: list[str] | None = None,
        expanded_queries: list[str] | None = None,
    ) -> list[dict]:
        service = getattr(self, "_service", None)
        if service is None:
            service = RetrievalService(
                metadata=self.metadata,
                category_matcher=_FacadeCategoryMatcher(self),
                query_expander=_FacadeQueryExpander(self),
                ranker=getattr(self, "_ranker", None) or RRFRanker(),
                score_query=self._hybrid_score,
            )
        return service.search(query, top_k, categories, expanded_queries)


class _FacadeCategoryMatcher:
    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def match(self, categories: list[str] | None) -> set[int] | None:
        return self.retriever._match_categories(categories)


class _FacadeQueryExpander:
    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def expand(self, query: str) -> list[str]:
        return self.retriever.expand_queries(query)


class _LegacyVectorSearcher:
    """Adapter used only by callers constructing Retriever without __init__."""

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def search(
        self,
        query: str,
        top_k: int,
        valid_indices: set[int] | None,
        query_label: str = "",
    ) -> list[int]:
        embedder = _FacadeEmbedder(self.retriever)
        return VectorSearcher(self.retriever.index, embedder).search(
            query, top_k, valid_indices, query_label
        )


class _FacadeEmbedder:
    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def embed_query(self, query: str) -> np.ndarray:
        return self.retriever.embed_query(query)


class _LegacyBM25Searcher:
    """Adapter for the original bm25 + tokenizer facade attributes."""

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def search(
        self,
        query: str,
        top_k: int,
        valid_indices: set[int] | None,
        query_label: str = "",
    ) -> list[int]:
        searcher = object.__new__(BM25Searcher)
        searcher.bm25 = self.retriever.bm25
        searcher.normalize_and_tokenize = self.retriever.normalize_and_tokenize
        return searcher.search(query, top_k, valid_indices, query_label)
