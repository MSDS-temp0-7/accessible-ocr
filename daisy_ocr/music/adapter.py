"""`daisy-music` 결과를 OCR 파이프라인의 악보 영역 계약으로 변환한다.

모델팀 폴더는 이름에 하이픈이 있고 독립 실행형 프로젝트 구조이므로 이
모듈에서만 동적으로 불러온다. WPF 앱과 나머지 OCR 코드는 모델팀 내부 구현에
직접 의존하지 않는다.
"""
from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class MusicRecognitionResult:
    text: str
    confidence: float
    needs_review: bool
    music_xml: str | None
    raw: dict[str, Any]


def _model_root() -> Path:
    configured = os.environ.get("MUSIC_MODEL_ROOT", "daisy-music")
    root = Path(configured).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _load_services():
    root = _model_root()
    services_dir = root / "services"
    if not services_dir.is_dir():
        raise RuntimeError(
            "악보 모델 폴더를 찾을 수 없습니다. "
            f"MUSIC_MODEL_ROOT를 확인하세요: {root}"
        )

    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    try:
        recognizer = importlib.import_module("services.music_recognizer")
        runner = importlib.import_module("services.audiveris_runner")
    except Exception as exc:
        raise RuntimeError(f"악보 모델 모듈을 불러오지 못했습니다: {exc}") from exc
    return recognizer, runner


def music_runtime_status() -> dict[str, Any]:
    if os.environ.get("MUSIC_RECOGNITION_ENABLED", "true").lower() in {"0", "false", "no"}:
        return {"enabled": False, "available": False, "message": "환경설정에서 비활성화됨"}

    try:
        _, runner = _load_services()
        command = runner.resolve_audiveris_command()
        return {
            "enabled": True,
            "available": True,
            "model_root": str(_model_root()),
            "audiveris_command": command,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "available": False,
            "model_root": str(_model_root()),
            "message": str(exc),
        }


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_content(content: dict[str, Any]) -> str:
    pieces: list[str] = []
    summary = content.get("summary")
    summary_text = summary.get("text") if isinstance(summary, dict) else summary
    if isinstance(summary_text, str) and summary_text.strip():
        pieces.append("악보 요약\n" + summary_text.strip())

    spoken_text = content.get("spokenText")
    if isinstance(spoken_text, str) and spoken_text.strip():
        pieces.append("마디별 읽기\n" + spoken_text.strip())

    review = content.get("review") if isinstance(content.get("review"), dict) else {}
    reasons = review.get("reasons") if isinstance(review, dict) else None
    if isinstance(reasons, list) and reasons:
        pieces.append("검수 사유\n" + ", ".join(str(reason) for reason in reasons))

    return "\n\n".join(pieces) or "악보는 인식되었지만 접근성 설명이 생성되지 않았습니다."


def recognize_music_region(
    image: Image.Image,
    output_root: Path,
    *,
    page_index: int,
    region_index: int,
) -> MusicRecognitionResult:
    """악보 영역 이미지를 모델팀 파이프라인으로 처리한다."""
    if os.environ.get("MUSIC_RECOGNITION_ENABLED", "true").lower() in {"0", "false", "no"}:
        raise RuntimeError("악보 인식이 MUSIC_RECOGNITION_ENABLED 설정에서 비활성화되어 있습니다.")

    recognizer, _ = _load_services()
    output_root.mkdir(parents=True, exist_ok=True)
    input_path = output_root / f"page-{page_index + 1:04d}-music-{region_index + 1:03d}.png"
    image.convert("RGB").save(input_path, format="PNG", optimize=True)

    timeout = int(os.environ.get("AUDIVERIS_TIMEOUT", "600"))
    try:
        result = recognizer.recognize_music(
            image_path=input_path,
            output_root=output_root / "runs",
            audiveris_timeout=timeout,
        )
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    content = result.get("musicContent") if isinstance(result, dict) else None
    if not isinstance(content, dict):
        raise RuntimeError("악보 모델 응답에 musicContent가 없습니다.")

    confidence_data = content.get("confidence")
    average = confidence_data.get("average") if isinstance(confidence_data, dict) else confidence_data
    confidence = max(0.0, min(1.0, _number(average, 0.0)))
    review = content.get("review") if isinstance(content.get("review"), dict) else {}
    return MusicRecognitionResult(
        text=_format_content(content),
        confidence=confidence,
        needs_review=bool(review.get("needsReview", False)),
        music_xml=content.get("musicXml") if isinstance(content.get("musicXml"), str) else None,
        raw=content,
    )
