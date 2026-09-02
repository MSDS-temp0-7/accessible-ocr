"""텍스트 커버리지 — 레이아웃 검출이 본문 글자를 얼마나 담아내는지.

**왜 IoU가 아닌가**: 공공행정문서 OCR의 정답은 *어절* 박스(페이지당 평균
117개, 평균 3.6자)이고 레이아웃 모델의 예측은 *영역* 박스(문단·표 단위)라
입도가 달라 IoU 매칭이 성립하지 않는다. 대신 **포함 관계**로 잰다.

    어절 박스의 중심점이 예측 영역 중 하나에 들어가면 "커버됨"
    coverage = 커버된 어절 수 / 전체 어절 수

커버되지 않은 어절 = DTBook 산출물에서 통째로 누락될 텍스트이므로,
이 값은 "레이아웃 검출이 본문 인식을 저하시키지 않는지"에 직접 답한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from daisy_ocr.data.aihub import WordBox
    from daisy_ocr.layout.detect import LayoutRegion


@dataclass
class CoverageResult:
    """한 페이지의 커버리지 측정 결과."""

    n_words: int
    n_covered: int
    uncovered: list["WordBox"] = field(default_factory=list)
    by_type: dict[str, int] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        return self.n_covered / self.n_words if self.n_words else 0.0


def contains(bbox: Sequence[float], point: tuple[float, float]) -> bool:
    """예측 영역 bbox(x1, y1, x2, y2)가 점을 포함하는가."""
    x1, y1, x2, y2 = bbox[:4]
    px, py = point
    return x1 <= px <= x2 and y1 <= py <= y2


def assign_region(
    point: tuple[float, float], regions: Sequence["LayoutRegion"]
) -> "LayoutRegion | None":
    """점을 포함하는 영역 중 **신뢰도가 가장 높은 것**을 반환(없으면 None).

    커버리지(`coverage`)와 유형 분류 정확도(`daisy_ocr.eval.classify`)가
    **같은 귀속 규칙**을 쓰도록 여기 한 곳에 둔다. 두 지표가 서로 다른
    규칙으로 매칭하면 값을 나란히 비교할 수 없다.
    """
    best = None
    for r in regions:
        if contains(r.bbox, point) and (best is None or r.confidence > best.confidence):
            best = r
    return best


def coverage(
    word_boxes: Sequence["WordBox"],
    regions: Sequence["LayoutRegion"],
    model: str | None = None,
) -> CoverageResult:
    """어절 정답 박스가 검출 영역에 얼마나 포함되는지 측정.

    한 어절이 여러 영역에 겹쳐 들어가면 **신뢰도가 가장 높은 영역**에
    귀속시킨다(중복 집계 방지).

    `model`은 `by_type` 집계에만 영향한다 — 체크포인트마다 라벨 체계가 달라
    유형으로 옮기는 매핑이 다르다. 커버리지 비율 자체는 영향받지 않는다.
    `model=None`이면 `detect_layout()`을 호출할 때 쓴 것과 같은 기본 모델을
    가정한다 — `regions`를 다른 모델로 뽑았다면 반드시 명시할 것(라벨 체계가
    안 맞으면 전부 'unknown'으로 조용히 잘못 집계된다).
    """
    from daisy_ocr.layout.detect import DEFAULT_MODEL, to_our_type

    if model is None:
        model = DEFAULT_MODEL

    n_covered = 0
    uncovered: list["WordBox"] = []
    by_type: dict[str, int] = {}

    for wb in word_boxes:
        best = assign_region(wb.center, regions)

        if best is None:
            uncovered.append(wb)
            continue

        n_covered += 1
        t = to_our_type(best.label, model)
        by_type[t] = by_type.get(t, 0) + 1

    return CoverageResult(
        n_words=len(word_boxes),
        n_covered=n_covered,
        uncovered=uncovered,
        by_type=by_type,
    )
