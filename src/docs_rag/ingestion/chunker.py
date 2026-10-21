import hashlib
import re
import uuid
from dataclasses import dataclass

from docs_rag.config import Settings
from docs_rag.ingestion.models import (
    Block,
    BlockKind,
    Chunk,
    ContentType,
    DocFile,
    Section,
)
from docs_rag.ingestion.parser import parse_markdown
from docs_rag.ingestion.tokens import TokenCounter

_FENCE_OPEN_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_WORD_RE = re.compile(r"\S+\s*")
_HTML_TAG_RE = re.compile(
    r"</?(?:a|abbr|article|aside|audio|b|blockquote|br|button|code|dd|del|details|dfn|div|dl|dt|em|figcaption|figure|footer|form|h[1-6]|header|hr|i|iframe|img|input|ins|kbd|label|li|main|mark|nav|ol|p|pre|q|s|script|section|small|source|span|strong|style|sub|summary|sup|table|tbody|td|tfoot|th|thead|tr|u|ul|video)(?:\s[^>]*)?/?>",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ChunkContext:
    project: str
    version: str
    path: str
    url: str
    title: str
    section: str
    language: str


def split_blocks(content: str, counter: TokenCounter) -> list[Block]:
    blocks: list[Block] = []
    current: list[str] = []
    fence_char: str | None = None
    fence_len = 0

    def flush() -> None:
        nonlocal current
        text = "\n".join(current).strip()
        if text:
            kind = _classify_block(text)
            if kind != "code":
                text = _HTML_TAG_RE.sub("", text).strip()
            if text:
                blocks.append(
                    Block(
                        kind=kind,
                        text=text,
                        token_count=counter.count(text),
                    )
                )
        current = []

    for line in content.split("\n"):
        if fence_char is not None:
            current.append(line)
            close_match = _FENCE_CLOSE_RE.match(line)
            if (
                close_match
                and close_match.group(1)[0] == fence_char
                and len(close_match.group(1)) >= fence_len
            ):
                fence_char = None
                fence_len = 0
            continue

        open_match = _FENCE_OPEN_RE.match(line)
        if open_match:
            flush()
            fence_char = open_match.group(1)[0]
            fence_len = len(open_match.group(1))
            current.append(line)
            continue

        if not line.strip():
            flush()
            continue

        current.append(line)

    flush()
    return blocks


def chunk_document(doc: DocFile, settings: Settings, counter: TokenCounter) -> list[Chunk]:
    parsed = parse_markdown(doc.text)
    context = ChunkContext(
        project=settings.docs_repo.rsplit("/", 1)[-1],
        version=settings.docs_ref,
        path=doc.relative_path,
        url=doc.url,
        title=parsed.title or doc.title,
        section=doc.section,
        language=settings.docs_language,
    )

    chunks: list[Chunk] = []
    for section in parsed.sections:
        if _is_sponsor_section(section):
            continue
        chunks.extend(
            _chunk_section(
                section=section,
                context=context,
                settings=settings,
                counter=counter,
                start_index=len(chunks),
            )
        )
    return chunks


def _is_sponsor_section(section: Section) -> bool:
    return any("sponsor" in title.casefold() for title in section.heading_path)


def _chunk_section(
    section: Section,
    context: ChunkContext,
    settings: Settings,
    counter: TokenCounter,
    start_index: int,
) -> list[Chunk]:
    content = section.content.strip()
    if not content:
        return []

    blocks = split_blocks(content, counter)
    if not blocks:
        return []

    header = " > ".join(section.heading_path)
    header_prefix = f"{header}\n\n" if header else ""
    max_tokens = settings.chunk_max_tokens
    overlap_tokens = settings.chunk_overlap_tokens
    max_body_tokens = max(1, max_tokens - counter.count(header_prefix))

    def make_chunk(chunk_blocks: list[Block], index: int) -> Chunk:
        body = "\n\n".join(block.text for block in chunk_blocks).strip()
        full_text = f"{header_prefix}{body}"
        return Chunk(
            chunk_id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{context.project}:{context.version}:{context.path}:{index}",
                )
            ),
            doc_id=context.path,
            path=context.path,
            url=context.url,
            title=context.title,
            heading_path=header,
            section=context.section,
            content_type=_content_type(chunk_blocks),
            language=context.language,
            project=context.project,
            version=context.version,
            chunk_index=index,
            content_hash=hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
            text=full_text,
            token_count=counter.count(full_text),
        )

    full_content = f"{header_prefix}{content}"
    if counter.count(full_content) <= max_tokens:
        return [make_chunk(blocks, start_index)]

    grouped: list[list[Block]] = []
    current: list[Block] = []
    current_tokens = 0

    for block in blocks:
        if block.token_count > max_body_tokens:
            if current:
                grouped.append(current)
                current = []
                current_tokens = 0
            for piece in _split_oversized(block, max_body_tokens, overlap_tokens, counter):
                grouped.append([piece])
            continue

        if current and current_tokens + block.token_count > max_body_tokens:
            grouped.append(current)
            current = _overlap_tail(current, overlap_tokens)
            current_tokens = sum(item.token_count for item in current)
            while current and current_tokens + block.token_count > max_body_tokens:
                removed = current.pop(0)
                current_tokens -= removed.token_count

        current.append(block)
        current_tokens += block.token_count

    if current:
        grouped.append(current)

    return [
        make_chunk(chunk_blocks, start_index + index) for index, chunk_blocks in enumerate(grouped)
    ]


def _split_oversized(
    block: Block,
    max_tokens: int,
    overlap_tokens: int,
    counter: TokenCounter,
) -> list[Block]:
    if block.kind == "code":
        return _split_code_block(block, max_tokens, counter)
    return _split_text_block(block, max_tokens, overlap_tokens, counter)


def _split_code_block(block: Block, max_tokens: int, counter: TokenCounter) -> list[Block]:
    lines = block.text.splitlines()
    if len(lines) < 2:
        return [block]

    opening_match = _FENCE_OPEN_RE.match(lines[0])
    if opening_match is None:
        return [block]

    opening = lines[0]
    fence = opening_match.group(1)
    inner = lines[1:]
    close_match = _FENCE_CLOSE_RE.match(lines[-1])
    if close_match and close_match.group(1)[0] == fence[0]:
        inner = lines[1:-1]

    pieces: list[str] = []
    current: list[str] = []

    for line in inner:
        candidate = "\n".join([opening, *current, line, fence])
        if current and counter.count(candidate) > max_tokens:
            pieces.append("\n".join([opening, *current, fence]))
            current = [line]
        else:
            current.append(line)

    pieces.append("\n".join([opening, *current, fence]))
    return [Block(kind="code", text=piece, token_count=counter.count(piece)) for piece in pieces]


def _split_text_block(
    block: Block,
    max_tokens: int,
    overlap_tokens: int,
    counter: TokenCounter,
) -> list[Block]:
    overlap_limit = min(overlap_tokens, max_tokens // 2)
    words = _WORD_RE.findall(block.text)
    pieces: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for word in words:
        word_tokens = counter.count(word)
        if current and current_tokens + word_tokens > max_tokens:
            pieces.append("".join(current).strip())

            overlap: list[str] = []
            overlap_count = 0
            for previous_word in reversed(current):
                previous_tokens = counter.count(previous_word)
                if overlap_count + previous_tokens > overlap_limit:
                    break
                overlap.insert(0, previous_word)
                overlap_count += previous_tokens

            if overlap_count + word_tokens > max_tokens:
                overlap = []
                overlap_count = 0

            current = overlap
            current_tokens = overlap_count

        current.append(word)
        current_tokens += word_tokens

    if current:
        pieces.append("".join(current).strip())

    return [
        Block(kind=block.kind, text=piece, token_count=counter.count(piece))
        for piece in pieces
        if piece
    ]


def _overlap_tail(blocks: list[Block], overlap_tokens: int) -> list[Block]:
    if overlap_tokens <= 0:
        return []

    tail: list[Block] = []
    total = 0
    for block in reversed(blocks):
        if total + block.token_count > overlap_tokens:
            break
        tail.insert(0, block)
        total += block.token_count
    return tail


def _content_type(blocks: list[Block]) -> ContentType:
    total = sum(block.token_count for block in blocks)
    code_tokens = sum(block.token_count for block in blocks if block.kind == "code")
    if code_tokens == 0:
        return "prose"
    if total > 0 and code_tokens / total >= 0.6:
        return "code"
    return "mixed"


def _classify_block(text: str) -> BlockKind:
    stripped = text.lstrip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return "code"

    lines = [line for line in text.splitlines() if line.strip()]
    if any(line.lstrip().startswith("|") for line in lines):
        return "table"
    if any(_LIST_RE.match(line) for line in lines):
        return "list"
    if lines and all(line.lstrip().startswith(">") for line in lines):
        return "quote"
    if stripped.startswith("<"):
        return "html"
    return "paragraph"
