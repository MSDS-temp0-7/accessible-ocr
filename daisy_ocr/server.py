"""Accessible OCR Windows 앱용 로컬 HTTP API.

PDF와 옵션을 받아 CLOVA OCR 및 DocLayout-YOLO를 실행하고, WPF가 읽는
book.xml/review.json ZIP 패키지를 반환한다. 작업 상태는 데모 단계에서는
메모리에 보관하며 앱을 종료하면 사라진다.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from pathlib import Path
from threading import Lock
from urllib.parse import unquote

import pypdfium2 as pdfium
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
WORKING_ROOT = Path.cwd()
REPOSITORY_ROOT = (
    WORKING_ROOT
    if (WORKING_ROOT / "config" / "integration-api.env.example").exists()
    else PACKAGE_ROOT
)
load_dotenv(REPOSITORY_ROOT / "config" / "integration-api.env", override=False)
load_dotenv(REPOSITORY_ROOT / ".env", override=False)
if not os.environ.get("CLOVA_GATEWAY") and os.environ.get("CLOVA_OCR_SECRET"):
    os.environ["CLOVA_GATEWAY"] = os.environ["CLOVA_OCR_SECRET"]

from daisy_ocr.layout.detect import DEFAULT_MODEL, LayoutRegion, to_our_type
from daisy_ocr.layout.render import render_pdf_page
from daisy_ocr.music.adapter import music_runtime_status, recognize_music_region
from daisy_ocr.output.package import PagePackage, build_result_package
from daisy_ocr.pipeline import PreparedPage, TranscribedRegion, merge_page, prepare_page

app = FastAPI(title="Accessible OCR Local API", version="0.1.0")


@dataclass
class Job:
    job_id: str
    document_id: str
    source_path: Path
    source_name: str
    options: dict
    result_path: Path
    status: str = "queued"
    progress: int = 0
    message: str = "처리 대기 중"
    error: str | None = None
    review_updates: dict[str, dict] = field(default_factory=dict)


_jobs: dict[str, Job] = {}
_jobs_by_document: dict[str, Job] = {}
_jobs_lock = Lock()


def _job_payload(job: Job) -> dict:
    return {
        "job_id": job.job_id,
        "document_id": job.document_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
    }


def _update_job(job: Job, **changes: object) -> None:
    with _jobs_lock:
        for name, value in changes.items():
            setattr(job, name, value)


def _decode_upload_filename(value: str) -> str:
    """RFC 2047/5987로 인코딩된 .NET multipart 파일명을 원래 이름으로 복원한다."""
    try:
        decoded = str(make_header(decode_header(value)))
    except (LookupError, UnicodeDecodeError):
        decoded = value
    return unquote(decoded).replace("\\", "/").rsplit("/", 1)[-1]


def _selected_page_indexes(page_count: int, value: object) -> list[int]:
    text = str(value or "").strip()
    if not text or "전체" in text.lower() or text.lower() in {"all", "all pages"}:
        return list(range(page_count))

    selected: set[int] = set()
    found_number = False
    for part in re.split(r"[,;]", text):
        numbers = [int(number) for number in re.findall(r"\d+", part)]
        if not numbers:
            continue
        found_number = True
        if len(numbers) == 1:
            selected.add(numbers[0] - 1)
        else:
            start, end = numbers[:2]
            if start > end:
                raise ValueError("시작 페이지는 끝 페이지보다 클 수 없습니다.")
            selected.update(range(start - 1, end))
    if not found_number or not selected:
        raise ValueError("페이지 범위에 숫자를 입력하세요.")
    if min(selected) < 0:
        raise ValueError("페이지 번호는 1 이상이어야 합니다.")
    if max(selected) >= page_count:
        raise ValueError(f"페이지 범위가 문서 전체 {page_count}페이지를 벗어났습니다.")
    return sorted(selected)


def _option_enabled(options: dict, element_type: str) -> bool:
    option_names = {
        "table": "DetectTables",
        "formula": "DetectMath",
        "graph": "DetectCharts",
        "music": "DetectMusic",
        "unknown": "DetectImages",
    }
    name = option_names.get(element_type)
    return bool(options.get(name, True)) if name else True


def _region_type(region: LayoutRegion, layout_model: str) -> str:
    """모델팀 어댑터가 승격한 악보 라벨과 원본 레이아웃 라벨을 통합한다."""
    return "music" if region.label == "music" else to_our_type(region.label, layout_model)


def _music_regions(prepared: PreparedPage, options: dict) -> list[LayoutRegion]:
    """악보 문맥이 있는 페이지의 가장 큰 그림 영역을 악보로 승격한다.

    현재 DocLayNet 체크포인트에는 music 클래스가 없다. 따라서 제목·캡션 OCR에
    악보 문맥이 있고 사용자가 악보 검출을 켠 경우에만 가장 큰 Picture/Figure
    영역 하나를 실제 악보 모델 입력으로 사용한다.
    """
    regions = list(prepared.non_text_regions)
    if not options.get("DetectMusic", True):
        return regions

    page_text = " ".join(block.text for block in prepared.ocr_blocks).lower()
    hints = tuple(
        value.strip().lower()
        for value in os.environ.get(
            "MUSIC_PAGE_HINTS",
            "악보,sheet music,music score,오선보,음이름,계이름",
        ).split(",")
        if value.strip()
    )
    if not any(hint in page_text for hint in hints):
        return regions

    candidates = [
        region for region in regions
        if to_our_type(region.label, prepared.layout_model) == "graph"
    ]
    if not candidates:
        return regions

    score_region = max(
        candidates,
        key=lambda region: max(0.0, region.bbox[2] - region.bbox[0])
        * max(0.0, region.bbox[3] - region.bbox[1]),
    )
    return [
        LayoutRegion("music", list(region.bbox), region.confidence)
        if region is score_region else region
        for region in regions
    ]


def _ocr_text_inside(prepared: PreparedPage, region: LayoutRegion) -> str:
    rx1, ry1, rx2, ry2 = region.bbox
    fragments: list[str] = []
    for block in prepared.ocr_blocks:
        bx1, by1, bx2, by2 = block.bbox
        center_x, center_y = (bx1 + bx2) / 2, (by1 + by2) / 2
        if rx1 <= center_x <= rx2 and ry1 <= center_y <= ry2 and block.text.strip():
            fragments.append(block.text.strip())
    return " ".join(fragments)


def _encode_page_preview(image) -> bytes:
    """검수 화면용 페이지 이미지를 JPEG로 직렬화한다."""
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()


async def _transcribe_special_regions(
    image,
    prepared: PreparedPage,
    options: dict,
    output_root: Path,
    page_index: int,
) -> tuple[list[LayoutRegion], list[TranscribedRegion]]:
    notices = {
        "table": "표 영역이 감지되었습니다. 전용 표 구조 분석 전 검수가 필요합니다.",
        "formula": "수식 영역이 감지되었습니다. 전용 수식 변환 전 검수가 필요합니다.",
        "graph": "이미지 또는 그래프 영역이 감지되었습니다. 설명 생성 전 검수가 필요합니다.",
        "music": "악보 영역이 감지되었습니다. 전용 악보 분석 전 검수가 필요합니다.",
        "unknown": "비텍스트 영역이 감지되었습니다. 검수가 필요합니다.",
    }
    regions: list[LayoutRegion] = []
    transcribed: list[TranscribedRegion] = []
    source_regions = _music_regions(prepared, options)
    for region_index, region in enumerate(source_regions):
        element_type = _region_type(region, prepared.layout_model)
        if not _option_enabled(options, element_type):
            continue
        regions.append(region)
        if element_type == "music":
            x1, y1, x2, y2 = region.bbox
            crop_box = (
                max(0, int(x1)), max(0, int(y1)),
                min(image.width, max(int(x1) + 1, int(x2))),
                min(image.height, max(int(y1) + 1, int(y2))),
            )
            crop = image.crop(crop_box)
            try:
                result = await asyncio.to_thread(
                    recognize_music_region,
                    crop,
                    output_root,
                    page_index=page_index,
                    region_index=region_index,
                )
                transcribed.append(TranscribedRegion(
                    type="music",
                    label=region.label,
                    bbox=tuple(region.bbox),
                    confidence=result.confidence,
                    text=result.text,
                    error="music_review_required" if result.needs_review else None,
                ))
            except Exception as exc:
                message = str(exc).strip() or type(exc).__name__
                transcribed.append(TranscribedRegion(
                    type="music",
                    label=region.label,
                    bbox=tuple(region.bbox),
                    confidence=region.confidence,
                    text=(
                        "악보 영역을 찾았지만 악보 인식기를 실행하지 못했습니다. "
                        "Audiveris와 AUDIVERIS_CMD 설정을 확인한 뒤 다시 분석하세요.\n"
                        f"오류: {message}"
                    ),
                    error=f"music_recognition_failed: {message}",
                ))
            finally:
                crop.close()
            continue

        recognized_text = _ocr_text_inside(prepared, region)
        notice = notices.get(element_type, notices["unknown"])
        text = f"{notice}\n{recognized_text}" if recognized_text else notice
        transcribed.append(TranscribedRegion(
            type=element_type,
            label=region.label,
            bbox=tuple(region.bbox),
            confidence=region.confidence,
            text=text,
            error="specialized_model_pending",
        ))
    return regions, transcribed


async def _process_job(job: Job) -> None:
    try:
        _update_job(job, status="processing", progress=5, message="PDF 페이지를 확인하고 있습니다.")
        document = pdfium.PdfDocument(str(job.source_path))
        try:
            page_count = len(document)
        finally:
            document.close()
        if page_count == 0:
            raise ValueError("페이지가 없는 PDF입니다.")

        dpi = int(os.environ.get("OCR_DPI", "200"))
        model = os.environ.get("OCR_LAYOUT_MODEL", DEFAULT_MODEL)
        page_indexes = _selected_page_indexes(page_count, job.options.get("PageRange"))
        packages: list[PagePackage] = []

        for sequence, page_index in enumerate(page_indexes):
            progress = 10 + int(sequence / max(len(page_indexes), 1) * 80)
            _update_job(job, progress=progress, message=f"{page_index + 1}페이지를 OCR 처리하고 있습니다.")
            image = await asyncio.to_thread(render_pdf_page, job.source_path, page_index, dpi)
            try:
                prepared = await prepare_page(image, layout_model=model)
                selected_regions, transcribed = await _transcribe_special_regions(
                    image,
                    prepared,
                    job.options,
                    job.source_path.parent / "music",
                    page_index,
                )
                ocr_blocks = prepared.ocr_blocks if job.options.get("DetectBody", True) else []
                elements = merge_page(ocr_blocks, selected_regions, transcribed)
                preview_bytes = await asyncio.to_thread(_encode_page_preview, image)
                packages.append(PagePackage(page_index, image.width, image.height, dpi, elements, preview_bytes))
            finally:
                image.close()

        _update_job(job, progress=92, message="검수 패키지를 만들고 있습니다.")
        package_bytes = build_result_package(job.document_id, job.source_name, packages)
        job.result_path.write_bytes(package_bytes)
        _update_job(job, status="done", progress=100, message="OCR 분석이 완료되었습니다.")
    except Exception as exc:
        _update_job(job, status="failed", message="OCR 분석에 실패했습니다.", error=str(exc))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "accessible-ocr-local-api",
        "music": music_runtime_status(),
    }


@app.post("/api/v1/jobs", status_code=202)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    options: str = Form("{}"),
) -> dict:
    decoded_filename = _decode_upload_filename(file.filename or "")
    if not decoded_filename or Path(decoded_filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="PDF 파일만 처리할 수 있습니다.")
    try:
        parsed_options = json.loads(options)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="options JSON 형식이 잘못되었습니다.") from exc

    workspace = Path(tempfile.mkdtemp(prefix="accessible-ocr-"))
    source_path = workspace / "source.pdf"
    with source_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            output.write(chunk)

    job_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    job = Job(job_id, document_id, source_path, decoded_filename, parsed_options, workspace / "result.zip")
    with _jobs_lock:
        _jobs[job_id] = job
        _jobs_by_document[document_id] = job
    background_tasks.add_task(_process_job, job)
    return _job_payload(job)


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return _job_payload(job)


@app.get("/api/v1/jobs/{job_id}/result")
def get_result(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    if job.status not in {"done", "completed"} or not job.result_path.exists():
        raise HTTPException(status_code=409, detail="아직 결과가 준비되지 않았습니다.")
    return FileResponse(job.result_path, media_type="application/zip", filename=f"{job.document_id}.zip")


@app.patch("/api/v1/documents/{document_id}/elements/{element_id}/review", status_code=204)
async def update_review(document_id: str, element_id: str, payload: dict) -> Response:
    job = _jobs_by_document.get(document_id)
    if not job:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    job.review_updates[element_id] = payload
    return Response(status_code=204)


def run() -> None:
    import uvicorn

    host = os.environ.get("OCR_API_HOST", "127.0.0.1")
    port = int(os.environ.get("OCR_API_PORT", "8000"))
    uvicorn.run("daisy_ocr.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
