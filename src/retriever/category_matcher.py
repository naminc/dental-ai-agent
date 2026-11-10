from __future__ import annotations


class CategoryMatcher:
    """Maps requested disease/category terms to metadata row indices."""

    def __init__(self, metadata: list[dict]) -> None:
        self.metadata = metadata

    def match(self, categories: list[str] | None) -> set[int] | None:
        if not categories:
            return None

        matched: set[int] = set()
        for index, document in enumerate(self.metadata):
            disease = document.get("metadata", {}).get("disease", "")
            if not disease:
                continue

            disease_lower = disease.lower()
            disease_words = set(disease_lower.split())
            for keyword in categories:
                keyword_lower = keyword.lower().strip()
                if not keyword_lower:
                    continue
                keyword_words = set(keyword_lower.split())

                if keyword_lower in disease_lower or disease_lower in keyword_lower:
                    matched.add(index)
                    break
                if keyword_words.issubset(disease_words) or disease_words.issubset(
                    keyword_words
                ):
                    matched.add(index)
                    break

        return matched if matched else None
