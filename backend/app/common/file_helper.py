"""
app/common/file_helper.py

Document text extraction. The single place file format matters — everything
downstream (chunker, embedder, store, retriever) is format-blind.

Unlike the reference, bytes arrive directly from the multipart upload rather
than being downloaded from S3. There is no object store in this service: an
item's text lives in items.raw_text, which is also what the frontend slices
with the chunk offsets to highlight a source in context.
"""

from __future__ import annotations

import re

TEXT_MIMES = {
    "text/plain", "text/markdown", "text/csv",
    "application/json", "text/html", "text/x-rst",
}
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".log", ".html",
}


def extract_text(file_bytes: bytes, filename: str, mime_type: str | None = None) -> str:
    """
    Extract plain text from raw upload bytes.

    Raises ValueError for unsupported types — the ingest router turns that into
    a per-file `skipped` entry rather than failing the whole request.
    """
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if suffix in TEXT_SUFFIXES or (mime_type or "") in TEXT_MIMES:
        return _extract_plaintext(file_bytes)

    if suffix == ".pdf" or mime_type == "application/pdf":
        return _extract_pdf(file_bytes)

    if suffix == ".docx" or mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return _extract_docx(file_bytes)

    raise ValueError(f"Unsupported file type: {suffix or mime_type or 'unknown'}")


def _extract_plaintext(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")
    return _clean_whitespace(text)


def _extract_pdf(file_bytes: bytes) -> str:
    """
    pymupdf4llm rather than pypdf: it emits markdown headers, which is what
    keeps Chunk.section_path meaningful on PDFs. With flat text extraction every
    chunk gets an empty section path and that metadata is dead weight.
    """
    try:
        import io

        import pymupdf
        import pymupdf4llm
    except ImportError as exc:
        raise ValueError(
            "PDF support not installed. `pip install pymupdf4llm`"
        ) from exc

    document = pymupdf.open(stream=io.BytesIO(file_bytes), filetype="pdf")
    return _clean_whitespace(pymupdf4llm.to_markdown(document))


def _extract_docx(file_bytes: bytes) -> str:
    try:
        import io

        import mammoth
    except ImportError as exc:
        raise ValueError("DOCX support not installed. `pip install mammoth`") from exc

    return _clean_whitespace(
        mammoth.convert_to_markdown(io.BytesIO(file_bytes)).value
    )


def _clean_whitespace(text: str) -> str:
    """
    Normalize line endings and collapse runs of spaces / blank lines.

    Deliberately conservative: this runs BEFORE chunking, so whatever it
    produces is what gets stored as raw_text and what the offsets index into.
    Rewriting text after offsets are computed would break highlighting.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
