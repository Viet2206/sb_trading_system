from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import sqlite3
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz
import numpy as np

from sb_system.market_data import PROJECT_ROOT
from sb_system.research import _detect_setup_types


DEFAULT_DOCS_DIR = PROJECT_ROOT / "docs" / "chart_template_notes"
DEFAULT_INDEX_PATH = PROJECT_ROOT / "data" / "research" / "chart_images.sqlite3"
DEFAULT_IMAGE_DIR = PROJECT_ROOT / "data" / "research" / "chart_images"
VECTOR_VERSION = "visual-structure-v1"
TARGET_HEIGHT = 128
TARGET_WIDTH = 256


@dataclass(frozen=True)
class ImageMatchSettings:
    docs_dir: Path
    index_path: Path
    image_dir: Path


def load_image_match_settings() -> ImageMatchSettings:
    return ImageMatchSettings(
        docs_dir=_project_path(
            os.getenv(
                "SB_CHART_EXAMPLE_DOCS_DIR",
                "docs/chart_template_notes",
            )
        ),
        index_path=_project_path(
            os.getenv(
                "SB_CHART_IMAGE_INDEX",
                "data/research/chart_images.sqlite3",
            )
        ),
        image_dir=_project_path(
            os.getenv(
                "SB_CHART_IMAGE_DIR",
                "data/research/chart_images",
            )
        ),
    )


class ChartImageIndex:
    def __init__(self, settings: ImageMatchSettings | None = None) -> None:
        self.settings = settings or load_image_match_settings()

    def status(self) -> dict[str, Any]:
        if not self.settings.index_path.exists():
            return self._empty_status()
        try:
            with self._connect(readonly=True) as connection:
                row = connection.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM source_documents) AS documents,
                        (SELECT COUNT(*) FROM chart_images) AS images,
                        (SELECT MAX(indexed_at) FROM source_documents) AS indexed_at
                    """
                ).fetchone()
                metadata = {
                    item["key"]: item["value"]
                    for item in connection.execute("SELECT key, value FROM metadata")
                }
        except sqlite3.DatabaseError:
            return self._empty_status()
        return {
            "ready": bool(row and row["images"]),
            "documents": int(row["documents"] if row else 0),
            "images": int(row["images"] if row else 0),
            "indexed_at": row["indexed_at"] if row else None,
            "vectorizer": metadata.get("vectorizer", VECTOR_VERSION),
            "docs_dir": str(self.settings.docs_dir),
        }

    def build(self, *, rebuild: bool = False) -> dict[str, Any]:
        paths = sorted(self.settings.docs_dir.rglob("*.pdf"))
        self.settings.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.image_dir.mkdir(parents=True, exist_ok=True)
        indexed_documents = 0
        skipped_documents = 0
        indexed_images = 0
        failed: list[dict[str, str]] = []

        with self._connect() as connection:
            self._create_schema(connection)
            metadata = {
                row["key"]: row["value"]
                for row in connection.execute("SELECT key, value FROM metadata")
            }
            if rebuild or metadata.get("vectorizer") != VECTOR_VERSION:
                connection.execute("DELETE FROM chart_images")
                connection.execute("DELETE FROM source_documents")
                connection.commit()
                _remove_generated_images(self.settings.image_dir)

            known = {
                row["path"]: row["sha256"]
                for row in connection.execute(
                    "SELECT path, sha256 FROM source_documents"
                )
            }
            current_paths = {
                path.relative_to(self.settings.docs_dir).as_posix()
                for path in paths
            }
            stale = [
                row["id"]
                for row in connection.execute(
                    "SELECT id, path FROM source_documents"
                )
                if row["path"] not in current_paths
            ]
            for document_id in stale:
                self._delete_document(connection, document_id)

            for path in paths:
                relative = path.relative_to(self.settings.docs_dir).as_posix()
                digest = _file_digest(path)
                if known.get(relative) == digest:
                    skipped_documents += 1
                    continue
                try:
                    count = self._index_document(
                        connection,
                        path=path,
                        relative_path=relative,
                        digest=digest,
                    )
                    connection.commit()
                    indexed_documents += 1
                    indexed_images += count
                except Exception as exc:
                    connection.rollback()
                    failed.append({"path": relative, "error": str(exc)})

            connection.executemany(
                """
                INSERT INTO metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                {
                    "vectorizer": VECTOR_VERSION,
                    "indexed_at": datetime.now(UTC).isoformat(),
                }.items(),
            )
            connection.commit()

        return {
            **self.status(),
            "indexed_documents": indexed_documents,
            "skipped_documents": skipped_documents,
            "indexed_images": indexed_images,
            "removed_documents": len(stale),
            "failed": failed,
        }

    def search_data_url(self, image_data: str, *, limit: int = 5) -> dict[str, Any]:
        image_bytes = decode_image_data(image_data)
        return self.search_bytes(image_bytes, limit=limit)

    def search_bytes(self, image_bytes: bytes, *, limit: int = 5) -> dict[str, Any]:
        if not self.settings.index_path.exists():
            raise RuntimeError("The historical chart image index has not been built.")
        query_vector = vectorize_image_bytes(image_bytes)
        with self._connect(readonly=True) as connection:
            rows = connection.execute(
                """
                SELECT id, document_id, document_title, source_path, page,
                       chart_index, image_path, width, height, setup_types,
                       embedding
                FROM chart_images
                """
            ).fetchall()
        if not rows:
            raise RuntimeError("The historical chart image index is empty.")

        scored = []
        for row in rows:
            vector = _unpack_vector(row["embedding"])
            score = float(np.dot(query_vector, vector))
            scored.append((score, row))
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1]["document_title"],
                item[1]["page"],
                item[1]["chart_index"],
            )
        )

        matches = []
        for rank, (score, row) in enumerate(scored[:limit], start=1):
            matches.append(
                {
                    "rank": rank,
                    "similarity": round(max(-1.0, min(1.0, score)), 4),
                    "similarity_percent": round(
                        max(0.0, min(1.0, score)) * 100
                    ),
                    "example_id": row["id"],
                    "document_id": row["document_id"],
                    "document_title": row["document_title"],
                    "source_path": row["source_path"],
                    "page": int(row["page"]),
                    "chart_index": int(row["chart_index"]),
                    "width": int(row["width"]),
                    "height": int(row["height"]),
                    "setup_types": json.loads(row["setup_types"]),
                }
            )

        return {
            "method": VECTOR_VERSION,
            "count": len(matches),
            "corpus_images": len(rows),
            "matches": matches,
        }

    def image_path(self, example_id: str) -> Path:
        if not self.settings.index_path.exists():
            raise FileNotFoundError(example_id)
        with self._connect(readonly=True) as connection:
            row = connection.execute(
                "SELECT image_path FROM chart_images WHERE id = ?",
                (example_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(example_id)
        path = (self.settings.image_dir / row["image_path"]).resolve()
        root = self.settings.image_dir.resolve()
        if root not in path.parents or not path.is_file():
            raise FileNotFoundError(example_id)
        return path

    def _index_document(
        self,
        connection: sqlite3.Connection,
        *,
        path: Path,
        relative_path: str,
        digest: str,
    ) -> int:
        try:
            research_path = path.relative_to(PROJECT_ROOT / "docs").as_posix()
        except ValueError:
            research_path = relative_path
        document_id = hashlib.sha1(research_path.encode("utf-8")).hexdigest()[:20]
        self._delete_document(connection, document_id)
        title = _title_from_path(relative_path)
        setup_types = _detect_setup_types(f"{title} {relative_path}")
        indexed_at = datetime.now(UTC).isoformat()
        connection.execute(
            """
            INSERT INTO source_documents
                (id, path, title, sha256, indexed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, relative_path, title, digest, indexed_at),
        )

        output_dir = self.settings.image_dir / document_id
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        document = fitz.open(path)
        try:
            for page_number, page in enumerate(document, start=1):
                groups = _chart_groups(page)
                chart_index = 0
                for clip in groups:
                    pixmap = _render_chart(page, clip)
                    if not _looks_like_chart(pixmap):
                        continue
                    chart_index += 1
                    count += 1
                    example_id = hashlib.sha1(
                        f"{document_id}:{page_number}:{chart_index}".encode(
                            "utf-8"
                        )
                    ).hexdigest()[:24]
                    relative_image = (
                        Path(document_id)
                        / f"{page_number:04d}-{chart_index:02d}.jpg"
                    )
                    output = self.settings.image_dir / relative_image
                    pixmap.save(output, jpg_quality=82)
                    embedding = vectorize_pixmap(pixmap)
                    connection.execute(
                        """
                        INSERT INTO chart_images
                            (id, document_id, document_title, source_path,
                             page, chart_index, image_path, width, height,
                             setup_types, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            example_id,
                            document_id,
                            title,
                            research_path,
                            page_number,
                            chart_index,
                            relative_image.as_posix(),
                            pixmap.width,
                            pixmap.height,
                            json.dumps(setup_types),
                            _pack_vector(embedding),
                        ),
                    )
        finally:
            document.close()
        return count

    def _delete_document(
        self, connection: sqlite3.Connection, document_id: str
    ) -> None:
        connection.execute(
            "DELETE FROM chart_images WHERE document_id = ?",
            (document_id,),
        )
        connection.execute(
            "DELETE FROM source_documents WHERE id = ?",
            (document_id,),
        )
        directory = self.settings.image_dir / document_id
        if directory.exists():
            for child in directory.iterdir():
                if child.is_file():
                    child.unlink()
            directory.rmdir()

    def _empty_status(self) -> dict[str, Any]:
        return {
            "ready": False,
            "documents": 0,
            "images": 0,
            "indexed_at": None,
            "vectorizer": VECTOR_VERSION,
            "docs_dir": str(self.settings.docs_dir),
        }

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

            CREATE TABLE IF NOT EXISTS source_documents (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chart_images (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL
                    REFERENCES source_documents(id) ON DELETE CASCADE,
                document_title TEXT NOT NULL,
                source_path TEXT NOT NULL,
                page INTEGER NOT NULL,
                chart_index INTEGER NOT NULL,
                image_path TEXT NOT NULL UNIQUE,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                setup_types TEXT NOT NULL,
                embedding BLOB NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chart_images_document_page
                ON chart_images(document_id, page);
            """
        )


def decode_image_data(image_data: str) -> bytes:
    if not isinstance(image_data, str) or not image_data.strip():
        raise ValueError("Current chart image data is required.")
    encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Current chart image data is invalid.") from exc
    if len(image_bytes) < 100:
        raise ValueError("Current chart image is empty.")
    if len(image_bytes) > 12 * 1024 * 1024:
        raise ValueError("Current chart image is larger than 12 MB.")
    return image_bytes


def vectorize_image_bytes(image_bytes: bytes) -> np.ndarray:
    try:
        pixmap = fitz.Pixmap(image_bytes)
    except Exception as exc:
        raise ValueError("Current chart image could not be decoded.") from exc
    return vectorize_pixmap(pixmap)


def vectorize_pixmap(pixmap: fitz.Pixmap) -> np.ndarray:
    grayscale = _pixmap_grayscale(pixmap)
    normalized = _fit_to_canvas(grayscale, TARGET_HEIGHT, TARGET_WIDTH)
    darkness = np.clip((0.985 - normalized) / 0.985, 0.0, 1.0)

    gradient_y, gradient_x = np.gradient(darkness)
    magnitude = np.hypot(gradient_x, gradient_y)
    orientation = (np.arctan2(gradient_y, gradient_x) + math.pi) % math.pi

    structure = _resize_nearest(darkness, 32, 64)
    edges = _resize_nearest(magnitude, 16, 32)
    horizontal_projection = darkness.mean(axis=1)
    vertical_projection = darkness.mean(axis=0)
    hog = _orientation_histograms(magnitude, orientation, 8, 16)

    blocks = [
        _standardize(structure.ravel()),
        _standardize(edges.ravel()),
        _standardize(horizontal_projection),
        _standardize(vertical_projection),
        hog,
    ]
    vector = np.concatenate(blocks).astype(np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _chart_groups(page: fitz.Page) -> list[fitz.Rect]:
    rectangles = [
        fitz.Rect(info["bbox"])
        for info in page.get_image_info(xrefs=True)
        if info.get("xref") and fitz.Rect(info["bbox"]).get_area() > 100
    ]
    groups: list[fitz.Rect] = []
    for rectangle in rectangles:
        merged = False
        for index, group in enumerate(groups):
            if _rectangles_connect(group, rectangle, page.rect):
                groups[index] = group | rectangle
                merged = True
                break
        if not merged:
            groups.append(rectangle)

    changed = True
    while changed:
        changed = False
        combined: list[fitz.Rect] = []
        for rectangle in groups:
            for index, group in enumerate(combined):
                if _rectangles_connect(group, rectangle, page.rect):
                    combined[index] = group | rectangle
                    changed = True
                    break
            else:
                combined.append(rectangle)
        groups = combined

    return sorted(groups, key=lambda rect: (rect.y0, rect.x0))


def _rectangles_connect(
    first: fitz.Rect, second: fitz.Rect, page: fitz.Rect
) -> bool:
    overlap_x = max(
        0.0,
        min(first.x1, second.x1) - max(first.x0, second.x0),
    )
    overlap_y = max(
        0.0,
        min(first.y1, second.y1) - max(first.y0, second.y0),
    )
    gap_x = max(0.0, max(first.x0, second.x0) - min(first.x1, second.x1))
    gap_y = max(0.0, max(first.y0, second.y0) - min(first.y1, second.y1))
    horizontal_pair = (
        overlap_y >= min(first.height, second.height) * 0.5
        and gap_x <= page.width * 0.015
    )
    vertical_pair = (
        overlap_x >= min(first.width, second.width) * 0.5
        and gap_y <= page.height * 0.015
    )
    return horizontal_pair or vertical_pair


def _render_chart(page: fitz.Page, clip: fitz.Rect) -> fitz.Pixmap:
    clip = clip & page.rect
    scale = max(1.0, min(2.4, 1400 / max(1.0, clip.width)))
    return page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        clip=clip,
        alpha=False,
    )


def _looks_like_chart(pixmap: fitz.Pixmap) -> bool:
    if pixmap.width < 420 or pixmap.height < 150:
        return False
    aspect = pixmap.width / max(1, pixmap.height)
    if aspect < 1.25 or aspect > 6:
        return False
    grayscale = _pixmap_grayscale(pixmap)
    dark_ratio = float((grayscale < 0.86).mean())
    return 0.012 <= dark_ratio <= 0.28


def _pixmap_grayscale(pixmap: fitz.Pixmap) -> np.ndarray:
    samples = np.frombuffer(pixmap.samples, dtype=np.uint8)
    channels = pixmap.n
    image = samples.reshape(pixmap.height, pixmap.width, channels)
    if channels == 1:
        return image[:, :, 0].astype(np.float32) / 255.0
    rgb = image[:, :, :3].astype(np.float32) / 255.0
    return (
        rgb[:, :, 0] * 0.299
        + rgb[:, :, 1] * 0.587
        + rgb[:, :, 2] * 0.114
    )


def _fit_to_canvas(
    image: np.ndarray, target_height: int, target_width: int
) -> np.ndarray:
    margin_y = max(1, round(image.shape[0] * 0.01))
    margin_x = max(1, round(image.shape[1] * 0.01))
    trimmed = image[
        margin_y : image.shape[0] - margin_y,
        margin_x : image.shape[1] - margin_x,
    ]
    scale = min(
        target_height / max(1, trimmed.shape[0]),
        target_width / max(1, trimmed.shape[1]),
    )
    resized_height = max(1, round(trimmed.shape[0] * scale))
    resized_width = max(1, round(trimmed.shape[1] * scale))
    resized = _resize_nearest(trimmed, resized_height, resized_width)
    canvas = np.ones((target_height, target_width), dtype=np.float32)
    top = (target_height - resized_height) // 2
    left = (target_width - resized_width) // 2
    canvas[top : top + resized_height, left : left + resized_width] = resized
    return canvas


def _resize_nearest(
    image: np.ndarray, target_height: int, target_width: int
) -> np.ndarray:
    rows = np.linspace(0, image.shape[0] - 1, target_height).astype(int)
    columns = np.linspace(0, image.shape[1] - 1, target_width).astype(int)
    return image[np.ix_(rows, columns)]


def _orientation_histograms(
    magnitude: np.ndarray,
    orientation: np.ndarray,
    cells_y: int,
    cells_x: int,
) -> np.ndarray:
    histograms = []
    row_edges = np.linspace(0, magnitude.shape[0], cells_y + 1).astype(int)
    column_edges = np.linspace(0, magnitude.shape[1], cells_x + 1).astype(int)
    bins = np.linspace(0, math.pi, 5)
    for row in range(cells_y):
        for column in range(cells_x):
            weights = magnitude[
                row_edges[row] : row_edges[row + 1],
                column_edges[column] : column_edges[column + 1],
            ].ravel()
            angles = orientation[
                row_edges[row] : row_edges[row + 1],
                column_edges[column] : column_edges[column + 1],
            ].ravel()
            histogram, _ = np.histogram(angles, bins=bins, weights=weights)
            norm = float(np.linalg.norm(histogram))
            histograms.extend(histogram / norm if norm else histogram)
    return np.asarray(histograms, dtype=np.float32)


def _standardize(values: np.ndarray) -> np.ndarray:
    standard_deviation = float(values.std())
    if standard_deviation < 1e-8:
        return values.astype(np.float32)
    return ((values - values.mean()) / standard_deviation).astype(np.float32)


def _pack_vector(vector: np.ndarray) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack_vector(payload: bytes) -> np.ndarray:
    vector = np.frombuffer(payload, dtype="<f4")
    return vector.astype(np.float32, copy=False)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _title_from_path(path: str) -> str:
    return Path(path).stem.replace("_", " ").strip()


def _project_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _remove_generated_images(directory: Path) -> None:
    if not directory.exists():
        return
    for path in sorted(directory.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
