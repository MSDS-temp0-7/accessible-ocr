"""DocLayout-YOLO 사전학습 모델 기반 레이아웃 검출 (학습 불필요, 로컬 CPU).

체크포인트를 **여러 개 등록해 두고 비교**할 수 있다(`MODELS`). 기본값은
`doclaynet`이며, `imgsz`는 `notebooks/layout-benchmark.ipynb` 6장에서 실측한
값(960)을 그대로 쓴다. `conf`는 이후 실전 파이프라인(웹앱 데모, F2~F4 라우팅)을
운영하며 재검토했다:

    포함관계 기반 유형별 recall (DocLayNet test 100장, daisy_ocr.eval.classify)
                table   formula  graph   평균 검출 영역/페이지
      conf 0.02  0.913   1.000   0.951        18.3
      conf 0.3   0.913   0.971   0.934        13.2  (현재값)

table recall은 변화 없고 formula·graph도 각각 2.9%p·1.7%p만 낮아지는 반면,
페이지당 검출 영역은 28% 줄어든다. conf 0.02는 raw 검출 단계에서 같은
물리적 영역에 박스가 4~20개까지 겹쳐 나오는 경우가 실측됐고(NMS가 다 못
거름), 이게 F2~F4로 그대로 라우팅되면 같은 표/수식/그림이 여러 번
설명되는 문제로 이어진다(다운스트림에서 겹침 기반 NMS로 추가 정리하긴
하지만, 애초에 conf를 올려 원천에서 줄이는 편이 낫다). recall 손실이
작고 노이즈 감소가 뚜렷해 0.3을 기본값으로 확정했다.

과거 판단(0.02)은 다른 지표(어절 커버리지 기반, 입도에 민감함)로 측정한
"0.959 vs 0.935" 차이에 근거했었다 — 위 표의 포함관계 기반 지표(입도
불일치에 면역, `daisy_ocr/eval/classify.py` 상단 참고)로 다시 재보니 그
정도로 크게 벌어지지 않았다.

라벨 체계가 체크포인트마다 다르다는 점도 중요하다:

- DocStructBench 학습본: 10종(`title`, `plain text`, `abandon`, ...).
  우리 5종으로 접을 때 **의미가 어긋난다** — 예컨대 목차(TOC)를 `plain text`로
  내놓는데 DocLayNet 정답은 `Table`이다.
- DocLayNet 학습본: DocLayNet 11종을 그대로 출력하므로 5종 매핑이 1:1이고
  의미 왜곡이 없다.

그래서 라벨→유형 매핑을 모델별로 분리하고, 모델 로드 시 `model.names`가
매핑에 전부 있는지 확인한다(체크포인트를 갈아끼웠을 때 조용히 틀리는 것 방지).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from daisy_ocr.runtime import configure_runtime, pick_device

# torch/doclayout 로드 전에 스레드 상한을 고정 → 전 코어 점유로 인한 PC 멈춤 방지
_THREADS = configure_runtime()


@dataclass(frozen=True)
class ModelSpec:
    """등록된 체크포인트 하나."""

    repo: str
    filename: str
    imgsz: int         # 기본 추론 해상도 (학습 해상도와 다를 수 있다 — 실측 최적값 우선)
    conf: float         # 기본 신뢰도 임계값 (실측 최적값)
    label_scheme: str  # 어느 라벨→유형 매핑을 쓸지


MODELS: dict[str, ModelSpec] = {
    # 비교·회귀용 — DocStructBench 10종. 라벨 체계가 우리 5종과 어긋난다(위 docstring 참고).
    "docstructbench": ModelSpec(
        repo="juliozhao/DocLayout-YOLO-DocStructBench",
        filename="doclayout_yolo_docstructbench_imgsz1024.pt",
        imgsz=1024,
        conf=0.20,
        label_scheme="docstructbench",
    ),
    # 기본값 — DocLayNet 학습본(DocSynth300K 사전학습 → DocLayNet 파인튜닝).
    # imgsz는 실측 최적값(960). conf는 0.3 — 위 docstring의 포함관계 기반
    # 재검토 참고(recall 손실 작음, 페이지당 검출 영역 28% 감소).
    "doclaynet": ModelSpec(
        repo="juliozhao/DocLayout-YOLO-DocLayNet-Docsynth300K_pretrained",
        filename="doclayout_yolo_doclaynet_imgsz1120_docsynth_pretrain.pt",
        imgsz=960,
        conf=0.3,
        label_scheme="doclaynet",
    ),
    # DocLayNet 학습본 (사전학습 없음) — 사전학습 효과 비교용. 튜닝 안 함.
    "doclaynet-scratch": ModelSpec(
        repo="juliozhao/DocLayout-YOLO-DocLayNet-from_scratch",
        filename="doclayout_yolo_doclaynet_imgsz1120_from_scratch.pt",
        imgsz=1120,
        conf=0.20,
        label_scheme="doclaynet",
    ),
}

DEFAULT_MODEL = "doclaynet"


@dataclass
class LayoutRegion:
    """검출된 레이아웃 영역 하나."""
    label: str            # 원본 라벨 (title, plain text, table, isolate_formula, figure, ...)
    bbox: list[float]     # [x1, y1, x2, y2]
    confidence: float


# ── 라벨 → 우리 5종 유형 (I/O 스펙 4.2 기준) ─────────────────────────────
#
# 키는 `_norm()`으로 정규화된 형태. 체크포인트가 'List-item'/'list_item'
# 어느 쪽으로 내놓든 같은 항목에 걸린다.

# DocStructBench 10종
_LABELS_DOCSTRUCTBENCH = {
    "title": "text",
    "plain text": "text",
    "abandon": "text",          # 머리말/꼬리말/페이지번호
    "figure caption": "text",
    "table caption": "text",
    "table footnote": "text",
    "formula caption": "text",
    "figure": "graph",
    "table": "table",
    "isolate formula": "formula",
}

# DocLayNet 11종 — 1:1 매핑 (daisy_ocr.data.doclaynet.DOCLAYNET_TO_OUR와 동일해야 함)
_LABELS_DOCLAYNET = {
    "caption": "text",
    "footnote": "text",
    "formula": "formula",
    "list item": "text",
    "page footer": "text",
    "page header": "text",
    "picture": "graph",
    "section header": "text",
    "table": "table",
    "text": "text",
    "title": "text",
}

LABEL_SCHEMES: dict[str, dict[str, str]] = {
    "docstructbench": _LABELS_DOCSTRUCTBENCH,
    "doclaynet": _LABELS_DOCLAYNET,
}


def _norm(label: str) -> str:
    """라벨 표기 차이를 흡수 (대소문자, `-`/`_`/공백)."""
    return label.strip().lower().replace("-", " ").replace("_", " ")


def to_our_type(label: str, model: str = DEFAULT_MODEL) -> str:
    """원본 라벨을 우리 유형 체계(text/table/formula/graph/music/unknown)로 변환."""
    scheme = LABEL_SCHEMES[MODELS[model].label_scheme]
    return scheme.get(_norm(label), "unknown")


_models: dict[str, object] = {}


def _get_model(name: str = DEFAULT_MODEL):
    """체크포인트를 로드(이름별 캐시). 라벨 매핑 누락이 있으면 즉시 실패."""
    if name not in MODELS:
        raise KeyError(f"등록되지 않은 모델: {name}. 사용 가능: {list(MODELS)}")

    if name not in _models:
        from doclayout_yolo import YOLOv10
        from huggingface_hub import hf_hub_download
        import torch

        torch.set_num_threads(_THREADS)  # 런타임에도 스레드 상한 재확인
        spec = MODELS[name]
        weights = hf_hub_download(repo_id=spec.repo, filename=spec.filename)
        model = YOLOv10(weights)

        # 체크포인트가 내놓을 수 있는 모든 라벨이 매핑돼 있는지 확인.
        # 빠뜨리면 해당 영역이 조용히 'unknown'이 되어 지표가 틀어진다.
        scheme = LABEL_SCHEMES[spec.label_scheme]
        missing = {v for v in model.names.values() if _norm(v) not in scheme}
        if missing:
            raise ValueError(
                f"모델 '{name}'의 라벨이 '{spec.label_scheme}' 매핑에 없음: {sorted(missing)}"
            )
        _models[name] = model

    return _models[name]


def detect_layout(
    image: Image.Image,
    conf: float | None = None,
    imgsz: int | None = None,
    device: str = "auto",
    model: str = DEFAULT_MODEL,
) -> list[LayoutRegion]:
    """이미지 한 장의 레이아웃 영역을 검출.

    `conf`/`imgsz`를 `None`으로 두면 해당 체크포인트의 등록된 기본값을 쓴다
    (`MODELS[model]` 참고 — 기본 `doclaynet`은 imgsz 960 · conf 0.3).
    `device='auto'`면 GPU 가용 시 GPU 사용.
    """
    net = _get_model(model)
    if imgsz is None:
        imgsz = MODELS[model].imgsz
    if conf is None:
        conf = MODELS[model].conf
    dev = pick_device(device)
    arr = np.array(image.convert("RGB"))
    result = net.predict(arr, imgsz=imgsz, conf=conf, device=dev, verbose=False)[0]

    names = result.names  # {id: label}
    regions: list[LayoutRegion] = []
    boxes = result.boxes
    for i in range(len(boxes)):
        cls_id = int(boxes.cls[i].item())
        xyxy = boxes.xyxy[i].tolist()
        regions.append(
            LayoutRegion(
                label=names.get(cls_id, str(cls_id)),
                bbox=[float(v) for v in xyxy],
                confidence=float(boxes.conf[i].item()),
            )
        )
    # 위→아래, 좌→우 순으로 정렬(간이 판독 순서)
    regions.sort(key=lambda r: (round(r.bbox[1] / 20), r.bbox[0]))
    return regions
