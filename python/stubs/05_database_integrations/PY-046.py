"""PY-046 - Consume a paginated REST-style source safely.

Question: python/questions/05_database_integrations/PY-046.md   (python -m lab show PY-046)
Check   : python -m lab check PY-046
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol


class PageClient(Protocol):
    def get_page(self, token: str | None, page_size: int | None = None) -> dict:
        """Return {"items": [dict, ...], "next": str | None}. token=None requests the first page."""
        raise NotImplementedError


class PaginationLoopError(RuntimeError):
    """The server handed out a page token that was already requested."""


class PaginationLimitError(RuntimeError):
    """More than max_pages pages would be needed."""


def iterate_pages(client: PageClient, *, page_size: int | None = None, max_pages: int = 1000,
                  id_key: str = "id") -> Iterator[dict]:
    """Yield every distinct record from all pages, lazily. See the question for the rules."""
    raise NotImplementedError
