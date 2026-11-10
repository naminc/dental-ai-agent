from __future__ import annotations

from src.lib.constants import EXPAND_QUERY_SYSTEM_PROMPT
from src.providers.protocols import ChatCompletionProvider


class QueryExpander:
    """Creates query variants using an injected chat-completion boundary."""

    def __init__(self, provider: ChatCompletionProvider | None) -> None:
        self.provider = provider

    def expand(self, query: str) -> list[str]:
        if not self.provider:
            return [query]

        try:
            raw = self.provider.complete(
                messages=[
                    {"role": "system", "content": EXPAND_QUERY_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0.5,
                max_tokens=200,
            )
            variants = [
                line.strip().lstrip("- ").strip()
                for line in raw.splitlines()
                if line.strip()
            ]
            return [query] + [variant for variant in variants[:2] if variant]
        except Exception:
            return [query]
