from __future__ import annotations


class RRFRanker:
    """Calculates legacy RRF scores, merges variants, and boosts overviews."""

    RRF_K = 60
    RRF_MISS_RANK = 1000
    OVERVIEW_SIGNALS = [
        "tổng quan",
        "tìm hiểu về",
        "quy trình chung",
        "giới thiệu",
        "là gì",
        "các loại",
    ]

    def score(
        self,
        vector_ranked: list[int],
        bm25_ranked: list[int],
        vector_weight: float,
        bm25_weight: float,
    ) -> dict[int, float]:
        candidates = set(vector_ranked) | set(bm25_ranked)
        if not candidates:
            return {}

        vector_ranks = {index: rank for rank, index in enumerate(vector_ranked)}
        bm25_ranks = {index: rank for rank, index in enumerate(bm25_ranked)}
        return {
            index: (
                vector_weight
                / (self.RRF_K + vector_ranks.get(index, self.RRF_MISS_RANK) + 1)
                + bm25_weight
                / (self.RRF_K + bm25_ranks.get(index, self.RRF_MISS_RANK) + 1)
            )
            for index in candidates
        }

    @staticmethod
    def merge(score_sets: list[dict[int, float]]) -> dict[int, float]:
        merged: dict[int, float] = {}
        for scores in score_sets:
            for index, score in scores.items():
                merged[index] = merged.get(index, 0.0) + score
        return merged

    def boost_overview(self, results: list[dict]) -> list[dict]:
        overview: list[dict] = []
        rest: list[dict] = []
        for document in results:
            combined = (
                f"{document.get('title', '').lower()} "
                f"{document.get('section', '').lower()}"
            )
            if any(signal in combined for signal in self.OVERVIEW_SIGNALS):
                overview.append(document)
            else:
                rest.append(document)
        return overview + rest
