"""PY-046 reference solution: lazy generator with loop detection, id de-duplication and a page cap."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class PageClient(Protocol):
    def get_page(self, token: str | None, page_size: int | None = None) -> dict: ...


class PaginationLoopError(RuntimeError):
    """The server handed out a page token that was already requested."""


class PaginationLimitError(RuntimeError):
    """More than max_pages pages would be needed."""


def iterate_pages(client: PageClient, *, page_size: int | None = None, max_pages: int = 1000,
                  id_key: str = "id") -> Iterator[dict]:
    if page_size is not None and (isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1):
        raise ValueError("page_size must be a positive int or None")
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")
    return _walk(client, page_size, max_pages, id_key)


def _walk(client, page_size, max_pages, id_key) -> Iterator[dict]:
    seen_ids: set = set()
    requested: set = set()        # tokens already sent; None stands for the first page
    token = None
    pages = 0
    while True:
        if pages >= max_pages:
            raise PaginationLimitError(f"more than {max_pages} pages")
        requested.add(token)
        page = client.get_page(token, page_size=page_size)
        pages += 1
        for item in page["items"]:
            try:
                key = item[id_key]
            except KeyError:
                raise ValueError(f"record without {id_key!r}: {item!r}") from None
            if key in seen_ids:
                continue
            seen_ids.add(key)
            yield item
        token = page.get("next")
        if token is None:
            return
        if token in requested:
            raise PaginationLoopError(f"token {token!r} was already requested")
