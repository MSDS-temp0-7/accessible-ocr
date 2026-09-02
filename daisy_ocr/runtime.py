"""공통 런타임 설정 — CPU 스레드 상한, 캐시, 디바이스 선택.

목적: 추론이 전 CPU 코어를 점유해 PC 전체가 멈추는 것을 방지한다.
반드시 torch/onnxruntime import **이전에** `configure_runtime()`을 호출해야
스레드 상한이 확실히 적용된다(스레드 관련 환경변수는 라이브러리 로드 시 고정됨).
"""
from __future__ import annotations

import os

_configured = False


def _default_thread_cap() -> int:
    """물리 코어의 약 절반(최소 1, 최대 4)으로 상한.

    전 코어 점유로 인한 시스템 멈춤을 막는 보수적 기본값.
    """
    cpu = os.cpu_count() or 4
    return max(1, min(4, cpu // 2))


def configure_runtime(threads: int | None = None) -> int:
    """스레드 상한과 캐시 관련 환경변수를 설정. 설정된 스레드 수를 반환.

    - OMP/MKL/OpenBLAS 스레드 환경변수(라이브러리 로드 전 설정돼야 유효)
    - HuggingFace 심링크 경고 억제
    - torch가 이미 import돼 있으면 `torch.set_num_threads`도 직접 적용
    """
    global _configured
    n = threads if threads is not None else _default_thread_cap()

    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(var, str(n))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    # torch가 이미 로드된 경우 런타임에도 반영
    import sys
    if "torch" in sys.modules:
        try:
            sys.modules["torch"].set_num_threads(n)
        except Exception:
            pass

    _configured = True
    return n


def pick_device(prefer: str = "auto") -> str:
    """사용할 디바이스 결정. 'auto'면 CUDA 가용 시 cuda, 아니면 cpu."""
    if prefer != "auto":
        return prefer
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"
