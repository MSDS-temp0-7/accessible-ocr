"""영역 유형 분류 정확도 — 검출 영역이 유형(5종)을 맞게 붙였는지.

**왜 IoU가 아닌가**: `coverage.py`가 어절↔영역 입도 불일치 때문에 IoU를
버린 것과 같은 이유다. DocLayNet 정답은 *문단* 단위, 레이아웃 모델 예측은
*단락 묶음·단(column)* 단위여서 경계가 애초에 일치하지 않는다. 실측으로
확인된 규모(100장, DocStructBench 모델):

    미검출로 집계된 287건 중 225건(78%)이 실은 "더 큰 예측 박스 안에
    85% 이상 들어있음" — 즉 검출은 됐고 입도만 다른 것.
    IoU 0.5 기준 F1 0.729 중 실제 검출 실패는 오류 639건의 15%뿐이었다.

그래서 `coverage.py`와 **똑같은 귀속 규칙**(`assign_region`)을 쓴다.

    정답 박스의 중심점이 들어가는 예측 영역(신뢰도 최고)의 유형과
    정답 유형을 비교한다.

예측 하나가 문단 5개를 덮으면 5개 전부 올바르게 `text`로 채점된다 —
IoU 방식이 FN 4건으로 세던 것이 사라진다.

**전체 정확도를 지표로 쓰지 말 것**: DocLayNet을 5종으로 접으면 `text`가
87.9%라서 "전부 text"인 더미도 88%가 나온다. 봐야 하는 값은
`nonbody_recall()` — 표/수식/그림을 놓치면 F2/F3/F4 라우팅이 실패하고
표가 통째로 본문으로 흘러간다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Sequence

from daisy_ocr.eval.coverage import assign_region

if TYPE_CHECKING:
    from daisy_ocr.data.doclaynet import GTBox
    from daisy_ocr.layout.detect import LayoutRegion

# 본문이 아니라서 각 담당 엔진(F2/F3/F4)으로 라우팅돼야 하는 유형.
# 이걸 text로 오분류하면 해당 콘텐츠가 DTBook 본문에 잘못 섞인다.
NONBODY_TYPES = ("table", "formula", "graph")

UNCOVERED = "(미커버)"


@dataclass
class TypeStat:
    """유형 하나의 집계."""

    correct: int = 0            # 맞게 분류
    wrong: int = 0              # 영역엔 들어갔지만 유형이 틀림
    uncovered: int = 0          # 어느 영역에도 안 들어감

    @property
    def support(self) -> int:
        return self.correct + self.wrong + self.uncovered

    @property
    def recall(self) -> float:
        """이 유형의 정답 중 맞게 분류된 비율."""
        return self.correct / self.support if self.support else 0.0

    @property
    def coverage(self) -> float:
        """이 유형의 정답 중 영역에 잡히기라도 한 비율."""
        s = self.support
        return (self.correct + self.wrong) / s if s else 0.0


@dataclass
class ClassifyResult:
    """한 페이지(또는 합산)의 유형 분류 결과."""

    n_gt: int = 0
    n_covered: int = 0
    n_correct: int = 0
    # (정답 유형, 예측 유형) -> 개수. 미커버는 예측 유형이 UNCOVERED.
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)
    per_type: dict[str, TypeStat] = field(default_factory=dict)
    uncovered: list["GTBox"] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        """전체 정확도. **더미 베이스라인(≈88%)과 함께만 해석할 것.**"""
        return self.n_correct / self.n_gt if self.n_gt else 0.0

    @property
    def coverage_ratio(self) -> float:
        """정답 영역이 예측에 잡힌 비율 — `coverage.py`의 값과 같은 의미."""
        return self.n_covered / self.n_gt if self.n_gt else 0.0

    def merge(self, other: "ClassifyResult") -> "ClassifyResult":
        """페이지별 결과를 합산."""
        self.n_gt += other.n_gt
        self.n_covered += other.n_covered
        self.n_correct += other.n_correct
        for k, v in other.confusion.items():
            self.confusion[k] = self.confusion.get(k, 0) + v
        for t, s in other.per_type.items():
            cur = self.per_type.setdefault(t, TypeStat())
            cur.correct += s.correct
            cur.wrong += s.wrong
            cur.uncovered += s.uncovered
        self.uncovered.extend(other.uncovered)
        return self


def classify_accuracy(
    gt_boxes: Sequence["GTBox"], regions: Sequence["LayoutRegion"], model: str | None = None
) -> ClassifyResult:
    """정답 박스마다 유형이 맞게 분류됐는지 측정.

    `model`은 예측 라벨을 5종으로 옮길 때 쓰는 매핑을 고른다(체크포인트마다
    라벨 체계가 다르다 — `daisy_ocr.layout.detect.to_our_type` 참고). `None`이면
    `detect_layout()`의 기본 모델을 가정한다 — `regions`를 다른 모델로 뽑았다면
    반드시 명시할 것.
    """
    from daisy_ocr.layout.detect import DEFAULT_MODEL, to_our_type

    if model is None:
        model = DEFAULT_MODEL

    res = ClassifyResult()
    for gb in gt_boxes:
        gt_type = gb.our_type
        res.n_gt += 1
        stat = res.per_type.setdefault(gt_type, TypeStat())

        best = assign_region(gb.center, regions)
        if best is None:
            stat.uncovered += 1
            res.uncovered.append(gb)
            key = (gt_type, UNCOVERED)
            res.confusion[key] = res.confusion.get(key, 0) + 1
            continue

        res.n_covered += 1
        pred_type = to_our_type(best.label, model)
        key = (gt_type, pred_type)
        res.confusion[key] = res.confusion.get(key, 0) + 1

        if pred_type == gt_type:
            res.n_correct += 1
            stat.correct += 1
        else:
            stat.wrong += 1

    return res


def nonbody_recall(res: ClassifyResult) -> dict[str, float]:
    """비본문 3종의 recall — **이 프로젝트의 실제 목표 지표.**

    DocLayNet에 없는 유형(music)이나 표본이 0인 유형은 결과에서 빠진다.
    """
    return {
        t: res.per_type[t].recall
        for t in NONBODY_TYPES
        if t in res.per_type and res.per_type[t].support > 0
    }


def type_precision(res: ClassifyResult) -> dict[str, float]:
    """유형별 precision — 예측이 X라고 한 것 중 실제로 X였던 비율.

    `TypeStat.recall`은 "정답 X를 놓치지 않았는가"만 본다. 반대 방향
    ("X라고 예측한 것이 진짜 X인가")은 `confusion`에서 예측 열을 합산해야
    나온다 — 예컨대 recall이 100%인 유형도 다른 유형의 오탐을 끌어모아
    precision은 낮을 수 있다(이 프로젝트에서 실제로 발생: formula recall
    100%인데 precision 96.6% — text/graph 정답의 중심점이 formula 예측
    영역 안에 들어가 버린 경우).

    **주의**: 이 값도 `classify_accuracy`와 같은 GT 중심 귀속 규칙을 쓴다.
    즉 "어느 GT의 중심점도 포함하지 않는 예측"(완전히 헛짚은 예측)은 분모에
    아예 안 잡힌다 — 객체 탐지의 표준 precision(전체 예측 수 대비)보다
    좁은 개념이다. 이 프로젝트가 IoU 대신 포함관계를 쓰기로 한 것과 같은
    이유(coverage.py 상단 참고)로, 완전 헛다리 예측까지 재려면 별도 지표가
    필요하다.
    """
    pred_totals: dict[str, int] = {}
    pred_correct: dict[str, int] = {}
    for (gt, pred), n in res.confusion.items():
        if pred == UNCOVERED:
            continue
        pred_totals[pred] = pred_totals.get(pred, 0) + n
        if gt == pred:
            pred_correct[pred] = pred_correct.get(pred, 0) + n

    return {
        t: pred_correct.get(t, 0) / total
        for t, total in pred_totals.items()
        if total > 0
    }


def confusion_frame(res: ClassifyResult, types: Sequence[str] | None = None):
    """혼동행렬을 DataFrame으로. 행=정답, 열=예측(+미커버)."""
    import pandas as pd

    if types is None:
        types = sorted({t for t, _ in res.confusion} | {p for _, p in res.confusion if p != UNCOVERED})
    rows = list(types)
    cols = list(types) + [UNCOVERED]
    data = [[res.confusion.get((r, c), 0) for c in cols] for r in rows]
    return pd.DataFrame(data, index=pd.Index(rows, name="정답"), columns=pd.Index(cols, name="예측"))


def summary_frame(res: ClassifyResult):
    """유형별 recall/precision/coverage/support 표."""
    import pandas as pd

    precision = type_precision(res)
    rows = []
    for t, s in sorted(res.per_type.items(), key=lambda kv: -kv[1].support):
        rows.append({
            "type": t,
            "recall": s.recall,
            "precision": precision.get(t, float("nan")),
            "coverage": s.coverage,
            "support": s.support,
            "correct": s.correct,
            "wrong": s.wrong,
            "uncovered": s.uncovered,
        })
    return pd.DataFrame(rows).set_index("type")
