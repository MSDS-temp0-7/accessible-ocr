"""노트북 시각화 헬퍼 — 한글 폰트, 박스 오버레이."""
from __future__ import annotations

from typing import Iterable, Sequence

# 우리 5종 유형 색상 (scripts/test_layout.py 와 동일 계열)
TYPE_COLORS = {
    "text": "#2ca02c",
    "table": "#d62728",
    "formula": "#1f77b4",
    "graph": "#ff7f0e",
    "music": "#9467bd",
    "unknown": "#7f7f7f",
}

# Windows 기본 탑재 한글 폰트 순으로 시도
_FONT_CANDIDATES = ("Malgun Gothic", "NanumGothic", "Gulim", "AppleGothic")


def set_korean_font() -> str | None:
    """matplotlib에 한글 폰트를 지정. 적용된 폰트명을 반환.

    이걸 안 하면 GT 텍스트(`annotation.text`)가 전부 두부(□)로 나온다.
    """
    import matplotlib
    import matplotlib.font_manager as fm

    available = {f.name for f in fm.fontManager.ttflist}
    for name in _FONT_CANDIDATES:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return name
    return None


def draw_boxes(
    ax,
    boxes: Iterable[Sequence[float]],
    color: str = "#d62728",
    labels: Iterable[str] | None = None,
    linewidth: float = 1.0,
    fontsize: int = 7,
) -> None:
    """xyxy 박스들을 축에 그린다. `labels`가 있으면 박스 위에 텍스트도."""
    import matplotlib.patches as patches

    label_iter = iter(labels) if labels is not None else None
    for bbox in boxes:
        x1, y1, x2, y2 = bbox[:4]
        ax.add_patch(
            patches.Rectangle(
                (x1, y1), x2 - x1, y2 - y1,
                linewidth=linewidth, edgecolor=color, facecolor="none",
            )
        )
        if label_iter is not None:
            ax.text(x1, y1 - 3, next(label_iter), color=color, fontsize=fontsize)


def draw_regions(ax, regions, fontsize: int = 8, model: str | None = None) -> None:
    """검출된 LayoutRegion들을 유형별 색으로 그린다(신뢰도 라벨 포함).

    `model`은 라벨→유형 매핑 선택용 — 체크포인트마다 라벨 체계가 다르다.
    `None`이면 `detect_layout()`의 기본 모델을 가정한다.
    """
    from daisy_ocr.layout.detect import DEFAULT_MODEL, to_our_type

    if model is None:
        model = DEFAULT_MODEL

    for r in regions:
        t = to_our_type(r.label, model)
        color = TYPE_COLORS.get(t, TYPE_COLORS["unknown"])
        draw_boxes(ax, [r.bbox], color=color, linewidth=2.0)
        ax.text(r.bbox[0], r.bbox[1] - 4, f"{t} {r.confidence:.2f}",
                color=color, fontsize=fontsize)
