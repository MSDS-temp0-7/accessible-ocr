import io
import json
import zipfile
from xml.etree import ElementTree as ET

from daisy_ocr.output.package import PagePackage, build_result_package
from daisy_ocr.pipeline import PageElement
from daisy_ocr.server import _decode_upload_filename, _selected_page_indexes


def test_result_package_contains_wpf_contract_files() -> None:
    pages = [PagePackage(
        page_index=0,
        width=1000,
        height=1400,
        dpi=200,
        elements=[PageElement(
            kind="ocr",
            type="text",
            text="실제 OCR 문장",
            bbox=(10, 20, 110, 60),
            confidence=0.93,
        )],
    )]

    package = build_result_package("document-1", "sample.pdf", pages)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert set(archive.namelist()) == {"book.xml", "review.json"}
        root = ET.fromstring(archive.read("book.xml"))
        assert "실제 OCR 문장" in "".join(root.itertext())
        review = json.loads(archive.read("review.json"))

    element = review["elements"]["p0001-e00001"]
    assert element["bbox"] == [10, 20, 100, 40]
    assert element["review_status"] == "pending"


def test_special_region_is_always_marked_for_review() -> None:
    pages = [PagePackage(0, 100, 100, 200, [
        PageElement("ai", "formula", "전용 모델 연결 대기", (0, 0, 50, 20), 0.99),
    ])]
    package = build_result_package("document-2", "formula.pdf", pages)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        review = json.loads(archive.read("review.json"))
    assert review["elements"]["p0001-e00001"]["review_status"] == "needs_review"


def test_page_range_matches_wpf_input() -> None:
    assert _selected_page_indexes(6, "전체 페이지 (1-6)") == [0, 1, 2, 3, 4, 5]
    assert _selected_page_indexes(6, "1-3, 5") == [0, 1, 2, 4]


def test_dotnet_encoded_korean_pdf_filename_is_decoded() -> None:
    encoded = "=?utf-8?B?7KCR6re87ZiVIE9DUiDsoITshqHqsoDsgqwucGRm?="
    assert _decode_upload_filename(encoded) == "접근형 OCR 전송검사.pdf"
