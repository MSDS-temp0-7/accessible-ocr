"""페이지 1장을 "레이아웃 분할 → 텍스트 부분 텍스트화 → 하나로 병합"하는 모듈.

이 모듈이 담당하는 범위(=이 프로젝트 담당자의 실제 책임 범위)와, 담당이
아닌 범위를 명확히 나눈다:

    담당 범위 (이 파일의 핵심 3개 함수)
      1. 레이아웃 분할   `prepare_page()` 1단계 — daisy_ocr.layout.detect
         페이지 안의 영역을 찾고 텍스트/비텍스트로 나눈다.
      2. 텍스트 부분 텍스트화  `prepare_page()` 2단계 — daisy_ocr.ocr.clova_engine
         레이아웃 검출과 완전히 독립적으로 페이지 전체 글자를 읽는다.
         레이아웃이 박스를 못 그린 부분도 텍스트가 빠지지 않게 하려는
         설계다. 비텍스트(표/그래프/수식/악보) 영역 중복 검출 제거도
         `prepare_page()`가 맡는다(3단계).
      3. 하나로 병합    `merge_page()`
         텍스트화 결과와, 비텍스트 영역을 "무언가로" 설명한 결과를 받아
         중복 없이 원본 문서를 읽는 순서 그대로 합친다.

    담당 아님 — 다른 모델팀 책임
      비텍스트(표/그래프/수식/악보) 영역을 실제로 무엇으로 바꿀지(표
      구조 인식, LaTeX 변환, 이미지 설명 등)는 이 모듈의 관심사가
      아니다. `merge_page()`는 `TranscribedRegion`이라는 엔진 무관
      계약(타입·bbox·텍스트만 있으면 됨)만 요구하므로, 어떤 모델이
      만들었든 그 형태로만 넘기면 그대로 합쳐진다.
      `transcribe_regions()`(OpenAI 비전 모델 호출)와 `process_page()`
      (전체를 이어붙인 편의 함수)는 **참고용 기본 구현**이다 — 웹앱
      데모가 지금 이걸 쓰고 있을 뿐, 다른 모델팀 결과물로 통째로
      바뀌어도 `prepare_page()`/`merge_page()`는 손댈 필요가 없다.

각 단계가 실제로 왜 이렇게 됐는지는 함수 docstring에 있다 — 전부 webapp
데모를 실제 문서로 반복 검증하며 발견한 문제를 고친 결과다.
"""
from __future__ import annotations

import asyncio
import io
import os
import time
from dataclasses import dataclass

from PIL import Image

from daisy_ocr.layout.detect import DEFAULT_MODEL, MODELS, LayoutRegion, detect_layout, to_our_type
from daisy_ocr.ocr.clova_engine import TextBlock, read_page

Bbox = tuple[float, float, float, float]

# F2(표)/F3(그래프)/F4(수식)의 전용 모델을 대신하는 간이 데모 프롬프트.
# 실제 표 구조 인식·수치 검증·MathML 변환은 아직 없다.
TRANSCRIBE_PROMPTS: dict[str, str] = {
    "table": "이 표 이미지를 마크다운 표로 옮겨 적어줘. 셀 내용을 임의로 요약하거나 생략하지 마. 마크다운 표만 출력해.",
    "formula": "이 수식 이미지를 LaTeX로 옮겨 적어줘. LaTeX 코드만 출력해.",
    "graph": "이 이미지(그래프·사진·그림)가 무엇을 보여주는지 한국어로 2~3문장으로 설명해줘.",
    "music": "이 악보 이미지에 어떤 음악적 요소(음자리표·박자·음표 등)가 보이는지 간단히 설명해줘.",
    "unknown": "이 이미지에 무엇이 있는지 한국어로 간단히 설명해줘.",
}

DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_MAX_TRANSCRIBE_REGIONS = 40  # 페이지당 API 호출 상한(비용·레이트리밋 보호)


@dataclass(frozen=True)
class TranscribedRegion:
    """비텍스트 영역 1개를 OpenAI로 전사한 결과."""

    type: str          # table | formula | graph | music | unknown
    label: str          # 레이아웃 모델 원본 라벨
    bbox: Bbox
    confidence: float   # 레이아웃 검출 신뢰도
    text: str | None    # 전사 결과. 실패 시 None
    error: str | None = None


@dataclass(frozen=True)
class PageElement:
    """최종 읽기 순서 목록의 항목 하나 — 본문 조각이거나 비텍스트 전사 결과."""

    kind: str  # "ocr" | "ai"
    type: str  # ocr는 "text" 고정, ai는 table/formula/graph/music/unknown
    text: str
    bbox: Bbox
    confidence: float | None = None  # OCR 신뢰도 또는 레이아웃 검출 신뢰도
    label: str | None = None          # ai만 채움(레이아웃 원본 라벨)
    error: str | None = None          # ai 전사 실패 시 에러 메시지


@dataclass
class PreparedPage:
    """`prepare_page()`의 결과 — 레이아웃 분할 + 텍스트화까지 끝난 상태.

    `non_text_regions`가 다음 단계(비텍스트 전사)의 입력이다. 어떤
    모델이 이걸 전사하든(OpenAI든 다른 모델팀 결과든) 상관없이, 전사
    결과를 `TranscribedRegion` 형태로만 만들어 `merge_page()`에 넘기면
    된다.
    """

    ocr_blocks: list[TextBlock]           # CLOVA로 읽은 페이지 전체 텍스트 블록
    regions: list[LayoutRegion]           # 레이아웃 원본 검출(중복 제거 전, 연구·디버그용)
    non_text_regions: list[LayoutRegion]  # 표/그래프/수식/악보만, 중복 제거 완료 — 다음 단계 입력
    layout_model: str
    conf: float
    imgsz: int
    ocr_elapsed_ms: float
    detect_elapsed_ms: float


@dataclass
class PageResult:
    elements: list[PageElement]           # 읽기 순서로 정렬된 최종 결과 — 주 산출물
    regions: list[LayoutRegion]           # 레이아웃 원본 검출(중복 제거 전, 연구·디버그용)
    ocr_blocks: list[TextBlock]           # CLOVA 원본 블록(필터 전)
    transcribed: list[TranscribedRegion]  # OpenAI 전사 원본(중복 제거 후 보낸 것 기준)
    ocr_elapsed_ms: float
    detect_elapsed_ms: float
    transcribe_elapsed_ms: float
    model: str
    conf: float
    imgsz: int


def _overlap_ratios(a: Bbox, b: Bbox) -> tuple[float, float]:
    """(IoU, containment) — containment = 교집합 / min(두 넓이).

    작은 박스가 큰 박스 안에 거의 다 들어가는 경우 IoU는 낮게 나온다(분모가
    큰 박스 면적에 끌려감). 같은 물리적 영역의 중복 검출을 놓치지 않으려면
    포함관계도 같이 봐야 한다 — daisy_ocr.eval.coverage의 포함관계 기준과
    같은 발상이다.
    """
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max((ax2 - ax1) * (ay2 - ay1), 1e-6)
    area_b = max((bx2 - bx1) * (by2 - by1), 1e-6)
    iou = inter / max(area_a + area_b - inter, 1e-6)
    containment = inter / min(area_a, area_b)
    return iou, containment


def dedupe_regions(
    regions: list[LayoutRegion], iou_thresh: float = 0.5, contain_thresh: float = 0.8
) -> list[LayoutRegion]:
    """같은 유형끼리 겹침(IoU)이나 포함관계가 크면 신뢰도가 높은 것만 남긴다.

    conf가 낮을수록 같은 물리적 영역(특히 수식)에 박스가 여러 개 겹쳐
    검출된다(실측: 수식 1개에 박스 최대 20개, YOLO 자체 NMS가 다 못 거름).
    그대로 두면 OpenAI가 같은 내용을 겹치는 박스 수만큼 반복 전사한다.
    표준 NMS(IoU)만으로는 부족해서(위 `_overlap_ratios` 참고) 포함관계를
    같이 쓴다.
    """
    ordered = sorted(regions, key=lambda r: -r.confidence)
    kept: list[LayoutRegion] = []
    for r in ordered:
        is_dup = False
        for k in kept:
            if k.label != r.label:
                continue
            iou, containment = _overlap_ratios(k.bbox, r.bbox)
            if iou > iou_thresh or containment > contain_thresh:
                is_dup = True
                break
        if not is_dup:
            kept.append(r)
    return kept


def is_covered_by_any_region(bbox: Bbox, regions: list[LayoutRegion], min_overlap: float = 0.3) -> bool:
    """OCR 블록 자신의 넓이 중 `min_overlap` 이상이 어떤 비텍스트 영역과 겹치는가.

    중심점만 보면 놓치는 경우가 있다 — CLOVA가 비텍스트 영역 주변 문장과
    그 안의 글자를 하나의 블록으로 묶어버리면 블록 중심이 영역 밖으로 빠질
    수 있다(실측: 수식이 본문 텍스트에 섞여 중복 표시됨). 블록 자신의
    넓이 기준 겹침 비율로 판단하면 이런 경우도 잡힌다.
    """
    bx1, by1, bx2, by2 = bbox
    barea = max((bx2 - bx1) * (by2 - by1), 1e-6)
    for r in regions:
        rx1, ry1, rx2, ry2 = r.bbox
        ix1, iy1 = max(rx1, bx1), max(ry1, by1)
        ix2, iy2 = min(rx2, bx2), min(ry2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        if (iw * ih) / barea > min_overlap:
            return True
    return False


@dataclass
class _FlowItem:
    x1: float
    y1: float
    y2: float
    element: PageElement


def order_by_reading_flow(items: list[_FlowItem]) -> list[_FlowItem]:
    """같은 가로줄끼리 묶어(y구간 겹침) 그 안에서는 x로, 줄 자체는 y로 정렬한다.

    단순히 bbox 상단 y로만 정렬하면 같은 줄에 나란히 놓인 항목들(문서
    양식의 "이름 / 연락처 / 주소" 같은 다열 필드)이 y값의 미세한 차이
    때문에 서로 뒤섞인다.

    비텍스트(ai) 항목은 이 줄 묶기에서 제외한다 — 한 줄이 아니라 문단
    하나를 통째로 차지하므로 다른 텍스트와 줄을 공유할 이유가 없고,
    합칠 때 행의 y범위를 매번 넓히면(min/max) 세로로 긴 항목이 한 번
    섞였을 때 범위가 확 커져서 그 아래 무관한 줄들까지 전부 같은 행으로
    빨려 들어가 순서가 무너진다(실측 확인).

    OCR끼리 묶을 때도 행의 기준 범위는 그 행을 처음 만든 항목(seed) 것을
    그대로 유지하고 절대 넓히지 않는다 — 매번 넓히면 촘촘히 붙어 있는
    여러 줄이 사슬처럼(transitive) 하나의 행으로 계속 흡수돼 순서가
    무너진다(실측 확인: 문서 하단 항목 목록에서 발생).
    """
    ocr_items = [it for it in items if it.element.kind == "ocr"]
    other_items = [it for it in items if it.element.kind != "ocr"]

    rows: list[dict] = []
    for item in sorted(ocr_items, key=lambda it: it.y1):
        row = next(
            (
                r for r in rows
                if min(r["y2"], item.y2) - max(r["y1"], item.y1)
                > 0.4 * min(item.y2 - item.y1, r["y2"] - r["y1"])
            ),
            None,
        )
        if row is not None:
            row["items"].append(item)
        else:
            rows.append({"y1": item.y1, "y2": item.y2, "items": [item]})

    for item in other_items:
        rows.append({"y1": item.y1, "y2": item.y2, "items": [item]})

    rows.sort(key=lambda r: r["y1"])
    ordered: list[_FlowItem] = []
    for row in rows:
        ordered.extend(sorted(row["items"], key=lambda it: it.x1))
    return ordered


# ─────────────────────────────────────────────────────────────────────────
# 담당 범위: 레이아웃 분할 → 텍스트화 → 병합. 아래 두 함수가 그 전부다.
# ─────────────────────────────────────────────────────────────────────────


async def prepare_page(
    image: Image.Image,
    *,
    layout_model: str = DEFAULT_MODEL,
    conf: float | None = None,
    imgsz: int | None = None,
) -> PreparedPage:
    """레이아웃 분할 + 텍스트 부분 텍스트화. 비텍스트 영역을 "무엇으로 바꿀지"는
    다루지 않는다 — `non_text_regions`를 돌려줄 뿐이다.

    `conf`/`imgsz`를 `None`으로 두면 `layout_model` 체크포인트의 등록된
    기본값을 쓴다(`daisy_ocr.layout.detect.MODELS` 참고). 레이아웃 검출과
    본문 OCR은 서로 독립이라 순차 호출해도 무방하다(둘 다 각자 완결된
    작업이라 순서를 바꿔도 결과는 같다).
    """
    t0 = time.perf_counter()
    ocr_blocks = await asyncio.to_thread(read_page, image)
    ocr_elapsed_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    regions = await asyncio.to_thread(detect_layout, image, conf, imgsz, "auto", layout_model)
    detect_elapsed_ms = (time.perf_counter() - t0) * 1000

    non_text_regions = [r for r in regions if to_our_type(r.label, layout_model) != "text"]
    deduped_regions = dedupe_regions(non_text_regions)

    spec_conf, spec_imgsz = conf, imgsz
    if spec_conf is None or spec_imgsz is None:
        spec = MODELS[layout_model]
        spec_conf = spec_conf if spec_conf is not None else spec.conf
        spec_imgsz = spec_imgsz if spec_imgsz is not None else spec.imgsz

    return PreparedPage(
        ocr_blocks=ocr_blocks,
        regions=regions,
        non_text_regions=deduped_regions,
        layout_model=layout_model,
        conf=spec_conf,
        imgsz=spec_imgsz,
        ocr_elapsed_ms=ocr_elapsed_ms,
        detect_elapsed_ms=detect_elapsed_ms,
    )


def merge_page(
    ocr_blocks: list[TextBlock],
    non_text_regions: list[LayoutRegion],
    transcribed: list[TranscribedRegion],
) -> list[PageElement]:
    """텍스트화 결과 + 비텍스트 전사 결과를 중복 없이 읽기 순서로 합친다.

    `transcribed`는 어떤 모델이 만들었든 상관없다 — `TranscribedRegion`
    (type/label/bbox/confidence/text/error)만 갖추면 된다. 이 함수는
    engine-agnostic하다.

    처리 순서:
      1. 비텍스트 영역과 크게(30%↑) 겹치는 OCR 조각은 뺀다 — `transcribed`가
         이미 그 자리를 대표하므로. `transcribed`가 비어 있으면(비텍스트
         전사를 아예 안 했거나 실패) 아무것도 잃지 않도록 원본을 그대로 쓴다.
      2. 읽기 순서로 정렬한다(`order_by_reading_flow`).
    """
    kept_blocks = (
        [b for b in ocr_blocks if not is_covered_by_any_region(b.bbox, non_text_regions)]
        if transcribed else ocr_blocks
    )

    flow_items = [
        _FlowItem(
            x1=b.bbox[0], y1=b.bbox[1], y2=b.bbox[3],
            element=PageElement(kind="ocr", type="text", text=b.text, bbox=b.bbox, confidence=b.confidence),
        )
        for b in kept_blocks
    ] + [
        _FlowItem(
            x1=t.bbox[0], y1=t.bbox[1], y2=t.bbox[3],
            element=PageElement(
                kind="ai", type=t.type, text=t.text or "", bbox=t.bbox,
                confidence=t.confidence, label=t.label, error=t.error,
            ),
        )
        for t in transcribed
    ]
    return [it.element for it in order_by_reading_flow(flow_items)]


# ─────────────────────────────────────────────────────────────────────────
# 참고용 기본 구현 — 다른 모델팀 결과물로 교체될 부분. `merge_page()`는 이
# 아래 어떤 것에도 의존하지 않는다.
# ─────────────────────────────────────────────────────────────────────────


async def _get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(".env에 OPENAI_API_KEY가 없습니다.")
    from openai import AsyncOpenAI
    return AsyncOpenAI(api_key=api_key)


async def transcribe_regions(
    image: Image.Image,
    regions: list[LayoutRegion],
    layout_model: str = DEFAULT_MODEL,
    *,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    max_regions: int = DEFAULT_MAX_TRANSCRIBE_REGIONS,
) -> list[TranscribedRegion]:
    """[참고 구현] 비텍스트 영역들을 크롭해 OpenAI 비전 모델로 전사한다.

    다른 모델팀이 표/그래프/수식 전사를 자체 모델로 대체한다면 이 함수
    대신 그 모델을 호출하고, 결과를 `TranscribedRegion` 리스트로만 만들어
    `merge_page()`에 넘기면 된다 — 이 함수의 존재 자체가 필수는 아니다.

    `regions`는 `prepare_page()`가 돌려준 `non_text_regions`를 그대로
    넘기면 된다. `layout_model`은 `region.label`을 5종 유형으로 되돌리는
    데만 쓴다(`daisy_ocr.layout.detect.to_our_type`).
    """
    import base64

    if not regions:
        return []

    client = await _get_openai_client()
    truncated = regions[:max_regions]

    async def transcribe_one(r: LayoutRegion) -> TranscribedRegion:
        our_type = to_our_type(r.label, layout_model)
        x1, y1, x2, y2 = r.bbox
        crop_box = (
            max(0, int(x1)), max(0, int(y1)),
            min(image.width, max(int(x1) + 1, int(x2))),
            min(image.height, max(int(y1) + 1, int(y2))),
        )
        crop = image.crop(crop_box)
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        prompt = TRANSCRIBE_PROMPTS.get(our_type, TRANSCRIBE_PROMPTS["unknown"])
        try:
            resp = await client.chat.completions.create(
                model=openai_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                max_completion_tokens=1500,
                # gpt-5 계열은 추론 모델이라 reasoning_effort를 안 낮추면 보이지 않는
                # reasoning 토큰이 max_completion_tokens를 다 먹어 답변이 빈 문자열로
                # 나올 수 있다(실측: reasoning_tokens 704/731).
                reasoning_effort="minimal",
            )
            return TranscribedRegion(
                type=our_type, label=r.label, bbox=r.bbox, confidence=r.confidence,
                text=resp.choices[0].message.content, error=None,
            )
        except Exception as exc:  # 이 영역만 실패 처리하고 나머지는 계속
            return TranscribedRegion(
                type=our_type, label=r.label, bbox=r.bbox, confidence=r.confidence,
                text=None, error=str(exc),
            )

    return list(await asyncio.gather(*[transcribe_one(r) for r in truncated]))


async def process_page(
    image: Image.Image,
    *,
    layout_model: str = DEFAULT_MODEL,
    conf: float | None = None,
    imgsz: int | None = None,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    max_transcribe_regions: int = DEFAULT_MAX_TRANSCRIBE_REGIONS,
    transcribe_non_text: bool = True,
) -> PageResult:
    """[편의 함수] `prepare_page()` → `transcribe_regions()`(OpenAI) →
    `merge_page()`를 그대로 이어붙인 올인원 함수 — webapp 데모가 쓴다.

    비텍스트 전사를 다른 모델팀 결과물로 바꾸는 실제 서비스에서는 이
    함수를 쓰지 말고, `prepare_page()`로 `non_text_regions`를 얻어 그
    모델을 호출한 뒤 `merge_page()`로 직접 조합할 것 — 셋 다 이 모듈이
    공개하는 독립 함수다.

    `conf`/`imgsz`를 `None`으로 두면 `layout_model` 체크포인트의 등록된
    기본값을 쓴다(`daisy_ocr.layout.detect.MODELS` 참고).

    비용 참고: 호출 1번 = CLOVA 과금 1페이지 + OpenAI 호출(비텍스트 영역
    수만큼, 최대 `max_transcribe_regions`개)이다. 배치·재시도 루프로 감싸지
    말 것 — 페이지 1장씩만 호출하는 게 설계 전제다.
    """
    prepared = await prepare_page(image, layout_model=layout_model, conf=conf, imgsz=imgsz)

    transcribed: list[TranscribedRegion] = []
    transcribe_elapsed_ms = 0.0
    if transcribe_non_text and prepared.non_text_regions:
        t0 = time.perf_counter()
        transcribed = await transcribe_regions(
            image, prepared.non_text_regions, layout_model,
            openai_model=openai_model, max_regions=max_transcribe_regions,
        )
        transcribe_elapsed_ms = (time.perf_counter() - t0) * 1000

    elements = merge_page(prepared.ocr_blocks, prepared.non_text_regions, transcribed)

    return PageResult(
        elements=elements,
        regions=prepared.regions,
        ocr_blocks=prepared.ocr_blocks,
        transcribed=transcribed,
        ocr_elapsed_ms=prepared.ocr_elapsed_ms,
        detect_elapsed_ms=prepared.detect_elapsed_ms,
        transcribe_elapsed_ms=transcribe_elapsed_ms,
        model=layout_model,
        conf=prepared.conf,
        imgsz=prepared.imgsz,
    )
