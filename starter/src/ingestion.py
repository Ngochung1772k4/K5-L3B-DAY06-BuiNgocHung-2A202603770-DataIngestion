"""Read and normalize source data while retaining physical-page provenance."""
import unicodedata
from pathlib import Path
from collections.abc import Iterable
from pypdf import PdfReader
from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str,
             selected_pages: Iterable[int] | None = None,
             page_metadata: dict[int, dict] | None = None) -> list[DocumentPage]:
    """Extract physical PDF pages (1-based); callers record empty pages as errors."""
    wanted = set(selected_pages) if selected_pages is not None else None
    metadata = page_metadata or {}
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for number, pdf_page in enumerate(reader.pages, start=1):
        if wanted is not None and number not in wanted:
            continue
        text = normalize_text(pdf_page.extract_text() or "")
        pages.append(DocumentPage(document_id, source, number, text,
                                  dict(metadata.get(number, {})), len(text)))
    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode and line wrapping; retain paragraph and heading boundaries."""
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # PDF line wrapping often splits words with a hyphen at a line boundary.
    text = __import__("re").sub(r"(?<=\w)-\n(?=\w)", "", text)
    paragraphs = []
    for block in __import__("re").split(r"\n\s*\n", text):
        lines = [__import__("re").sub(r"\s+", " ", line).strip()
                 for line in block.split("\n")]
        paragraph = " ".join(line for line in lines if line)
        if paragraph:
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs).strip()
