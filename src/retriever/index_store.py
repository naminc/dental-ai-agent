from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import ClassVar

import faiss


class IndexStore:
    """Loads and shares one FAISS index/metadata pair per process."""

    _cache: ClassVar[dict[tuple[Path, Path], tuple[faiss.Index, list[dict]]]] = {}
    _cache_lock: ClassVar[Lock] = Lock()

    def __init__(self, db_dir: Path, engine: str) -> None:
        self.engine = engine
        self.index_path = (db_dir / "faiss.index").resolve()
        self.metadata_path = (db_dir / "metadata.json").resolve()
        self.index, self.metadata = self._load()

    def _load(self) -> tuple[faiss.Index, list[dict]]:
        key = (self.index_path, self.metadata_path)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

            if not self.index_path.is_file():
                raise FileNotFoundError(
                    f"FAISS index not found at: {self.index_path}\n"
                    f"Please run: python -m src.retriever.ingest --engine {self.engine}"
                )
            if not self.metadata_path.is_file():
                raise FileNotFoundError(
                    f"Retriever metadata not found at: {self.metadata_path}\n"
                    f"Please run: python -m src.retriever.ingest --engine {self.engine}"
                )

            try:
                index = faiss.read_index(str(self.index_path))
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load FAISS index at: {self.index_path}"
                ) from exc

            try:
                with self.metadata_path.open("r", encoding="utf-8") as file:
                    metadata = json.load(file)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load retriever metadata at: {self.metadata_path}"
                ) from exc

            if not isinstance(metadata, list):
                raise ValueError(
                    f"Retriever metadata must be a JSON list: {self.metadata_path}"
                )

            loaded = (index, metadata)
            self._cache[key] = loaded
            return loaded

    @classmethod
    def clear_cache(cls) -> None:
        """Test/maintenance hook; production code normally never needs this."""
        with cls._cache_lock:
            cls._cache.clear()
