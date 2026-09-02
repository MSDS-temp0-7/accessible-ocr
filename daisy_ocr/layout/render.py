"""PDF 페이지를 이미지(PIL)로 렌더링."""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


def render_pdf_page(pdf_path: str | Path, page_index: int = 0, dpi: int = 200) -> Image.Image:
    """PDF의 한 페이지를 지정 dpi로 렌더링해 PIL 이미지로 반환."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[page_index]
        scale = dpi / 72.0  # PDF 기준 72dpi
        bitmap = page.render(scale=scale)
        return bitmap.to_pil().convert("RGB")
    finally:
        pdf.close()


def render_all_pages(pdf_path: str | Path, dpi: int = 200) -> list[Image.Image]:
    """PDF 전체 페이지를 렌더링."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        scale = dpi / 72.0
        return [pdf[i].render(scale=scale).to_pil().convert("RGB") for i in range(len(pdf))]
    finally:
        pdf.close()
