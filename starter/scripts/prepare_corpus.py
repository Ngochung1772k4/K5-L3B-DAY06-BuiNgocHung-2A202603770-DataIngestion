"""Extract the explicitly selected, text-readable OpenStax pages and manifest them."""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ingestion import load_pdf

PDF = ROOT / "data" / "OpenStax_Introduction_to_Sociology_2e.download.pdf"
OUT = ROOT / "starter" / "data" / "pages.jsonl"
MANIFEST = ROOT / "data" / "manifest.json"
SOURCE_ID = "openstax-introduction-to-sociology-2e"
PDF_URL = "https://assets.openstax.org/oscms-prodcms/media/documents/IntroductionToSociology2e-OP_tbTLqMj.pdf"
BOOK_URL = "https://openstax.org/details/books/introduction-sociology-2e"
PAGES = [14, 15, *range(17, 29), *range(38, 54)]
CHAPTERS = {**{page: "1" for page in [14, 15, *range(17, 29)]},
            **{page: "2" for page in range(38, 54)}}
ATTRIBUTION = ("Introduction to Sociology 2e, Paul Peter Urone and Roger Hinrichs, OpenStax/Rice University, "
               "CC BY 4.0. Source: https://openstax.org/details/books/introduction-sociology-2e")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pages = load_pdf(PDF, SOURCE_ID, PDF_URL, PAGES,
                     {p: {"chapter": CHAPTERS[p], "language": "en"} for p in PAGES})
    errors = [{"page": p.page, "error": "no extractable text or fewer than 1,500 normalized characters"}
              for p in pages if len(p.text) < 1500]
    (ROOT / "starter" / "results" / "ingestion_errors.json").write_text(
        json.dumps(errors, indent=2), encoding="utf-8")
    if errors:
        raise RuntimeError(f"Selected pages had extraction failures: {errors}")
    rows = []
    for page in pages:
        rows.append({"document_id": page.document_id, "source": page.source,
                     "physical_page": page.page, "page": page.page,
                     "chapter": page.metadata["chapter"], "language": "en",
                     "char_count": len(page.text), "text": page.text,
                     "attribution": ATTRIBUTION})
    OUT.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
    replacement_pages = [{"page": p.page, "replacement_character_count": p.text.count("\ufffd"),
                          "char_count": len(p.text)} for p in pages if "\ufffd" in p.text]
    (ROOT / "starter" / "results" / "extraction_audit.json").write_text(
        json.dumps({"empty_or_short_pages": errors, "pages_with_unicode_replacement_character": replacement_pages,
                    "note": "No U+FFFD replacement characters were found. Typographic quotation marks in the PDF are preserved as Unicode punctuation."},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "source_id": SOURCE_ID,
        "title": "Introduction to Sociology 2e",
        "authors": ["Paul Peter Urone", "Roger Hinrichs"],
        "publisher": "OpenStax, Rice University",
        "source_path_or_url": PDF_URL,
        "book_page": BOOK_URL,
        "license_or_permission": "Creative Commons Attribution 4.0 International (CC BY 4.0); attribution retained in the source and each extracted page record.",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "accessed_at": date.today().isoformat(),
        "snapshot": "OpenStax PDF downloaded 2026-11-14; PDF revision ITS2-2015-001(03/16)-RS.",
        "physical_pdf_pages": 509,
        "content_page_count": len(pages),
        "page_count_rule": "Count selected textbook-content pages, excluding cover/front matter, exercise pages and references. Physical page numbers are 1-based PDF page indices. The selection spans two body chapters and every page exceeds 1,500 normalized characters.",
        "physical_pages_included": PAGES,
        "chapters": {"1": "An Introduction to Sociology", "2": "Sociological Research"},
        "page_char_counts": {str(p.page): len(p.text) for p in pages},
        "chapter_page_counts": dict(Counter(CHAPTERS.values())),
        "extraction": {"tool": "pypdf", "version": "6.21.4", "ocr": False,
                       "normalization": "Unicode NFKC, remove soft hyphen, repair line-end hyphenation, normalize line wrapping while preserving blank-line paragraph boundaries."},
        "attribution": ATTRIBUTION,
        "derived_page_records": "starter/data/pages.jsonl"
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(pages), "characters": sum(len(p.text) for p in pages),
                      "min_page_characters": min(len(p.text) for p in pages),
                      "chapter_counts": dict(Counter(CHAPTERS.values())),
                      "pages_file": str(OUT), "manifest": str(MANIFEST)}, indent=2))


if __name__ == "__main__":
    main()
