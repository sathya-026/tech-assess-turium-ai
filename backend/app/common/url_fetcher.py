"""
app/common/url_fetcher.py

Server-side URL fetching for ingestion.

Split into two halves on purpose:

  validate_url()  — pure, synchronous, no network. Runs in the /ingest request
                    so a malformed URL is rejected immediately with a clear
                    reason instead of failing minutes later in the background.

  fetch_url()     — network. Runs inside the indexing pipeline, because a slow
                    or hanging site must not hold the ingest request open. This
                    is the same shape as the reference's S3 download stage: a
                    fetch step at the head of the background pipeline.

HTML extraction prefers trafilatura, which strips navigation, headers, footers,
and ads to isolate the main article body. That matters more here than it looks:
boilerplate is near-identical across every page of a site, so indexing it
creates many chunks that are highly similar to each other and to nothing the
user will ask about. They crowd real content out of top_k.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 20.0
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (compatible; RAG-Ingest/0.2; +local)"

ALLOWED_SCHEMES = {"http", "https"}

HTML_MIMES = {"text/html", "application/xhtml+xml"}
PLAINTEXT_MIMES = {
    "text/plain", "text/markdown", "text/csv", "application/json", "text/x-rst",
}


@dataclass
class FetchedPage:
    url: str            # final URL after redirects
    title: str
    text: str
    content_type: str


class UrlFetchError(Exception):
    """Raised for any failure reaching or parsing a URL. Message is user-safe."""


# ---------------------------------------------------------------------------
# Validation (synchronous, no network)
# ---------------------------------------------------------------------------

def validate_url(raw: str) -> str:
    """
    Normalize and sanity-check a URL. Returns the cleaned URL.
    Raises ValueError with a displayable reason.
    """
    candidate = raw.strip()
    if not candidate:
        raise ValueError("empty URL")

    # Bare domains are what users actually paste; assume https rather than
    # rejecting them.
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"unsupported scheme '{parsed.scheme}' (only http/https)")
    if not parsed.netloc:
        raise ValueError("malformed URL — no host")
    if "." not in parsed.netloc.split(":")[0] and parsed.hostname != "localhost":
        raise ValueError(f"malformed host '{parsed.netloc}'")

    return candidate


# ---------------------------------------------------------------------------
# Fetch (network, runs in the background pipeline)
# ---------------------------------------------------------------------------

async def fetch_url(url: str) -> FetchedPage:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise UrlFetchError(
            f"Server returned {exc.response.status_code} for {url}"
        ) from exc
    except httpx.TimeoutException as exc:
        raise UrlFetchError(
            f"Timed out after {FETCH_TIMEOUT_SECONDS:.0f}s fetching {url}"
        ) from exc
    except httpx.HTTPError as exc:
        raise UrlFetchError(f"Could not reach {url}: {type(exc).__name__}") from exc

    if len(response.content) > MAX_RESPONSE_BYTES:
        raise UrlFetchError(
            f"Response exceeds {MAX_RESPONSE_BYTES // 1024 // 1024}MB limit"
        )

    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    final_url = str(response.url)

    if content_type in HTML_MIMES or not content_type:
        text, title = _extract_html(response.text, final_url)
    elif content_type in PLAINTEXT_MIMES:
        text, title = response.text, ""
    elif content_type == "application/pdf":
        from app.common.file_helper import extract_text
        text, title = extract_text(response.content, "download.pdf", content_type), ""
    else:
        raise UrlFetchError(f"Unsupported content type '{content_type}' at {url}")

    text = _clean(text)
    if not text.strip():
        raise UrlFetchError(f"No readable text extracted from {url}")

    return FetchedPage(
        url=final_url,
        title=title or _title_from_url(final_url),
        text=text,
        content_type=content_type or "text/html",
    )


# ---------------------------------------------------------------------------
# HTML -> text
# ---------------------------------------------------------------------------

def _extract_html(raw_html: str, url: str) -> tuple[str, str]:
    """
    Returns (text, title).

    trafilatura is emitted as markdown so heading structure survives — that is
    what keeps Chunk.section_path meaningful for web pages, the same reason
    file_helper uses pymupdf4llm rather than flat PDF text extraction.
    """
    try:
        import trafilatura

        extracted = trafilatura.extract(
            raw_html,
            output_format="markdown",
            include_links=False,
            include_comments=False,
            include_tables=True,
            url=url,
        )
        if extracted and extracted.strip():
            metadata = trafilatura.extract_metadata(raw_html)
            title = (metadata.title or "") if metadata else ""
            return extracted, title
        logger.info("trafilatura found no main content for %s, falling back", url)
    except ImportError:
        logger.info("trafilatura not installed, using stdlib HTML stripper")
    except Exception:
        logger.warning("trafilatura failed on %s, falling back", url, exc_info=True)

    return _strip_tags(raw_html)


class _TextExtractor(HTMLParser):
    """
    Stdlib fallback. Keeps the whole page including navigation, so results are
    noisier than trafilatura — acceptable as a fallback, not as a default.
    """

    SKIP = {"script", "style", "noscript", "svg", "head", "iframe"}
    BLOCK = {
        "p", "div", "br", "li", "tr", "section", "article", "header", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
    }
    HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip_depth = 0
        self._in_title = False
        self._pending_heading: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.HEADINGS:
            self.parts.append(f"\n\n{self.HEADINGS[tag]} ")
            self._pending_heading = tag
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag == self._pending_heading:
            self.parts.append("\n")
            self._pending_heading = None
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0 and data.strip():
            self.parts.append(data)


def _strip_tags(raw_html: str) -> tuple[str, str]:
    parser = _TextExtractor()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception:
        # Malformed markup: fall back to a blunt regex strip rather than failing
        # the whole ingest.
        logger.warning("HTML parse failed, using regex strip", exc_info=True)
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html,
                      flags=re.S | re.I)
        return html.unescape(re.sub(r"<[^>]+>", " ", text)), ""

    return "".join(parser.parts), parser.title.strip()


def _clean(text: str) -> str:
    """
    Normalize whitespace.

    Must run BEFORE chunking, never after: chunk offsets index into the stored
    raw_text, so rewriting the text afterwards would break citation
    highlighting.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path:
        slug = path.rsplit("/", 1)[-1]
        slug = re.sub(r"\.\w{1,5}$", "", slug)
        if slug:
            return f"{parsed.netloc} — {slug.replace('-', ' ').replace('_', ' ')}"
    return parsed.netloc