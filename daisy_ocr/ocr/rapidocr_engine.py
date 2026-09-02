"""RapidOCR(PP-OCR 계열, onnxruntime 백엔드) 기반 전체 페이지 텍스트 인식.

레이아웃 모델(`daisy_ocr.layout.detect`)과 완전히 독립적으로 동작한다 —
레이아웃이 어떤 영역을 놓쳐도 이 모듈은 페이지 전체에서 글자를 찾는다.

**EasyOCR 대신 이걸 쓰는 이유**: 같은 영어 문서 기준 실측 비교에서
EasyOCR은 68개 조각으로 잘게 쪼개면서 'LhCrI', "Vork there thiey
areleaders" 같은 오인식을 다수 냈다. RapidOCR(PP-OCRv6 검출 + 언어별
PP-OCRv5 인식)은 같은 문서를 30개의 자연스러운 문장 단위로, 신뢰도
0.97~1.00·오타 없이 인식했다. 한국어도 실제 AI Hub 문서로 확인함(예:
"허가하오니 허가조건이행 및 제반법규를 철저히 준수하시기 바랍니다").

PaddleOCR을 직접 쓰지 않는 이유는 `daisy_ocr/layout/detect.py`가 아니라
이 웹앱 개발 중 실측한 별도 문제다 — PaddlePaddle 3.3.1의 oneDNN 실행
엔진이 이 Windows/CPU 환경에서 `ConvertPirAttribute2RuntimeAttribute`
미지원 오류로 텍스트 검출 자체가 죽는다(server/mobile 모델, oneDNN,
PIR 비활성화 세 가지 우회 다 실패). RapidOCR은 같은 계열 모델을 onnxruntime
으로 돌려 이 문제를 원천적으로 피한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

# 요청마다 RapidOCR이 찍는 [INFO] 모델 경로 로그가 너무 시끄럽다 — 경고 이상만 남긴다.
logging.getLogger("RapidOCR").setLevel(logging.WARNING)

DEFAULT_LANG = "korean"  # rapidocr.utils.typings.LangRec 값 문자열

_engines: dict[str, object] = {}


@dataclass
class TextBlock:
    """OCR로 인식된 텍스트 한 줄(RapidOCR 기준 대략 한 문장~한 줄 단위)."""

    text: str
    confidence: float
    bbox: tuple[float, float, float, float]  # xyxy


def _get_engine(lang: str = DEFAULT_LANG):
    """언어별로 엔진을 캐시(모델 로드·첫 언어 모델 다운로드가 몇 초 걸린다)."""
    if lang not in _engines:
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import LangRec, ModelType, OCRVersion

        _engines[lang] = RapidOCR(params={
            "Rec.lang_type": LangRec(lang),
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.model_type": ModelType.MOBILE,  # 언어별 모델은 mobile만 배포됨
        })
    return _engines[lang]


def read_page(image: Image.Image, lang: str = DEFAULT_LANG) -> list[TextBlock]:
    """이미지 한 장의 텍스트를 전부 인식해 읽기 순서 그대로 반환."""
    engine = _get_engine(lang)
    arr = np.array(image.convert("RGB"))
    result = engine(arr)

    if result.boxes is None:
        return []

    blocks = []
    for box, text, conf in zip(result.boxes, result.txts, result.scores):
        xs = box[:, 0]
        ys = box[:, 1]
        blocks.append(TextBlock(
            text=text,
            confidence=float(conf),
            bbox=(float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())),
        ))
    return blocks
