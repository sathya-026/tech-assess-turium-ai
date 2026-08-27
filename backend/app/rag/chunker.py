"""Text extraction and structure-aware chunking with character offsets.

Every chunk carries (char_start, char_end) into the original raw text. That is
what makes "show me the source snippet in the document" work in the UI without
a fuzzy string search on the frontend.

Offsets survive the pipeline because both passes are position-preserving:
_split_with_offsets never drops or reorders characters, and the overlap tail in
_merge is literally the preceding characters of the same document, so a merged
chunk is still one contiguous span.
"""

import re
from dataclasses import dataclass

from app.config import settings

HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SEPARATORS = ["\n\n", "\n", ". ", ", ", " ", ""]



@dataclass
class ChunkRecord:
    text: str
    section_path: str
    char_start: int
    char_end: int
    position: int = 0


def _split_sections(text: str) -> list[tuple[list[str], int, int]]:
    """Return (heading_path, start, end) spans. Header lines are excluded from
    the body but their titles are carried in the path."""
    sections: list[tuple[list[str], int, int]] = []
    stack: dict[int, str] = {}
    path: list[str] = []
    body_start = 0
    offset = 0

    for line in text.split("\n"):
        line_end = offset + len(line)
        match = HEADER_RE.match(line)
        if match:
            if offset > body_start:
                sections.append((list(path), body_start, offset))
            level = len(match.group(1))
            stack[level] = match.group(2).strip()
            for deeper in [lvl for lvl in stack if lvl > level]:
                del stack[deeper]
            path = [stack[lvl] for lvl in sorted(stack)]
            body_start = line_end + 1
        offset = line_end + 1

    if body_start < len(text):
        sections.append((list(path), body_start, len(text)))
    return sections


def _split_with_offsets(text: str, start: int, size: int,
                        separators: list[str]) -> list[tuple[int, int]]:
    """Break [start, start+len(text)) into spans no longer than `size`."""
    if len(text) <= size:
        return [(start, start + len(text))] if text.strip() else []

    for i, sep in enumerate(separators):
        if sep == "":
            return [(start + j, start + min(j + size, len(text)))
                    for j in range(0, len(text), size)]
        if sep not in text:
            continue

        spans: list[tuple[int, int]] = []
        cursor = 0
        parts = text.split(sep)
        for index, part in enumerate(parts):
            piece = part + (sep if index < len(parts) - 1 else "")
            piece_start = start + cursor
            cursor += len(piece)
            if not piece.strip():
                continue
            if len(piece) <= size:
                spans.append((piece_start, piece_start + len(piece)))
            else:
                spans.extend(
                    _split_with_offsets(piece, piece_start, size, separators[i + 1:])
                )
        return spans

    return [(start, start + len(text))]


def _merge(spans: list[tuple[int, int]], size: int,
           overlap: int) -> list[tuple[int, int]]:
    """Pack adjacent spans up to `size`, carrying `overlap` chars backward."""
    merged: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None

    for span in spans:
        if current is None:
            current = span
            continue
        if span[1] - current[0] > size:
            merged.append(current)
            current = (max(current[0], current[1] - overlap), span[1])
        else:
            current = (current[0], span[1])

    if current is not None:
        merged.append(current)
    return merged


def chunk_text(text: str) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []

    for path, start, end in _split_sections(text):
        body = text[start:end]
        spans = _split_with_offsets(body, start, settings.chunk_size, SEPARATORS)
        for span_start, span_end in _merge(spans, settings.chunk_size,
                                           settings.chunk_overlap):
            raw = text[span_start:span_end]
            lead = len(raw) - len(raw.lstrip())
            trail = len(raw) - len(raw.rstrip())
            span_start, span_end = span_start + lead, span_end - trail
            if span_end - span_start < settings.min_chunk_chars:
                continue
            records.append(ChunkRecord(
                text=text[span_start:span_end],
                section_path=" > ".join(path),
                char_start=span_start,
                char_end=span_end,
            ))

    for position, record in enumerate(records):
        record.position = position

    # The min_chunk_chars filter exists to drop stray fragments from *inside* a
    # document, not to reject a document for being short. A pasted one-line note
    # is a legitimate item, so if filtering removed everything, keep the whole
    # text as a single chunk.
    if not records and text.strip():
        lead = len(text) - len(text.lstrip())
        records = [ChunkRecord(
            text=text.strip(),
            section_path="",
            char_start=lead,
            char_end=lead + len(text.strip()),
            position=0,
        )]

    return records