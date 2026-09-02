"""CLOVA OCR(네이버 클라우드 플랫폼) General API로 페이지 본문을 읽는다.

일반 글자와 좌표·신뢰도는 CLOVA가 담당하고, 그래프·표·수식은 레이아웃
모델 및 후속 전용 모델이 담당한다. 페이지 1장당 과금되므로 `read_page()`는
이미지 한 장만 호출하며 배치·프리페치를 추가하지 않는다.
"""
from __future__ import annotations

import base64
import io
import os
import time
import uuid
from dataclasses import dataclass

import httpx
from PIL import Image


@dataclass
class TextBlock:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]


def _get_credentials() -> tuple[str, str]:
    # 새 앱 표준 이름을 우선하고, 모델팀의 기존 이름도 호환한다.
    secret = os.environ.get("CLOVA_OCR_SECRET") or os.environ.get("CLOVA_GATEWAY")
    invoke_url = os.environ.get("CLOVA_OCR_INVOKE_URL")
    placeholder_markers = ("REPLACE", "PASTE", "YOUR_")
    has_placeholder = any(
        marker in value.upper()
        for value in (secret or "", invoke_url or "")
        for marker in placeholder_markers
    )
    if not secret or not invoke_url or has_placeholder:
        raise RuntimeError(
            "config/integration-api.env의 CLOVA_OCR_SECRET과 "
            "CLOVA_OCR_INVOKE_URL을 실제 발급값으로 교체해야 합니다."
        )
    return secret, invoke_url


def read_page(image: Image.Image, timeout: float = 30.0) -> list[TextBlock]:
    """CLOVA OCR General API를 호출해 페이지 전체 텍스트 블록을 반환한다.

    한 번 호출 = 한 페이지 과금이므로 이 함수는 반드시 이미지 1장에 대해서만
    호출한다(호출부에서 배치·재시도 루프를 만들지 말 것).
    """
    secret, invoke_url = _get_credentials()

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "images": [{"format": "jpg", "name": "page", "data": b64}],
    }
    headers = {"X-OCR-SECRET": secret, "Content-Type": "application/json"}

    resp = httpx.post(invoke_url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    images = data.get("images") or []
    if not images:
        return []
    result = images[0]
    if result.get("inferResult") != "SUCCESS":
        raise RuntimeError(f"CLOVA OCR 실패: {result.get('message')}")

    blocks: list[TextBlock] = []
    for field in result.get("fields", []):
        vertices = field.get("boundingPoly", {}).get("vertices", [])
        if not vertices:
            continue
        xs = [v["x"] for v in vertices]
        ys = [v["y"] for v in vertices]
        blocks.append(TextBlock(
            text=field.get("inferText", ""),
            confidence=float(field.get("inferConfidence", 0.0)),
            bbox=(min(xs), min(ys), max(xs), max(ys)),
        ))
    return blocks
