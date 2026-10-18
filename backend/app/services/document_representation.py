"""Deterministic analytical-document cleaning, preview, and token chunking.

This module is shared by UC-14 mapping and UC-16 peer benchmarking.  It keeps
source text reviewable: no LLM rewriting, summarisation, or OCR is performed.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, replace
from typing import Callable, Iterable, Sequence

from app.core.config import get_settings
from app.core.exceptions import ValidationFailure
from app.services.embeddings import get_embedding_tokenizer

_HEADING_WORDS = re.compile(
    r"\b(title|overview|description|aims?|objectives?|learning outcomes?|topics?|"
    r"syllabus|curriculum|modules?|courses?|requirements?|eligibility|duties|"
    r"responsibilities|scope|deliverables|technical|skills?|knowledge)\b",
    re.IGNORECASE,
)
_ADMIN_ONLY = re.compile(
    r"\b(table of contents|document control|version history|approved by|copyright|"
    r"contact us|office hours|telephone|fax|page \d+|last updated)\b",
    re.IGNORECASE,
)
_PROGRAMME_CUES = re.compile(
    r"\b(programme|program|curriculum|year [1-6]|semester [1-9]|course catalogue|"
    r"degree structure|credit hours?|core modules?|elective modules?)\b",
    re.IGNORECASE,
)
_COURSE_CUES = re.compile(r"\b(course|module)\s+(code|title|description)\b", re.IGNORECASE)
_COURSE_CODE = re.compile(r"\b[A-Z]{2,5}[ -]?\d{3,4}[A-Z]?\b")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass(frozen=True)
class SourceSection:
    id: str
    filename: str
    section: str
    excerpt: str
    included_by_default: bool
    token_count: int = 0


@dataclass(frozen=True)
class DocumentChunk:
    filename: str
    section: str
    excerpt: str
    token_count: int


@dataclass(frozen=True)
class DocumentPreview:
    sections: list[SourceSection]
    warnings: list[str]
    appears_single_course: bool
    embedding_model: str
    chunk_max_tokens: int
    overlap_tokens: int
    max_source_tokens: int
    max_chunks: int
    warning_source_tokens: int

    def as_dict(self) -> dict:
        return {
            "sections": [asdict(section) for section in self.sections],
            "warnings": self.warnings,
            "appears_single_course": self.appears_single_course,
            "embedding_model": self.embedding_model,
            "chunk_max_tokens": self.chunk_max_tokens,
            "overlap_tokens": self.overlap_tokens,
            "max_source_tokens": self.max_source_tokens,
            "max_chunks": self.max_chunks,
            "warning_source_tokens": self.warning_source_tokens,
        }


def _normalise_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _remove_repeated_page_furniture(raw_text: str) -> str:
    pages = raw_text.split("\f")
    if len(pages) < 2:
        return raw_text
    candidates: list[list[str]] = []
    for page in pages:
        lines = [_normalise_line(line) for line in page.splitlines()]
        lines = [line for line in lines if line]
        candidates.append(lines[:3] + lines[-3:])
    counts: dict[str, int] = {}
    for lines in candidates:
        for line in set(lines):
            key = line.casefold()
            if 3 <= len(line) <= 160:
                counts[key] = counts.get(key, 0) + 1
    threshold = max(2, (len(pages) + 1) // 2)
    repeated = {line for line, count in counts.items() if count >= threshold}
    cleaned_pages = []
    for page in pages:
        kept = [
            line for line in page.splitlines()
            if _normalise_line(line).casefold() not in repeated
            and not re.fullmatch(r"\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*", line, re.IGNORECASE)
        ]
        cleaned_pages.append("\n".join(kept))
    return "\n\n".join(cleaned_pages)


def _looks_like_heading(line: str) -> bool:
    clean = line.strip().rstrip(":")
    if not clean or len(clean) > 140 or clean.endswith((".", ";", ",")):
        return False
    if re.match(r"^(\d+(?:\.\d+)*|[A-Z]|[IVX]+)[.)]?\s+\S", clean):
        return True
    words = clean.split()
    if len(words) <= 12 and _ADMIN_ONLY.search(clean):
        return True
    if len(words) <= 12 and _HEADING_WORDS.search(clean):
        return True
    letters = [char for char in clean if char.isalpha()]
    return bool(letters) and len(words) <= 10 and all(char.isupper() for char in letters)


def extract_sections(filename: str, raw_text: str) -> list[SourceSection]:
    """Clean parser output and split it into reviewable heading/paragraph sections."""
    cleaned = _remove_repeated_page_furniture(raw_text)
    cleaned = re.sub(r"(?<=\w)-\n(?=\w)", "", cleaned)
    lines = [_normalise_line(line) for line in cleaned.splitlines()]

    sections: list[tuple[str, str]] = []
    heading = "Document content"
    body: list[str] = []

    def flush() -> None:
        excerpt = "\n".join(body).strip()
        if excerpt:
            sections.append((heading, excerpt))

    for line in lines:
        if not line:
            if body and body[-1] != "":
                body.append("")
            continue
        if _looks_like_heading(line):
            flush()
            heading = line.rstrip(":")
            body = []
        else:
            body.append(line)
    flush()

    # Documents without recognizable headings are common. Fall back to
    # reviewable paragraph groups instead of treating the whole file as one
    # confidently detected section or discarding its content.
    if len(sections) == 1 and sections[0][0] == "Document content":
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", sections[0][1]) if part.strip()]
        if len(paragraphs) > 1:
            sections = [
                (f"Paragraph {index}", paragraph)
                for index, paragraph in enumerate(paragraphs, start=1)
            ]

    result: list[SourceSection] = []
    for index, (detected_heading, excerpt) in enumerate(sections):
        content_words = re.findall(r"\b[\w+#.-]+\b", excerpt)
        administrative = bool(_ADMIN_ONLY.search(f"{detected_heading} {excerpt}"))
        include = len(content_words) >= 5 and not (
            administrative and not _HEADING_WORDS.search(excerpt)
        )
        digest = hashlib.sha256(
            f"{filename}\0{index}\0{detected_heading}\0{excerpt}".encode("utf-8")
        ).hexdigest()[:16]
        result.append(
            SourceSection(
                id=digest,
                filename=filename,
                section=detected_heading,
                excerpt=excerpt,
                included_by_default=include,
            )
        )
    return result


def _appears_single_course(sections: Sequence[SourceSection]) -> bool:
    text = "\n".join(f"{item.section}\n{item.excerpt}" for item in sections)
    codes = {match.group(0).replace(" ", "").replace("-", "") for match in _COURSE_CODE.finditer(text)}
    return bool(_COURSE_CUES.search(text)) and len(codes) <= 1 and not _PROGRAMME_CUES.search(text)


def preview_documents(
    documents: Sequence[tuple[str, str]],
    *,
    max_source_tokens: int,
    max_chunks: int,
) -> DocumentPreview:
    settings = get_settings()
    sections = [
        section
        for filename, text in documents
        for section in extract_sections(filename, text)
    ]
    included = [section for section in sections if section.included_by_default]
    if not included:
        raise ValidationFailure(
            "Could not identify meaningful analytical text. Upload a text-based copy "
            "with selectable text; scanned or image-only PDFs require OCR and are not supported."
        )
    tokenizer, usable_limit, _ = get_embedding_tokenizer()
    sections = [
        replace(
            section,
            token_count=len(
                tokenizer.encode(
                    section.excerpt, add_special_tokens=False, truncation=False
                )
            ),
        )
        for section in sections
    ]
    included = [section for section in sections if section.included_by_default]
    appears_single_course = _appears_single_course(included)
    warnings: list[str] = []
    if appears_single_course:
        warnings.append(
            "The preview appears to describe one course or module. Confirm that the "
            "selected files adequately cover the wider programme before peer benchmarking."
        )
    selected_tokens = sum(section.token_count for section in included)
    warning_source_tokens = max(1, int(max_source_tokens * 0.8))
    if selected_tokens >= warning_source_tokens:
        warnings.append(
            f"The default selection contains {selected_tokens:,} source tokens and is "
            f"close to the {max_source_tokens:,}-token analysis limit. Exclude irrelevant sections."
        )
    return DocumentPreview(
        sections=sections,
        warnings=warnings,
        appears_single_course=appears_single_course,
        embedding_model=settings.embedding_model,
        chunk_max_tokens=min(settings.document_chunk_max_tokens, usable_limit),
        overlap_tokens=settings.document_chunk_overlap_tokens,
        max_source_tokens=max_source_tokens,
        max_chunks=max_chunks,
        warning_source_tokens=warning_source_tokens,
    )


def select_sections(
    preview: DocumentPreview, included_ids: Iterable[str] | None
) -> list[SourceSection]:
    requested = set(included_ids or ())
    selected = [
        section for section in preview.sections
        if section.id in requested or (not requested and section.included_by_default)
    ]
    if not selected:
        raise ValidationFailure("Include at least one meaningful extracted section.")
    unknown = requested - {section.id for section in preview.sections}
    if unknown:
        raise ValidationFailure("The document preview is stale. Preview the files again.")
    return selected


def _split_long_piece(
    text: str, count_tokens: Callable[[str], int], max_tokens: int
) -> list[str]:
    words = text.split()
    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and count_tokens(candidate) > max_tokens:
            pieces.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk_sections(
    sections: Sequence[SourceSection],
    *,
    count_tokens: Callable[[str], int],
    max_tokens: int,
    overlap_tokens: int,
) -> list[DocumentChunk]:
    """Create sentence-aware, token-bounded chunks without dropping final text."""
    chunks: list[DocumentChunk] = []
    for source in sections:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", source.excerpt) if part.strip()]
        units: list[str] = []
        for paragraph in paragraphs:
            sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(paragraph) if part.strip()]
            for sentence in sentences:
                if count_tokens(sentence) > max_tokens:
                    units.extend(_split_long_piece(sentence, count_tokens, max_tokens))
                else:
                    units.append(sentence)
        current: list[str] = []
        for unit in units:
            candidate = " ".join([*current, unit])
            if current and count_tokens(candidate) > max_tokens:
                excerpt = " ".join(current)
                chunks.append(DocumentChunk(source.filename, source.section, excerpt, count_tokens(excerpt)))
                overlap: list[str] = []
                if overlap_tokens:
                    for previous in reversed(current):
                        candidate_overlap = " ".join([previous, *overlap])
                        if overlap and count_tokens(candidate_overlap) > overlap_tokens:
                            break
                        overlap.insert(0, previous)
                        if count_tokens(candidate_overlap) >= overlap_tokens:
                            break
                current = overlap
                while current and count_tokens(" ".join([*current, unit])) > max_tokens:
                    current.pop(0)
            current.append(unit)
        if current:
            excerpt = " ".join(current)
            chunks.append(DocumentChunk(source.filename, source.section, excerpt, count_tokens(excerpt)))
    return chunks


def build_chunks(
    sections: Sequence[SourceSection],
    *,
    max_source_tokens: int,
    max_chunks: int,
) -> tuple[list[DocumentChunk], int]:
    """Tokenize with the configured embedding model and enforce its real limit."""
    settings = get_settings()
    tokenizer, usable_limit, _ = get_embedding_tokenizer()
    max_tokens = min(settings.document_chunk_max_tokens, usable_limit)
    if settings.document_chunk_overlap_tokens >= max_tokens:
        raise ValidationFailure("Document chunk overlap must be smaller than the token limit.")

    def count_tokens(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False, truncation=False))

    source_tokens = sum(count_tokens(section.excerpt) for section in sections)
    if source_tokens > max_source_tokens:
        raise ValidationFailure(
            f"The selected content contains {source_tokens:,} source tokens; the limit is "
            f"{max_source_tokens:,}. Exclude administrative or less relevant sections."
        )

    chunks = chunk_sections(
        sections,
        count_tokens=count_tokens,
        max_tokens=max_tokens,
        overlap_tokens=settings.document_chunk_overlap_tokens,
    )
    if not chunks:
        raise ValidationFailure("No usable analytical document chunks remain after cleaning.")
    if len(chunks) > max_chunks:
        raise ValidationFailure(
            f"The selected content produces {len(chunks)} chunks; the limit is "
            f"{max_chunks}. Exclude administrative or less relevant sections."
        )
    return chunks, max_tokens


def chunks_payload(chunks: Sequence[DocumentChunk]) -> list[dict]:
    return [asdict(chunk) for chunk in chunks]
