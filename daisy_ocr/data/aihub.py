"""AI Hub 「공공행정문서 OCR」 데이터셋 로더.

이 데이터셋의 성격 (전수 조사 결과):
- 페이지 11,397장, 라벨 JSON ↔ 원천 JPG 가 파일명 기준으로 대응
- annotation 1,339,230개가 **전부** `type=rectangle` / `ttype=textType1`
- 즉 **어절 단위 텍스트 검출·인식** 데이터이며, 표/수식/그림 같은
  **영역 유형 라벨은 존재하지 않는다**

따라서 F1의 5종 유형 분류를 이 데이터로 학습할 수는 없고,
사전학습 레이아웃 모델의 **텍스트 커버리지 평가셋**으로 쓴다.
(`daisy_ocr.eval.coverage` 참고)

디렉터리 구조:
    <루트>/[라벨]validation/01.라벨링데이터(Json)/<분류>/<기관코드>/<연도>/*.json
    <루트>/[원천]validation/02.원천데이터(Jpg)/<분류>/<기관코드>/<연도>/*.jpg

라벨/원천의 하위 경로와 파일명이 같아 경로 산술로 짝을 찾는다. 다만 루트
위치는 압축 해제·재배치에 따라 달라지므로 **하드코딩하지 않고 탐색한다**
(`find_roots`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# 데이터셋 최상위 (프로젝트 루트 기준 상대 경로)
DATASET_BASE = Path("data/공공행정문서 OCR")

LABEL_DIRNAME = "01.라벨링데이터(Json)"
IMAGE_DIRNAME = "02.원천데이터(Jpg)"

DEFAULT_INDEX_CSV = Path("data/cache/aihub_index.csv")
DEFAULT_SAMPLE_CSV = Path("data/cache/sample_100.csv")


@dataclass(frozen=True)
class WordBox:
    """어절 하나의 정답 박스.

    원본 JSON의 `annotation.bbox`는 `[x, y, w, h]`(원점 좌상단)이다.
    검출 모델(`LayoutRegion.bbox`)은 `[x1, y1, x2, y2]`를 쓰므로,
    **좌표 변환은 이 클래스의 `xyxy` 한 곳에서만** 한다.
    """

    ann_id: int
    text: str
    xywh: tuple[int, int, int, int]

    @property
    def xyxy(self) -> tuple[int, int, int, int]:
        x, y, w, h = self.xywh
        return (x, y, x + w, y + h)

    @property
    def center(self) -> tuple[float, float]:
        x, y, w, h = self.xywh
        return (x + w / 2, y + h / 2)


@dataclass
class PageLabel:
    """페이지 한 장의 라벨."""

    image_file: str
    width: int
    height: int
    category: str
    make_code: str
    year: str
    boxes: list[WordBox]


# ── 루트 탐색 ────────────────────────────────────────────────────────────

def _find_dirs(base: Path, name: str, max_depth: int = 4) -> list[Path]:
    """`base` 아래에서 이름이 `name`인 디렉터리를 찾는다.

    일치하는 디렉터리 안으로는 더 내려가지 않는다 — 그러지 않으면
    이미지 11,397장이 든 하위 트리를 통째로 훑게 된다.
    """
    found: list[Path] = []

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = [c for c in d.iterdir() if c.is_dir()]
        except OSError:
            return
        for c in children:
            if c.name == name:
                found.append(c)   # 여기서 멈춤
            else:
                walk(c, depth + 1)

    walk(base, 0)
    return sorted(found)


@lru_cache(maxsize=4)
def find_roots(base: Path | str = DATASET_BASE) -> tuple[Path, Path]:
    """(라벨 루트, 원천 루트)를 탐색해 반환.

    라벨이 여러 벌 존재할 수 있으므로(재배치 중 복사본 등) **원천과 같은
    상위 디렉터리를 공유하는 짝**을 우선한다.
    """
    base = Path(base)
    if not base.exists():
        raise FileNotFoundError(f"데이터셋 없음: {base.resolve()}")

    label_roots = _find_dirs(base, LABEL_DIRNAME)
    image_roots = _find_dirs(base, IMAGE_DIRNAME)
    if not label_roots or not image_roots:
        raise FileNotFoundError(
            f"라벨/원천 디렉터리를 찾지 못함 (label={len(label_roots)}, "
            f"image={len(image_roots)}) under {base.resolve()}"
        )

    # 라벨 루트의 조부모 = 원천 루트의 조부모 인 짝을 우선
    for ir in image_roots:
        for lr in label_roots:
            if lr.parent.parent == ir.parent.parent:
                return lr, ir
    return label_roots[0], image_roots[0]


def image_path_for(json_path: Path | str, base: Path | str = DATASET_BASE) -> Path:
    """라벨 JSON 경로 → 대응하는 원천 JPG 경로.

    라벨/원천이 동일한 하위 경로·파일명을 쓰므로 루트만 갈아끼우면 된다.
    (실재 여부는 보장하지 않는다 — 짝 없는 파일이 소수 존재)
    """
    label_root, image_root = find_roots(base)
    rel = Path(json_path).relative_to(label_root)
    return (image_root / rel).with_suffix(".jpg")


def iter_label_paths(base: Path | str = DATASET_BASE):
    """라벨 JSON 경로를 정렬된 순서로 순회."""
    label_root, _ = find_roots(base)
    yield from sorted(label_root.rglob("*.json"))


# ── 라벨 파싱 ────────────────────────────────────────────────────────────

def load_page(json_path: Path | str) -> PageLabel:
    """라벨 JSON 한 개를 파싱.

    주의: `annotation.id`에는 **결번**이 있다(예: 5350069-2011-0001-0029은
    34번 없음). id를 리스트 인덱스로 쓰지 말 것. 또 배열 순서가 판독 순서를
    보장하지 않으므로(같은 파일에서 y좌표가 되돌아감) 순서 의존 금지.
    """
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    img = raw["images"][0]
    boxes = [
        WordBox(
            ann_id=int(a["id"]),
            text=a["annotation.text"],
            xywh=tuple(int(v) for v in a["annotation.bbox"]),  # type: ignore[arg-type]
        )
        for a in raw["annotations"]
    ]
    return PageLabel(
        image_file=img["image.file.name"],
        width=int(img["image.width"]),
        height=int(img["image.height"]),
        category=img["image.category"],
        make_code=img["image.make.code"],
        year=img["image.make.year"],
        boxes=boxes,
    )


# ── 인덱스 ───────────────────────────────────────────────────────────────

def build_index(
    base: Path | str = DATASET_BASE,
    out_csv: Path | str | None = DEFAULT_INDEX_CSV,
    require_image: bool = True,
):
    """전 페이지 인덱스를 만든다(이미지 픽셀은 읽지 않음 → 1분 내외).

    크기 정보는 JSON 안에 있으므로 JPG를 열 필요가 없다. 다만
    `require_image=True`면 대응 JPG의 **존재만** 확인하고 없는 행은 버린다
    (짝 없는 라벨이 소수 있음).

    컬럼: json_path, jpg_path, category, make_code, year, width, height, n_boxes
    """
    import pandas as pd

    rows = []
    dropped = 0
    for jp in iter_label_paths(base):
        ip = image_path_for(jp, base)
        if require_image and not ip.exists():
            dropped += 1
            continue
        page = load_page(jp)
        rows.append(
            {
                "json_path": jp.as_posix(),
                "jpg_path": ip.as_posix(),
                "category": page.category,
                "make_code": page.make_code,
                "year": page.year,
                "width": page.width,
                "height": page.height,
                "n_boxes": len(page.boxes),
            }
        )

    if dropped:
        print(f"⚠️  대응 JPG 없어 제외한 라벨: {dropped}건")

    df = pd.DataFrame(rows)
    if out_csv is not None:
        out = Path(out_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False, encoding="utf-8-sig")
    return df


def load_index(csv_path: Path | str = DEFAULT_INDEX_CSV):
    """캐시된 인덱스 CSV를 읽는다. 없으면 안내와 함께 예외."""
    import pandas as pd

    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(
            f"인덱스 없음: {p}\n먼저 01_data_index.ipynb 를 실행하거나 build_index() 호출"
        )
    # year·make_code는 문자열로 유지 (정렬·그룹핑 일관성)
    return pd.read_csv(p, dtype={"year": str, "make_code": str})


def stratified_sample(index_df, n: int = 100, seed: int = 0):
    """업무분류 12종에서 균등하게 n장을 뽑는다(재현 가능).

    카테고리별 보유량이 균등 배분량보다 적으면 그만큼만 뽑고, 남은 몫은
    여유 있는 카테고리에 돌아간다(작은 카테고리부터 배정해 한 번에 수렴).
    """
    import pandas as pd

    groups = {k: g for k, g in index_df.groupby("category")}
    order = sorted(groups, key=lambda k: len(groups[k]))

    quota: dict[str, int] = {}
    remaining_n, remaining_k = n, len(order)
    for cat in order:
        take = min(remaining_n // remaining_k, len(groups[cat]))
        quota[cat] = take
        remaining_n -= take
        remaining_k -= 1

    picked = [groups[c].sample(n=k, random_state=seed) for c, k in quota.items() if k]
    return pd.concat(picked).sort_values(["category", "json_path"]).reset_index(drop=True)
