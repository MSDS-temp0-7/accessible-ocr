from __future__ import annotations

import asyncio

from PIL import Image

from daisy_ocr.layout.detect import LayoutRegion
from daisy_ocr.music.adapter import MusicRecognitionResult
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
    monkeypatch.setenv("CHART_RECOGNITION_ENABLED", "false")
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
    assert "설정" in (transcribed[0].text or "")


def test_music_no_system_retries_with_wider_page_context(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CHART_RECOGNITION_ENABLED", "false")
    crop_sizes = []

    def recognize(image, *args, **kwargs):
        crop_sizes.append(image.size)
        if len(crop_sizes) == 1:
            raise RuntimeError("Audiveris failed: No system found")
        return MusicRecognitionResult(
            text="악보 요약 성공",
            confidence=0.88,
            needs_review=False,
            music_xml="<score-partwise/>",
            raw={},
        )

    monkeypatch.setattr("daisy_ocr.server.recognize_music_region", recognize)
    image = Image.new("RGB", (220, 240), "white")
    try:
        _, transcribed = asyncio.run(
            _transcribe_special_regions(
                image,
                _prepared("악보"),
                {"DetectMusic": True},
                tmp_path,
                2,
            )
        )
    finally:
        image.close()

    assert len(crop_sizes) == 2
    assert crop_sizes[0][0] > 180
    assert crop_sizes[0][1] > 90
    assert crop_sizes[1][0] == 220
    assert crop_sizes[1][1] > crop_sizes[0][1]
    assert transcribed[0].text == "악보 요약 성공"
    assert transcribed[0].error is None


def test_music_no_system_reports_recognition_failure_not_setup(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CHART_RECOGNITION_ENABLED", "false")

    def fail_model(*args, **kwargs):
        raise RuntimeError("No system found")

    monkeypatch.setattr("daisy_ocr.server.recognize_music_region", fail_model)
    image = Image.new("RGB", (220, 240), "white")
    try:
        _, transcribed = asyncio.run(
            _transcribe_special_regions(
                image,
                _prepared("악보"),
                {"DetectMusic": True},
                tmp_path,
                2,
            )
        )
    finally:
        image.close()

    assert "Audiveris는 실행됐지만" in (transcribed[0].text or "")
    assert "완전한 악보 시스템" in (transcribed[0].text or "")


def test_rules_summary_never_calls_ollama(monkeypatch):
    from daisy_ocr.music.adapter import _load_services
    _load_services()
    from services import local_llm_summarizer as summarizer
    monkeypatch.setenv("MUSIC_SUMMARY_MODE", "rules")
    def unexpected(*args, **kwargs):
        raise AssertionError("Rules mode must not contact Ollama")
    monkeypatch.setattr(summarizer, "call_local_llm", unexpected)
    result = summarizer.select_optional_fact_ids([
        {"id": "low", "priority": 1}, {"id": "high", "priority": 3}, {"id": "mid", "priority": 2}
    ], 2)
    assert result["selectedIds"] == ["high", "mid"]
    assert result["selectedBy"] == "deterministic_rules"
    assert result["issues"] == []
    assert not result["fallbackUsed"]


def test_qwen3_request_uses_json_without_thinking_and_unloads(monkeypatch):
    from daisy_ocr.music.adapter import _load_services
    _load_services()
    from services import local_llm_summarizer as summarizer

    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "{}"}}

    def fake_post(url, json, timeout):
        captured.update({"url": url, "payload": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr(summarizer, "LOCAL_LLM_MODEL", "qwen3:14b")
    monkeypatch.setattr(summarizer, "LOCAL_LLM_THINK", False)
    monkeypatch.setattr(summarizer, "LOCAL_LLM_KEEP_ALIVE", "0")
    monkeypatch.setattr(summarizer.requests, "post", fake_post)

    assert summarizer.call_local_llm("system", "user") == "{}"
    assert captured["payload"]["model"] == "qwen3:14b"
    assert captured["payload"]["format"] == "json"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["keep_alive"] == "0"
