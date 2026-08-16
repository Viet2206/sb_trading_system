from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import struct
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from sb_system.market_data import PROJECT_ROOT


DEFAULT_INDEX_PATH = PROJECT_ROOT / "data" / "research" / "research.sqlite3"
DEFAULT_DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_PAGE_CACHE = PROJECT_ROOT / "data" / "research" / "pages"
LOCAL_VECTOR_DIMENSIONS = 384
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")

SETUP_TAXONOMY: dict[str, tuple[str, ...]] = {
    "first-green-day": ("first green day", "fgd", "first day green"),
    "first-red-day": ("first red day", "frd", "first day red"),
    "inside-day": ("inside day", "inside-day", " id "),
    "three-day-long": ("three day long", "3dl", "day 3 long"),
    "three-day-short": ("three day short", "3ds", "day 3 short"),
    "closing-inside-breakout": (
        "close in breakout",
        "closing breakout",
        "closing inside breakout",
        "cib",
        "2cib",
    ),
    "pump-and-dump": ("pump and dump", "pump dump", "pnd"),
    "parabolic": ("parabolic", "short squeeze", "blowoff"),
    "opening-range": ("opening range", "monday opening range"),
    "hod-lod": ("hod", "lod", "high of day", "low of day"),
    "three-session": ("three session", "3 session"),
    "low-hanging-fruit": ("low hanging fruit", "lhf"),
    "major-news": ("major news", "first bounce", "equity open"),
}

QUERY_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "fgd": ("first green day", "dump day", "buy setup"),
    "frd": ("first red day", "pump day", "sell setup"),
    "3dl": ("three day long", "day 3", "reversal"),
    "3ds": ("three day short", "day 3", "reversal"),
    "cib": ("close in breakout", "closing breakout", "breakout close"),
    "2cib": ("two close in breakout", "consecutive breakout closes"),
    "hod": ("high of day", "stop hunt"),
    "lod": ("low of day", "stop hunt"),
    "lhf": ("low hanging fruit",),
}


@dataclass(frozen=True)
class ResearchSettings:
    docs_dir: Path
    index_path: Path
    page_cache_dir: Path
    embedding_provider: str
    embedding_model: str


def load_research_settings() -> ResearchSettings:
    provider = os.getenv("SB_EMBEDDING_PROVIDER", "local").strip().lower()
    if provider not in {"local", "openai"}:
        provider = "local"
    return ResearchSettings(
        docs_dir=_resolve_project_path(os.getenv("SB_RESEARCH_DOCS_DIR", "docs")),
        index_path=_resolve_project_path(
            os.getenv("SB_RESEARCH_INDEX", "data/research/research.sqlite3")
        ),
        page_cache_dir=_resolve_project_path(
            os.getenv("SB_RESEARCH_PAGE_CACHE", "data/research/pages")
        ),
        embedding_provider=provider,
        embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        ).strip(),
    )


class ResearchLibrary:
    def __init__(self, settings: ResearchSettings | None = None) -> None:
        self.settings = settings or load_research_settings()

    def status(self) -> dict[str, Any]:
        if not self.settings.index_path.exists():
            return {
                "ready": False,
                "documents": 0,
                "pages": 0,
                "chunks": 0,
                "indexed_at": None,
                "embedding_provider": self.settings.embedding_provider,
                "embedding_model": self._embedding_model_name(),
                "docs_dir": str(self.settings.docs_dir),
            }
        try:
            with self._connect(readonly=True) as connection:
                row = connection.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM documents) AS documents,
                        (SELECT COALESCE(SUM(pages), 0) FROM documents) AS pages,
                        (SELECT COUNT(*) FROM chunks) AS chunks,
                        (SELECT MAX(indexed_at) FROM documents) AS indexed_at
                    """
                ).fetchone()
                metadata = self._metadata(connection)
        except sqlite3.DatabaseError:
            return {
                "ready": False,
                "documents": 0,
                "pages": 0,
                "chunks": 0,
                "indexed_at": None,
                "embedding_provider": self.settings.embedding_provider,
                "embedding_model": self._embedding_model_name(),
                "docs_dir": str(self.settings.docs_dir),
            }
        return {
            "ready": bool(row and row["documents"]),
            "documents": int(row["documents"] if row else 0),
            "pages": int(row["pages"] if row else 0),
            "chunks": int(row["chunks"] if row else 0),
            "indexed_at": row["indexed_at"] if row else None,
            "embedding_provider": metadata.get(
                "embedding_provider", self.settings.embedding_provider
            ),
            "embedding_model": metadata.get(
                "embedding_model", self._embedding_model_name()
            ),
            "docs_dir": str(self.settings.docs_dir),
        }

    def index_documents(self, *, rebuild: bool = False) -> dict[str, Any]:
        from pypdf import PdfReader

        paths = sorted(self.settings.docs_dir.rglob("*.pdf"))
        self.settings.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)
            metadata = self._metadata(connection)
            provider_changed = bool(metadata) and (
                metadata.get("embedding_provider") != self.settings.embedding_provider
                or metadata.get("embedding_model") != self._embedding_model_name()
            )
            rebuild = rebuild or provider_changed
            if rebuild:
                connection.execute("DELETE FROM chunks_fts")
                connection.execute("DELETE FROM chunks")
                connection.execute("DELETE FROM documents")
                connection.commit()

            known = {
                row["path"]: row["sha256"]
                for row in connection.execute("SELECT path, sha256 FROM documents")
            }
            indexed = 0
            skipped = 0
            failed: list[dict[str, str]] = []
            for path in paths:
                relative_path = path.relative_to(self.settings.docs_dir).as_posix()
                digest = _file_digest(path)
                if known.get(relative_path) == digest:
                    skipped += 1
                    continue
                try:
                    reader = PdfReader(str(path))
                    pages = [
                        _normalize_text(page.extract_text() or "")
                        for page in reader.pages
                    ]
                    self._replace_document(
                        connection,
                        path=relative_path,
                        digest=digest,
                        pages=pages,
                    )
                    connection.commit()
                    indexed += 1
                except Exception as exc:
                    connection.rollback()
                    failed.append({"path": relative_path, "error": str(exc)})

            existing_paths = {path.relative_to(self.settings.docs_dir).as_posix() for path in paths}
            stale = [
                row["id"]
                for row in connection.execute("SELECT id, path FROM documents")
                if row["path"] not in existing_paths
            ]
            for document_id in stale:
                self._delete_document(connection, document_id)

            self._set_metadata(
                connection,
                {
                    "embedding_provider": self.settings.embedding_provider,
                    "embedding_model": self._embedding_model_name(),
                    "indexed_at": datetime.now(UTC).isoformat(),
                },
            )
            connection.commit()

        return {
            **self.status(),
            "indexed": indexed,
            "skipped": skipped,
            "removed": len(stale),
            "failed": failed,
        }

    def documents(
        self, *, category: str | None = None, setup: str | None = None
    ) -> list[dict[str, Any]]:
        if not self.settings.index_path.exists():
            return []
        clauses: list[str] = []
        parameters: list[Any] = []
        if category:
            clauses.append("category = ?")
            parameters.append(category)
        if setup:
            clauses.append("setup_types LIKE ?")
            parameters.append(f'%"{setup}"%')
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect(readonly=True) as connection:
            rows = connection.execute(
                f"""
                SELECT id, path, title, category, pages, setup_types, indexed_at
                FROM documents
                {where}
                ORDER BY category, title
                """,
                parameters,
            ).fetchall()
        return [
            {
                "id": row["id"],
                "path": row["path"],
                "title": row["title"],
                "category": row["category"],
                "pages": row["pages"],
                "setup_types": json.loads(row["setup_types"]),
                "indexed_at": row["indexed_at"],
            }
            for row in rows
        ]

    def search(
        self,
        query: str,
        *,
        setup: str | None = None,
        category: str | None = None,
        limit: int = 12,
    ) -> dict[str, Any]:
        clean_query = _normalize_text(query)
        if not clean_query:
            raise ValueError("Search query is required.")
        if not self.settings.index_path.exists():
            return {"query": clean_query, "count": 0, "results": []}

        expanded_query = _expand_query(clean_query)
        query_vector = self._embed_texts([expanded_query])[0]
        detected_query_setups = set(_detect_setup_types(clean_query))
        matched_aliases = [
            alias
            for setup_name in detected_query_setups
            for alias in SETUP_TAXONOMY[setup_name]
            if alias.strip() in clean_query.lower()
        ]
        with self._connect(readonly=True) as connection:
            candidates = self._candidate_rows(
                connection,
                expanded_query,
                setup=setup,
                category=category,
            )

        scored = []
        query_terms = set(_tokens(expanded_query))
        for row in candidates:
            vector = _unpack_vector(row["embedding"])
            vector_score = max(0.0, _cosine(query_vector, vector))
            lexical_score = _term_overlap(query_terms, row["search_text"])
            row_setups = set(json.loads(row["setup_types"]))
            setup_score = 1.0 if (
                (setup and setup in row_setups)
                or (detected_query_setups & row_setups)
            ) else 0.0
            phrase_score = 1.0 if any(
                alias.strip() in row["search_text"] for alias in matched_aliases
            ) else 0.0
            substantive_score = min(1.0, len(_tokens(row["content"])) / 120)
            score = min(
                1.0,
                (vector_score * 0.42)
                + (lexical_score * 0.28)
                + (setup_score * 0.08)
                + (phrase_score * 0.12)
                + (substantive_score * 0.10),
            )
            if score <= 0:
                continue
            scored.append((score, row))

        scored.sort(key=lambda item: (-item[0], item[1]["title"], item[1]["page"]))
        results = [
            self._result_payload(row, score, index + 1)
            for index, (score, row) in enumerate(scored[:limit])
        ]
        return {"query": clean_query, "count": len(results), "results": results}

    def document_path(self, document_id: str) -> Path:
        row = self._document_row(document_id)
        path = (self.settings.docs_dir / row["path"]).resolve()
        docs_root = self.settings.docs_dir.resolve()
        if docs_root not in path.parents or not path.is_file():
            raise FileNotFoundError(document_id)
        return path

    def document_page_count(self, document_id: str) -> int:
        return int(self._document_row(document_id)["pages"])

    def render_page(self, document_id: str, page: int, *, width: int = 1200) -> Path:
        if page < 1 or page > self.document_page_count(document_id):
            raise ValueError("Page number is outside the document.")
        output = self.settings.page_cache_dir / document_id / f"{page}-{width}.png"
        if output.exists():
            return output

        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to render PDF pages.") from exc

        output.parent.mkdir(parents=True, exist_ok=True)
        document = fitz.open(self.document_path(document_id))
        try:
            source_page = document.load_page(page - 1)
            scale = max(1.0, width / max(1.0, source_page.rect.width))
            pixmap = source_page.get_pixmap(
                matrix=fitz.Matrix(scale, scale), alpha=False
            )
            pixmap.save(output)
        finally:
            document.close()
        return output

    def _replace_document(
        self,
        connection: sqlite3.Connection,
        *,
        path: str,
        digest: str,
        pages: Sequence[str],
    ) -> None:
        document_id = hashlib.sha1(path.encode("utf-8")).hexdigest()[:20]
        self._delete_document(connection, document_id)
        title = _title_from_path(path)
        category = Path(path).parent.name.replace("_", " ").title()
        source_text = f"{title} {path} {' '.join(pages[:3])}".lower()
        setup_types = _detect_setup_types(source_text)
        now = datetime.now(UTC).isoformat()
        connection.execute(
            """
            INSERT INTO documents
                (id, path, title, category, sha256, pages, setup_types, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                path,
                title,
                category,
                digest,
                len(pages),
                json.dumps(setup_types),
                now,
            ),
        )

        records: list[dict[str, Any]] = []
        for page_number, page_text in enumerate(pages, start=1):
            content = page_text or (
                f"Chart example page from {title}. "
                f"Source category: {category}. "
                f"Document tags: {' '.join(setup_types) or 'Stacey Burke trade setup'}."
            )
            for chunk_index, chunk in enumerate(_chunk_text(content)):
                chunk_setup_types = sorted(
                    set(setup_types + _detect_setup_types(chunk))
                )
                records.append(
                    {
                        "id": hashlib.sha1(
                            f"{document_id}:{page_number}:{chunk_index}".encode("utf-8")
                        ).hexdigest()[:24],
                        "document_id": document_id,
                        "page": page_number,
                        "chunk_index": chunk_index,
                        "content": chunk,
                        "setup_types": chunk_setup_types,
                        "search_text": _search_text(
                            title, category, chunk_setup_types, chunk
                        ),
                    }
                )

        embeddings = self._embed_texts([record["search_text"] for record in records])
        for record, embedding in zip(records, embeddings, strict=True):
            connection.execute(
                """
                INSERT INTO chunks
                    (id, document_id, page, chunk_index, content, setup_types,
                     search_text, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["document_id"],
                    record["page"],
                    record["chunk_index"],
                    record["content"],
                    json.dumps(record["setup_types"]),
                    record["search_text"],
                    _pack_vector(embedding),
                ),
            )
            connection.execute(
                """
                INSERT INTO chunks_fts
                    (chunk_id, document_id, title, category, setup_types, content)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    document_id,
                    title,
                    category,
                    " ".join(record["setup_types"]),
                    record["content"],
                ),
            )

    def _candidate_rows(
        self,
        connection: sqlite3.Connection,
        query: str,
        *,
        setup: str | None,
        category: str | None,
    ) -> list[sqlite3.Row]:
        clauses = []
        parameters: list[Any] = []
        if setup:
            clauses.append("c.setup_types LIKE ?")
            parameters.append(f'%"{setup}"%')
        if category:
            clauses.append("d.category = ?")
            parameters.append(category)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"""
            SELECT c.id, c.document_id, c.page, c.content, c.setup_types,
                   c.search_text, c.embedding, d.title, d.category
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            {where}
            """,
            parameters,
        ).fetchall()

        terms = set(_tokens(query))
        if not terms:
            return rows
        ranked = sorted(
            rows,
            key=lambda row: _term_overlap(terms, row["search_text"]),
            reverse=True,
        )
        return ranked[:1200]

    def _result_payload(
        self, row: sqlite3.Row, score: float, citation_index: int
    ) -> dict[str, Any]:
        content = row["content"].strip()
        excerpt = content if len(content) <= 620 else f"{content[:617].rstrip()}..."
        return {
            "citation": f"S{citation_index}",
            "score": round(score, 4),
            "document_id": row["document_id"],
            "document_title": row["title"],
            "category": row["category"],
            "page": int(row["page"]),
            "setup_types": json.loads(row["setup_types"]),
            "excerpt": excerpt,
            "visual_only": content.startswith("Chart example page from "),
        }

    def _document_row(self, document_id: str) -> sqlite3.Row:
        if not self.settings.index_path.exists():
            raise FileNotFoundError(document_id)
        with self._connect(readonly=True) as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        if row is None:
            raise FileNotFoundError(document_id)
        return row

    def _delete_document(
        self, connection: sqlite3.Connection, document_id: str
    ) -> None:
        chunk_ids = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
            )
        ]
        for chunk_id in chunk_ids:
            connection.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))
        connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    def _embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.settings.embedding_provider == "openai":
            if not os.getenv("OPENAI_API_KEY", "").strip():
                raise RuntimeError(
                    "OPENAI_API_KEY is required when SB_EMBEDDING_PROVIDER=openai."
                )
            from openai import OpenAI

            client = OpenAI(timeout=60.0, max_retries=2)
            embeddings: list[list[float]] = []
            for start in range(0, len(texts), 100):
                batch = list(texts[start : start + 100])
                response = client.embeddings.create(
                    model=self.settings.embedding_model,
                    input=batch,
                    encoding_format="float",
                )
                embeddings.extend(
                    [list(item.embedding) for item in sorted(response.data, key=lambda x: x.index)]
                )
            return embeddings
        return [_local_embedding(text) for text in texts]

    def _embedding_model_name(self) -> str:
        if self.settings.embedding_provider == "openai":
            return self.settings.embedding_model
        return f"local-feature-hash-{LOCAL_VECTOR_DIMENSIONS}"

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        if readonly:
            uri = f"{self.settings.index_path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True)
        else:
            connection = sqlite3.connect(self.settings.index_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                pages INTEGER NOT NULL,
                setup_types TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                setup_types TEXT NOT NULL,
                search_text TEXT NOT NULL,
                embedding BLOB NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document_page
                ON chunks(document_id, page);

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                title,
                category,
                setup_types,
                content
            );
            """
        )

    @staticmethod
    def _metadata(connection: sqlite3.Connection) -> dict[str, str]:
        return {
            row["key"]: row["value"]
            for row in connection.execute("SELECT key, value FROM metadata")
        }

    @staticmethod
    def _set_metadata(
        connection: sqlite3.Connection, values: dict[str, str]
    ) -> None:
        connection.executemany(
            """
            INSERT INTO metadata (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            values.items(),
        )


def _resolve_project_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _title_from_path(path: str) -> str:
    title = Path(path).stem.replace("_", " ")
    title = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _detect_setup_types(text: str) -> list[str]:
    haystack = f" {text.lower()} "
    return [
        setup
        for setup, aliases in SETUP_TAXONOMY.items()
        if any(alias in haystack for alias in aliases)
    ]


def _chunk_text(
    text: str, *, target_words: int = 210, overlap_words: int = 35
) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(len(words), start + target_words)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(start + 1, end - overlap_words)
    return chunks


def _search_text(
    title: str, category: str, setup_types: Iterable[str], content: str
) -> str:
    return _normalize_text(
        f"{title}\n{category}\n{' '.join(setup_types)}\n{content}"
    ).lower()


def _expand_query(query: str) -> str:
    lower = query.lower()
    additions = []
    for key, values in QUERY_EXPANSIONS.items():
        if key in lower:
            additions.extend(values)
    detected = _detect_setup_types(lower)
    for setup in detected:
        additions.extend(SETUP_TAXONOMY[setup])
    return _normalize_text(" ".join([query, *additions]))


def _local_embedding(text: str) -> list[float]:
    tokens = _tokens(text)
    features = tokens + [
        f"{tokens[index]}_{tokens[index + 1]}" for index in range(len(tokens) - 1)
    ]
    counts = Counter(features)
    vector = [0.0] * LOCAL_VECTOR_DIMENSIONS
    for feature, count in counts.items():
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "little")
        index = value % LOCAL_VECTOR_DIMENSIONS
        sign = -1.0 if value & (1 << 63) else 1.0
        vector[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def _pack_vector(vector: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack_vector(payload: bytes) -> list[float]:
    if not payload:
        return []
    dimensions = len(payload) // 4
    return list(struct.unpack(f"<{dimensions}f", payload))


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def _term_overlap(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    text_terms = set(_tokens(text))
    return len(query_terms & text_terms) / len(query_terms)
