"""Keep the team's GPU dependencies outside the existing OCR environment."""
from __future__ import annotations

import atexit
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import psutil


def _worker_environment() -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="0" if os.name == "nt" else "1")
    # Native Windows tools emit the system encoding; JSON stdio stays UTF-8.
    env["CUDA_VISIBLE_DEVICES"] = os.environ.get("CHART_CUDA_VISIBLE_DEVICES", "0")
    return env


def _root() -> Path:
    return Path(os.environ.get("OCR_REPOSITORY_ROOT", Path.cwd())).resolve()


def _python() -> Path:
    return Path(os.environ.get("CHART_PYTHON", str(_root() / ".venv-chart/Scripts/python.exe")))


def chart_runtime_status() -> dict:
    enabled = os.environ.get("CHART_RECOGNITION_ENABLED", "false").lower() in {"1", "true", "yes"}
    configured = _python().is_file() and (_root() / "ai_engine/chart_analyzer.py").is_file()
    return {"enabled": enabled, "configured": configured, "loaded": _worker.ready and _worker.process is not None and _worker.process.poll() is None,
            "model": os.environ.get("CHART_MODEL_ID", "Qwen/Qwen2.5-VL-7B-Instruct"),
            "message": "실제 추론 성공 여부는 도표 분석으로 확인합니다." if configured else "도표용 Python 환경과 ai_engine 폴더가 필요합니다."}


class _Worker:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.log = None
        self.replies = None
        self.ready = False

    def close(self):
        self.ready = False
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    for child in reversed(psutil.Process(self.process.pid).children(recursive=True)):
                        try:
                            child.terminate()
                        except psutil.NoSuchProcess:
                            pass
                except psutil.NoSuchProcess:
                    pass
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None

    def start(self):
        self.close()
        root = _root()
        if not _python().is_file():
            raise RuntimeError("도표용 Python이 없습니다. scripts/setup-chart.ps1을 먼저 실행하세요.")
        log_path = root / "artifacts/chart-worker.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = log_path.open("a", encoding="utf-8")
        # The CPU layout engine sets CUDA_VISIBLE_DEVICES=-1. The independent
        # chart environment must not inherit that process-local CPU choice.
        env = _worker_environment()
        self.process = subprocess.Popen(
            [str(_python()), "-u", str(root / "daisy_ocr/chart/worker.py")],
            cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.replies = queue.Queue()
        def read_replies(process, replies):
            try:
                for line in process.stdout:
                    replies.put(line)
            finally:
                replies.put(None)
        threading.Thread(target=read_replies, args=(self.process, self.replies), daemon=True).start()

    def analyze(self, path: Path) -> dict:
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self.start()
            try:
                self.process.stdin.write(json.dumps({"image_path": str(path.resolve())}) + "\n")
                self.process.stdin.flush()
                line = self.replies.get(timeout=int(os.environ.get("CHART_TIMEOUT", "900")))
                if line is None:
                    raise RuntimeError("도표 프로세스가 종료되었습니다. artifacts/chart-worker.log를 확인하세요.")
                reply = json.loads(line)
                if not reply.get("ok"):
                    raise RuntimeError(reply.get("error", "도표 모델 실행 실패"))
                self.ready = True
                return reply["result"]
            except queue.Empty as exc:
                self.close()
                raise RuntimeError("도표 분석 시간이 초과되었습니다. GPU 메모리와 다운로드 상태를 확인하세요.") from exc
            except (OSError, ValueError):
                self.close()
                raise


_worker = _Worker()
atexit.register(_worker.close)


def format_chart_result(result: dict) -> tuple[str, float]:
    charts = result.get("results")
    if not isinstance(charts, list) or len(charts) != 1:
        raise ValueError("잘라낸 영역 1개에 대한 도표 결과 1개가 필요합니다.")
    item = charts[0]
    data = item.get("parsed_data")
    if not isinstance(data, dict) or not str(data.get("description", "")).strip():
        raise ValueError("도표 응답에 설명이 없습니다.")
    labels = {"graph_type": "유형", "title": "제목", "axis": "축", "legend": "범례", "data": "데이터", "description": "설명"}
    text = "\n".join(f"{label}: {data[key]}" for key, label in labels.items() if str(data.get(key, "")).strip())
    score = float(item.get("confidence_score", 0))
    if not math.isfinite(score):
        raise ValueError("도표 검수 점수가 유효하지 않습니다.")
    return text + "\n검수 안내: AI 설명입니다. 원본과 수치·내용을 대조하세요.", max(0.0, min(1.0, score))


def recognize_chart_region(image, output_root: Path, *, page_index: int, region_index: int):
    if not chart_runtime_status()["enabled"]:
        raise RuntimeError("도표 인식이 비활성화되어 있습니다.")
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"page-{page_index + 1:04d}-chart-{region_index + 1:03d}.png"
    image.convert("RGB").save(path)
    result = _worker.analyze(path)
    path.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return format_chart_result(result)
