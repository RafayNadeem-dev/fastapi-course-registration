"""Two-stage parser: convert source (pdf/docx) to markdown on disk, then
header-aware chunk the markdown.

No DB, no FastAPI imports.
"""

from dataclasses import dataclass, field
from pathlib import Path

import mammoth
import pymupdf4llm
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_SUPPORTED_MIMES = {PDF_MIME, DOCX_MIME}

_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


@dataclass(frozen=True)
class ParsedChunk:
    chunk_index: int
    text: str
    page_number: int | None
    char_count: int
    metadata: dict = field(default_factory=dict)


class ParsingError(ValueError):
    """Base for permanent parsing/conversion failures. Retry will not help."""


class UnsupportedMimeError(ParsingError):
    """Mime type is not in the supported set."""


class PasswordProtectedError(ParsingError):
    """Document is encrypted or password-protected."""


class CorruptDocumentError(ParsingError):
    """Document is malformed and cannot be parsed by the converter."""


class EmptyDocumentError(ParsingError):
    """Conversion succeeded but produced no extractable text."""


def markdown_path_for(stored_path: str) -> Path:
    return Path(stored_path).with_suffix(Path(stored_path).suffix + ".md")


def convert_to_markdown(stored_path: str, mime_type: str) -> Path:
    """Convert source file to markdown next to it. Skip if `.md` exists.

    Returns path to the markdown file. Idempotent.
    """
    source = Path(stored_path)
    if not source.exists():
        raise FileNotFoundError(f"stored file not found at {stored_path}")

    md_path = markdown_path_for(stored_path)
    if md_path.exists():
        return md_path

    if mime_type not in _SUPPORTED_MIMES:
        raise UnsupportedMimeError(f"unsupported mime type {mime_type!r}")

    try:
        if mime_type == PDF_MIME:
            text = pymupdf4llm.to_markdown(str(source))
        elif mime_type == DOCX_MIME:
            with source.open("rb") as fh:
                text = mammoth.convert_to_markdown(fh).value
    except ParsingError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "password" in msg or "encrypted" in msg:
            raise PasswordProtectedError(
                "password-protected document not supported"
            ) from exc
        raise CorruptDocumentError(f"convert failed: {exc}") from exc

    text = (text or "").strip()
    if not text:
        raise EmptyDocumentError("document contains no extractable text")

    md_path.write_text(text, encoding="utf-8")
    return md_path


def chunk_markdown(
    md_path: Path,
    chunk_size: int,
    chunk_overlap: int,
) -> list[ParsedChunk]:
    if not md_path.exists():
        raise FileNotFoundError(f"markdown file not found at {md_path}")

    text = md_path.read_text(encoding="utf-8")

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    sections = header_splitter.split_text(text)
    if not sections:
        # No headers detected — fall back to whole document as one section.
        char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        sections_iter = [({}, piece) for piece in char_splitter.split_text(text)]
    else:
        char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        sections_iter = []
        for section in sections:
            section_meta = dict(section.metadata)
            for piece in char_splitter.split_text(section.page_content):
                sections_iter.append((section_meta, piece))

    chunks: list[ParsedChunk] = []
    for section_meta, piece in sections_iter:
        piece = piece.strip()
        if not piece:
            continue
        chunks.append(
            ParsedChunk(
                chunk_index=len(chunks),
                text=piece,
                page_number=None,
                char_count=len(piece),
                metadata=section_meta,
            )
        )

    if not chunks:
        raise EmptyDocumentError("document contains no extractable text")

    return chunks
