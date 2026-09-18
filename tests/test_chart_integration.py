import asyncio
import json
import io
import zipfile

import pytest
from PIL import Image

from ai_engine.chart_analyzer import ChartAnalyzer
from daisy_ocr.chart.adapter import format_chart_result, _worker_environment
from daisy_ocr.layout.detect import LayoutRegion
from daisy_ocr.ocr.clova_engine import TextBlock
from daisy_ocr.pipeline import PreparedPage, merge_page
from daisy_ocr.output.package import PagePackage, build_result_package
from daisy_ocr.server import _transcribe_special_regions


def test_cpu_layout_setting_does_not_disable_chart_gpu(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "-1")
    monkeypatch.delenv("CHART_CUDA_VISIBLE_DEVICES", raising=False)
    assert _worker_environment()["CUDA_VISIBLE_DEVICES"] == "0"
    monkeypatch.setenv("CHART_CUDA_VISIBLE_DEVICES", "2")
    assert _worker_environment()["CUDA_VISIBLE_DEVICES"] == "2"


def test_team_parser_does_not_mix_fields_or_accept_extra_numbers():
    analyzer = ChartAnalyzer(None, None, pre_cropped=True)
    source = "graph_type: bar\ntitle: Sales\naxis:\n- x_axis: Quarter\n- y_axis: Units\nlegend: none\ndata: 10, 20, 30\ndescription: 10 to 20 to 30"
    score, data = analyzer._auto_validate(source)
    assert data["graph_type"] == "bar"
    assert data["title"] == "Sales"
    assert data["axis"] == "- x_axis: Quarter\n- y_axis: Units"
    assert data["data"] == "10, 20, 30"
    assert score == pytest.approx(1)
    bad_score, _ = analyzer._auto_validate(source + ", 999")
    assert bad_score < score


@pytest.mark.parametrize("fail", [False, True])
def test_chart_routes_crop_preserves_coordinates_and_review(monkeypatch, tmp_path, fail):
    monkeypatch.setenv("CHART_RECOGNITION_ENABLED", "true")
    calls = []
    def recognize(image, *args, **kwargs):
        calls.append(image.size)
        if fail:
            raise RuntimeError("test GPU unavailable")
        return "데이터: 10, 20, 30\n설명: 증가합니다.", 0.95
    monkeypatch.setattr("daisy_ocr.server.recognize_chart_region", recognize)
    region = LayoutRegion("Table", [10, 20, 110, 80], 0.9)
    page = PreparedPage(
        ocr_blocks=[TextBlock("원문 10", 0.99, (20, 30, 50, 45))],
        regions=[region], non_text_regions=[region], layout_model="doclaynet",
        conf=0.3, imgsz=960, ocr_elapsed_ms=0, detect_elapsed_ms=0,
    )
    with Image.new("RGB", (200, 100), "white") as image:
        regions, texts = asyncio.run(_transcribe_special_regions(image, page, {}, tmp_path / "music", 0))
    assert calls == [(100, 60)]
    assert texts[0].bbox == (10, 20, 110, 80)
    assert texts[0].type == "table"
    if fail:
        assert "원문 10" in texts[0].text
        assert "test GPU unavailable" in texts[0].error
    else:
        assert "10, 20, 30" in texts[0].text
    elements = merge_page(page.ocr_blocks, regions, texts)
    package = build_result_package("test", "test", [PagePackage(0, 200, 100, 200, elements)])
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        review = json.loads(archive.read("review.json"))
        assert next(iter(review["elements"].values()))["review_status"] == "needs_review"


@pytest.mark.parametrize("response", [{}, {"results": []}, {"results": [{"parsed_data": {}}]}])
def test_invalid_chart_responses_fail_explicitly(response):
    with pytest.raises(ValueError):
        format_chart_result(response)
