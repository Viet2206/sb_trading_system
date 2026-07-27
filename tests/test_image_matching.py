from __future__ import annotations

import base64
from pathlib import Path

import fitz
import numpy as np
import pytest

from sb_system.image_matching import (
    ChartImageIndex,
    ImageMatchSettings,
    decode_image_data,
    vectorize_image_bytes,
)


def _chart_bytes(*, inverted: bool = False) -> bytes:
    height, width = 360, 720
    pixels = np.full((height, width, 3), 255, dtype=np.uint8)
    x_values = np.arange(20, width - 20)
    baseline = height // 2
    prices = baseline + (
        72 * np.sin(x_values / 49.0) + 26 * np.sin(x_values / 13.0)
    ).astype(int)
    if inverted:
        prices = height - prices
    for x, y in zip(x_values, prices, strict=True):
        pixels[max(0, y - 2) : min(height, y + 3), x] = 20
    for x in range(40, width, 90):
        pixels[15 : height - 15, x] = 222
    pixmap = fitz.Pixmap(
        fitz.csRGB,
        width,
        height,
        pixels.tobytes(),
        False,
    )
    return pixmap.tobytes("png")


def _write_chart_pdf(path: Path, image_bytes: bytes) -> None:
    document = fitz.open()
    page = document.new_page(width=720, height=360)
    page.insert_image(page.rect, stream=image_bytes)
    document.save(path)
    document.close()


def test_decode_image_data_and_vector_similarity() -> None:
    chart = _chart_bytes()
    data_url = "data:image/png;base64," + base64.b64encode(chart).decode("ascii")

    assert decode_image_data(data_url) == chart
    vector = vectorize_image_bytes(chart)
    inverted = vectorize_image_bytes(_chart_bytes(inverted=True))

    assert np.isclose(np.linalg.norm(vector), 1.0)
    assert float(np.dot(vector, vector)) > 0.999
    assert float(np.dot(vector, inverted)) < 0.99


def test_decode_image_data_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="invalid"):
        decode_image_data("not-base64")


def test_build_and_search_chart_image_index(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    chart = _chart_bytes()
    _write_chart_pdf(docs_dir / "FirstRedDayExample.pdf", chart)
    index = ChartImageIndex(
        ImageMatchSettings(
            docs_dir=docs_dir,
            index_path=tmp_path / "chart-images.sqlite3",
            image_dir=tmp_path / "images",
        )
    )

    build = index.build(rebuild=True)
    result = index.search_bytes(chart, limit=5)

    assert build["documents"] == 1
    assert build["images"] == 1
    assert result["method"] == "visual-structure-v1"
    assert result["count"] == 1
    assert result["matches"][0]["rank"] == 1
    assert result["matches"][0]["similarity"] > 0.9
    assert index.image_path(result["matches"][0]["example_id"]).is_file()
