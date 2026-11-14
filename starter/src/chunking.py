"""Fixed-window and paragraph-aware chunking with stable, traceable IDs."""
import hashlib
import re
from .models import Chunk, DocumentPage


def _make_chunk(page: DocumentPage, text: str, ordinal: int, start: int, end: int,
                strategy: str) -> Chunk:
    chunk_id = hashlib.sha1(
        f"{page.document_id}|{page.page}|{strategy}|{start}|{end}|{text}".encode("utf-8")
    ).hexdigest()
    metadata = {**page.metadata, "chunk_index": ordinal, "char_start": start,
                "char_end": end, "char_count": len(text)}
    return Chunk(chunk_id, page.document_id, page.source, page.page, text, metadata)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split on character windows, backing up to word boundaries where possible."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > overlap >= 0")
    text, chunks, start = page.text, [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        value = text[start:end].strip()
        if value:
            chunks.append(_make_chunk(page, value, len(chunks), start, end, "fixed"))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group sentence/paragraph units up to max_size, preserving sentence boundaries.

    PDF text extraction often preserves line wrapping but loses blank paragraph
    markers. Sentence boundaries are therefore the reliable structural fallback.
    """
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    text = page.text
    cuts = [m.start() for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)]
    boundaries = [0, *cuts, len(text)]
    blocks = []
    for left, right in zip(boundaries, boundaries[1:]):
        start, end = left, right
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            blocks.append((start, end, text[start:end]))
    pieces: list[tuple[int, int, str]] = []
    for start, end, block in blocks:
        if len(block) <= max_size:
            pieces.append((start, end, block))
            continue
        cursor = start
        while cursor < end:
            stop = min(cursor + max_size, end)
            if stop < end:
                boundary = text.rfind(" ", cursor + max_size // 2, stop)
                if boundary > cursor:
                    stop = boundary
            pieces.append((cursor, stop, text[cursor:stop].strip()))
            cursor = stop
    grouped: list[tuple[int, int, str]] = []
    for start, end, block in pieces:
        if grouped and end - grouped[-1][0] <= max_size:
            old_start, _, old_text = grouped[-1]
            grouped[-1] = (old_start, end, f"{old_text}\n\n{block}")
        else:
            grouped.append((start, end, block))
    return [_make_chunk(page, text, i, start, end, "paragraph")
            for i, (start, end, text) in enumerate(grouped)]
