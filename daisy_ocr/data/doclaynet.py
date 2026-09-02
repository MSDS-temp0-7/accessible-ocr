"""DocLayNet 데이터셋 로더 — 영역 유형 분류 평가용.

`aihub.py`가 담당하는 「공공행정문서 OCR」은 어절 박스만 있고 **영역 유형
라벨이 없다**. 그래서 유형 분류(5종) 성능은 그 데이터로 측정할 수 없다.
DocLayNet은 영역마다 유형 라벨이 있으므로 이 역할을 맡는다.

    aihub.py     → 한국어 도메인, 텍스트 커버리지 측정
    doclaynet.py → 유형 분류 정확도 측정 (영/독/불/일 문서)

주의할 점 (전수 확인 결과):
- `category_id`는 **1부터 시작**한다(COCO 방식). test split 6,533박스의
  값 범위가 1~11이고 Text(10)가 2,937개로 최다 — DocLayNet 공개 분포와 일치.
  0-indexed로 착각하면 라벨이 한 칸씩 밀려 표를 그림으로 학습시키게 된다.
- 페이지는 **1025×1025 정사각형으로 렌더링**돼 있고 bbox도 같은 좌표계다
  (원본 PDF는 612×792 등이라 비율이 왜곡돼 있다). 정답과 이미지가 그대로
  정렬되므로 스케일 변환이 필요 없다 — `assert_same_coordinate_space` 참고.
- `music` 유형은 DocLayNet에 존재하지 않는다. 5종 중 이것만 측정 불가.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_REPO = "nevernever69/small-DocLayNet-v1.1"

# DocLayNet 원본 11종 (1-indexed COCO)
DOCLAYNET_NAMES = {
    1: "Caption",
    2: "Footnote",
    3: "Formula",
    4: "List-item",
    5: "Page-footer",
    6: "Page-header",
    7: "Picture",
    8: "Section-header",
    9: "Table",
    10: "Text",
    11: "Title",
}

# DocLayNet 11종 → 우리 5종 (I/O 스펙 4.2 유형→DTBook 매핑 기준)
#
# text가 8종을 흡수해 전체의 87.9%를 차지한다(test split 실측). 따라서
# **전체 정확도는 지표로 쓸 수 없다** — "전부 text"라고 답하는 더미도 88%가
# 나온다. 실제로 봐야 하는 값은 비본문 3종의 recall이다
# (`daisy_ocr.eval.classify.nonbody_recall` 참고).
DOCLAYNET_TO_OUR = {
    1: "text",      # Caption
    2: "text",      # Footnote
    3: "formula",   # Formula
    4: "text",      # List-item
    5: "text",      # Page-footer
    6: "text",      # Page-header
    7: "graph",     # Picture
    8: "text",      # Section-header
    9: "table",     # Table
    10: "text",     # Text
    11: "text",     # Title
}

assert set(DOCLAYNET_TO_OUR) == set(DOCLAYNET_NAMES), "11종 매핑 누락"


@dataclass(frozen=True)
class GTBox:
    """영역 하나의 정답 박스.

    원본 `bboxes`는 `[x, y, w, h]`(원점 좌상단)다. 검출 모델
    (`LayoutRegion.bbox`)은 `[x1, y1, x2, y2]`를 쓰므로 **좌표 변환은 이
    클래스의 `xyxy` 한 곳에서만** 한다 (`aihub.WordBox`와 같은 규약).
    """

    category_id: int
    xywh: tuple[float, float, float, float]

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        x, y, w, h = self.xywh
        return (x, y, x + w, y + h)

    @property
    def center(self) -> tuple[float, float]:
        x, y, w, h = self.xywh
        return (x + w / 2, y + h / 2)

    @property
    def doclaynet_type(self) -> str:
        """DocLayNet 원본 유형명 (Caption, Table, ...)."""
        return DOCLAYNET_NAMES[self.category_id]

    @property
    def our_type(self) -> str:
        """우리 5종 유형 (text/table/formula/graph)."""
        return DOCLAYNET_TO_OUR[self.category_id]


@dataclass
class Page:
    """페이지 한 장의 이미지 + 정답."""

    image: object          # PIL.Image.Image (import 비용 때문에 느슨하게 둔다)
    boxes: list[GTBox]
    doc_category: str      # financial_reports, patents, ...
    page_no: int
    original_filename: str


def _resolve_dataset(repo: str, split: str, data_files: str | list[str] | None):
    """레포에서 HF `Dataset` 핸들을 얻는다(아직 이미지를 디코드하지 않는다).

    `repo`를 공식 전체본(`docling-project/DocLayNet-v1.1`)으로 바꿔 쓸 때는
    주의할 점이 있다 — 그 레포 README엔 `nevernever69` 미러가 가진
    `configs:` 스플릿→파일 매핑이 없다. 그 상태로 `split="test"`만 지정하면
    `datasets`가 스플릿을 판별하려고 **train 셔드까지 통째로 받아버릴 수
    있다**(실측: train 7GB+ 다운로드 발생). 이럴 땐 `data_files`로 test 셔드
    파일명을 직접 지정해 원하는 파일만 받게 해야 한다:

        _resolve_dataset("docling-project/DocLayNet-v1.1", split="test",
                          data_files=["data/test-*.parquet"])

    `data_files`를 주면 `split` 인자는 무시된다(datasets 라이브러리 동작) —
    지정한 파일들 전체가 하나의 데이터셋이 된다. 또한 부분 로드는 datasets가
    기대하는 전체 스플릿 구성과 어긋나 `verify_splits`에서
    `ExpectedMoreSplitsError`가 나므로(실측됨) 그 검증을 건너뛴다.
    """
    from datasets import load_dataset

    if data_files is not None:
        return load_dataset(repo, data_files=data_files, split="train", verification_mode="no_checks")
    return load_dataset(repo, split=split)


def row_to_page(row) -> Page:
    """데이터셋 한 행(딕셔너리형)을 `Page`로 변환 — 여기서 이미지가 디코드된다."""
    meta = row["metadata"]
    return Page(
        image=row["image"],
        boxes=[
            GTBox(category_id=int(cid), xywh=tuple(bb))  # type: ignore[arg-type]
            for cid, bb in zip(row["category_id"], row["bboxes"])
        ],
        doc_category=meta["doc_category"],
        page_no=int(meta["page_no"]),
        original_filename=meta["original_filename"],
    )


def load_pages(
    n: int | None = 100,
    split: str = "test",
    repo: str = DEFAULT_REPO,
    data_files: str | list[str] | None = None,
) -> list[Page]:
    """DocLayNet에서 `n`장을 **한 번에 전부 디코드해서** 리스트로 반환.

    `n=None`이면 스플릿 전체 — 표본이 수천 장이면 이미지가 전부 메모리에
    올라간다(4,999장 기준 노트북에서는 문제없이 돌았지만, 페이지 하나만
    필요한 경우가 반복되는 상황엔 안 맞는다). 그런 용도(예: 요청마다 한
    장씩만 보여주는 웹 서버)엔 `load_dataset_handle()` + `row_to_page()`로
    필요한 행만 그때그때 디코드하는 쪽을 쓴다.

    첫 실행 시 HuggingFace에서 parquet을 내려받아 캐시한다(약 1.2GB, 기본
    레포 기준). `data_files` 관련 주의사항은 `_resolve_dataset()` 참고.
    """
    ds = _resolve_dataset(repo, split, data_files)
    if n is not None:
        ds = ds.select(range(min(n, len(ds))))
    return [row_to_page(row) for row in ds]


def load_dataset_handle(
    split: str = "test",
    repo: str = DEFAULT_REPO,
    data_files: str | list[str] | None = None,
):
    """지연 접근용 — 이미지를 미리 디코드하지 않고 `Dataset` 핸들만 반환.

    `handle[i]`로 인덱싱한 뒤 `row_to_page()`에 넘기면 그 한 장만 디코드된다.
    표본이 아주 클 때(예: 공식 전체 test 4,999장) 페이지 몇 장만 보여주면
    되는 상황(웹 서버 등)에 쓴다 — `load_pages()`처럼 전부 메모리에 올리지
    않는다.
    """
    return _resolve_dataset(repo, split, data_files)


def assert_same_coordinate_space(page: Page, meta_width: int, meta_height: int) -> None:
    """이미지 크기와 bbox 좌표계가 일치하는지 확인.

    DocLayNet 재배포본 중에는 이미지를 리사이즈해 두고 bbox는 원본 좌표로
    남긴 것이 있다. 그 경우 스케일 변환 없이 쓰면 모든 지표가 조용히 망가지므로
    로드 직후 한 번 확인한다.
    """
    w, h = page.image.size  # type: ignore[attr-defined]
    if (w, h) != (meta_width, meta_height):
        raise ValueError(
            f"좌표계 불일치: 이미지 {w}x{h} != coco {meta_width}x{meta_height}. "
            "bbox 스케일 변환이 필요하다."
        )


def type_distribution(pages: list[Page]) -> dict[str, int]:
    """5종 유형별 박스 수. 더미 베이스라인(최다 유형 비율) 계산용."""
    dist: dict[str, int] = {}
    for p in pages:
        for b in p.boxes:
            dist[b.our_type] = dist.get(b.our_type, 0) + 1
    return dict(sorted(dist.items(), key=lambda kv: -kv[1]))


def majority_baseline(pages: list[Page]) -> tuple[str, float]:
    """("가장 흔한 유형", 그 비율) — 전체 정확도가 넘어야 하는 하한선."""
    dist = type_distribution(pages)
    total = sum(dist.values())
    if not total:
        return ("", 0.0)
    top = max(dist, key=lambda k: dist[k])
    return (top, dist[top] / total)
