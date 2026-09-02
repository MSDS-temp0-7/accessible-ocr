"""WPF 클라이언트가 읽는 DTBook/review 결과 패키지를 만든다."""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from daisy_ocr.pipeline import PageElement

DTBOOK_NS = "http://www.daisy.org/z3986/2005/dtbook/"
ET.register_namespace("", DTBOOK_NS)


@dataclass(frozen=True)
class PagePackage:
    page_index: int
    width: int
    height: int
    dpi: int
    elements: list[PageElement]
    image_bytes: bytes | None = None


def _review_status(element: PageElement) -> str:
    if element.kind != "ocr" or element.error:
        return "needs_review"
    return "needs_review" if (element.confidence or 0.0) < 0.8 else "pending"


def _element_id(page_index: int, sequence: int) -> str:
    return f"p{page_index + 1:04d}-e{sequence + 1:05d}"


def build_result_package(document_id: str, title: str, pages: list[PagePackage]) -> bytes:
    root = ET.Element(f"{{{DTBOOK_NS}}}dtbook", {"version": "2005-3"})
    head = ET.SubElement(root, f"{{{DTBOOK_NS}}}head")
    ET.SubElement(head, f"{{{DTBOOK_NS}}}meta", {"name": "dc:Identifier", "content": document_id})
    ET.SubElement(head, f"{{{DTBOOK_NS}}}meta", {"name": "dc:Title", "content": title})
    book = ET.SubElement(root, f"{{{DTBOOK_NS}}}book")
    body = ET.SubElement(book, f"{{{DTBOOK_NS}}}bodymatter")

    review_pages: list[dict] = []
    review_elements: dict[str, dict] = {}
    for page in pages:
        level = ET.SubElement(body, f"{{{DTBOOK_NS}}}level1", {"class": "page"})
        ET.SubElement(level, f"{{{DTBOOK_NS}}}pagenum").text = str(page.page_index + 1)
        image_ref = f"pages/page-{page.page_index + 1:04d}.jpg" if page.image_bytes else None
        review_page = {"page_index": page.page_index, "width": page.width, "height": page.height, "dpi": page.dpi}
        if image_ref:
            review_page["image_ref"] = image_ref
        review_pages.append(review_page)

        for sequence, element in enumerate(page.elements):
            element_id = _element_id(page.page_index, sequence)
            paragraph = ET.SubElement(level, f"{{{DTBOOK_NS}}}p", {"id": element_id, "class": element.type})
            paragraph.text = element.text
            x1, y1, x2, y2 = element.bbox
            review_elements[element_id] = {
                "page_index": page.page_index,
                "type": element.type,
                "bbox": [round(x1, 2), round(y1, 2), round(max(0.0, x2 - x1), 2), round(max(0.0, y2 - y1), 2)],
                "confidence": round(float(element.confidence or 0.0), 4),
                "source": element.kind,
                "label": element.label,
                "error": element.error,
                "region_ref": element_id,
                "review_status": _review_status(element),
            }

    review = {"schema_version": "1.0", "document_id": document_id, "title": title, "pages": review_pages, "elements": review_elements}
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("book.xml", xml_bytes)
        archive.writestr("review.json", json.dumps(review, ensure_ascii=False, indent=2).encode("utf-8"))
        for page in pages:
            if page.image_bytes:
                archive.writestr(f"pages/page-{page.page_index + 1:04d}.jpg", page.image_bytes)
    return output.getvalue()
