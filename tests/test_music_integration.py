from __future__ import annotations

import asyncio

from PIL import Image

from daisy_ocr.layout.detect import LayoutRegion
from daisy_ocr.ocr.clova_engine import TextBlock
from daisy_ocr.pipeline import PreparedPage
from daisy_ocr.server import _music_regions, _transcribe_special_regions


def _prepared(page_text: str) -> PreparedPage:
    return PreparedPage(
        ocr_blocks=[TextBlock(page_text, 0.99, (0, 0, 200, 30))],
        regions=[],
        non_text_regions=[
            LayoutRegion("Picture", [10, 50, 190, 140], 0.91),
            LayoutRegion("Picture", [10, 160, 110, 210], 0.82),
        ],
        layout_model="doclaynet",
        conf=0.3,
        imgsz=960,
        ocr_elapsed_ms=1,
        detect_elapsed_ms=1,
    )


def test_music_heading_promotes_only_largest_picture() -> None:
    regions = _music_regions(_prepared("Page 3 - 악보 (Sheet Music)"), {"DetectMusic": True})
    assert [region.label for region in regions] == ["music", "Picture"]


def test_regular_picture_page_is_not_promoted() -> None:
    regions = _music_regions(_prepared("분기별 매출 그래프"), {"DetectMusic": True})
    assert all(region.label == "Picture" for region in regions)


def test_music_failure_stays_as_review_block(monkeypatch, tmp_path) -> None:
    def fail_model(*args, **kwargs):
        raise RuntimeError("Audiveris unavailable")

    monkeypatch.setattr("daisy_ocr.server.recognize_music_region", fail_model)
    image = Image.new("RGB", (220, 240), "white")
    try:
        regions, transcribed = asyncio.run(
            _transcribe_special_regions(
                image,
                _prepared("악보"),
                {"DetectMusic": True, "DetectCharts": True},
                tmp_path,
                2,
            )
        )
    finally:
        image.close()

    assert regions[0].label == "music"
    assert transcribed[0].type == "music"
    assert transcribed[0].error is not None
    assert "Audiveris unavailable" in (transcribed[0].text or "")
