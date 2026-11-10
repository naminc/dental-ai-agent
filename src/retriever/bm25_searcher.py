from __future__ import annotations

import logging
import re
import time

import numpy as np
from rank_bm25 import BM25Okapi
from underthesea import word_tokenize

logger = logging.getLogger(__name__)


class BM25Searcher:
    """Owns Vietnamese tokenization and keyword ranking."""

    def __init__(self, metadata: list[dict]) -> None:
        tokenized_documents = [
            self.normalize_and_tokenize(self._document_text(document))
            for document in metadata
        ]
        self.bm25 = BM25Okapi(tokenized_documents)

    @staticmethod
    def _document_text(document: dict) -> str:
        return " ".join(
            str(document.get(field, ""))
            for field in ("title", "section", "summary", "content")
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    @classmethod
    def normalize_and_tokenize(cls, text: str) -> list[str]:
        clean = cls.normalize_text(text)
        return word_tokenize(clean, format="text").split()

    def search(
        self,
        query: str,
        top_k: int,
        valid_indices: set[int] | None,
        query_label: str = "",
    ) -> list[int]:
        tag = f" [{query_label}]" if query_label else ""
        started = time.perf_counter()
        scores = self.bm25.get_scores(self.normalize_and_tokenize(query))
        sorted_indices = np.argsort(scores)[::-1]
        logger.info(
            "[TIME-LOG]   BM25 Search%s mất: %.3fs",
            tag,
            time.perf_counter() - started,
        )

        ranked: list[int] = []
        for index in sorted_indices:
            index = int(index)
            if scores[index] <= 0:
                break
            if valid_indices is not None and index not in valid_indices:
                continue
            ranked.append(index)
            if len(ranked) >= top_k * 5:
                break
        return ranked
