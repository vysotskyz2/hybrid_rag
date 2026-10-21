from dataclasses import asdict, dataclass
from typing import Literal

ContentType = Literal["prose", "code", "mixed"]
BlockKind = Literal["paragraph", "list", "table", "quote", "code", "html"]


@dataclass(frozen=True, slots=True)
class Section:
    level: int
    title: str
    heading_path: tuple[str, ...]
    content: str


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    title: str | None
    sections: tuple[Section, ...]


@dataclass(frozen=True, slots=True)
class Block:
    kind: BlockKind
    text: str
    token_count: int


@dataclass(frozen=True, slots=True)
class DocFile:
    relative_path: str
    text: str
    url: str
    title: str
    section: str


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    doc_id: str
    path: str
    url: str
    title: str
    heading_path: str
    section: str
    content_type: ContentType
    language: str
    project: str
    version: str
    chunk_index: int
    content_hash: str
    text: str
    token_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
