"""
services/audiveris_runner.py

이미지 파일(JPG / JPEG / PNG)을 입력받아:

1. 이미지 크기 검사
2. Audiveris 제한을 넘으면 자동 축소
3. Audiveris CLI batch 실행
4. .mxl / .omr 결과 확인
5. 결과 경로 반환

현재 개발 환경:
- macOS Apple Silicon
- Audiveris 5.10.2

향후 Docker에서는 AUDIVERIS_CMD 환경변수만 변경하면
동일한 코드를 사용할 수 있도록 구성한다.
"""

from __future__ import print_function

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None


# ============================================================
# 설정
# ============================================================

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}

# Audiveris 로그에서 확인한 최대 픽셀 수
AUDIVERIS_MAX_PIXELS = 20_000_000

# 기존 OMR 실험과 동일하게 긴 변 최대 4000px 사용
MAX_LONG_SIDE = 4000

DEFAULT_TIMEOUT_SECONDS = 600

MAC_AUDIVERIS_PATH = (
    "/Applications/Audiveris.app/"
    "Contents/MacOS/Audiveris"
)

WINDOWS_AUDIVERIS_PATHS = (
    Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    / "Audiveris" / "bin" / "Audiveris.bat",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    / "Audiveris" / "Audiveris.exe",
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Programs" / "Audiveris" / "bin" / "Audiveris.bat",
)


# ============================================================
# 예외
# ============================================================

class AudiverisError(RuntimeError):
    """Audiveris 실행 또는 결과 생성에 실패한 경우."""

    pass


# ============================================================
# Audiveris 실행 파일 탐색
# ============================================================

def resolve_audiveris_command() -> str:
    """
    Audiveris 실행 파일 경로를 결정한다.

    우선순위:
    1. AUDIVERIS_CMD 환경변수
    2. macOS 기본 설치 경로
    3. PATH의 audiveris / Audiveris
    """

    env_command = os.getenv("AUDIVERIS_CMD")

    if env_command:
        env_path = Path(env_command).expanduser()

        if env_path.exists():
            return str(env_path.resolve())

        found = shutil.which(env_command)

        if found:
            return found

        raise AudiverisError(
            "AUDIVERIS_CMD가 설정되어 있지만 "
            "실행 파일을 찾을 수 없습니다: "
            + env_command
        )

    mac_path = Path(MAC_AUDIVERIS_PATH)

    if mac_path.exists():
        return str(mac_path)

    for windows_path in WINDOWS_AUDIVERIS_PATHS:
        if windows_path.exists():
            return str(windows_path.resolve())

    found = shutil.which("audiveris")

    if found:
        return found

    found = shutil.which("Audiveris")

    if found:
        return found

    raise AudiverisError(
        "Audiveris 실행 파일을 찾을 수 없습니다.\n"
        "Windows에서는 Java와 Audiveris를 설치한 뒤,\n"
        "AUDIVERIS_CMD 환경변수에 Audiveris.bat 또는 실행 파일 경로를 "
        "설정해주세요. macOS에서는 Audiveris.app을 설치합니다."
    )


# ============================================================
# 이미지 확인
# ============================================================

def validate_image_path(image_path: Path) -> None:
    """
    입력 파일 존재 및 확장자를 검사한다.
    """

    if not image_path.exists():
        raise AudiverisError(
            "입력 이미지를 찾을 수 없습니다: "
            + str(image_path)
        )

    if not image_path.is_file():
        raise AudiverisError(
            "입력 경로가 파일이 아닙니다: "
            + str(image_path)
        )

    extension = image_path.suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise AudiverisError(
            "지원하지 않는 이미지 형식입니다: "
            + extension
            + "\n현재 지원: JPG, JPEG, PNG"
        )


# ============================================================
# 이미지 전처리
# ============================================================

def prepare_image(
    source_path: Path,
    input_dir: Path,
) -> Dict:
    """
    Audiveris 입력용 이미지를 준비한다.

    조건:
    - 총 픽셀 수 > 20,000,000
    - 또는 긴 변 > 4000

    둘 중 하나라도 해당하면 비율을 유지하면서 축소한다.

    원본 이미지는 변경하지 않는다.
    """

    if Image is None:
        raise AudiverisError(
            "Pillow가 설치되어 있지 않습니다.\n"
            "다음 명령으로 설치해주세요:\n"
            "python -m pip install Pillow"
        )

    input_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with Image.open(source_path) as opened_image:
            image = ImageOps.exif_transpose(opened_image)

            original_width, original_height = image.size

            original_pixels = (
                original_width * original_height
            )

            original_long_side = max(
                original_width,
                original_height,
            )

            needs_resize = (
                original_pixels > AUDIVERIS_MAX_PIXELS
                or original_long_side > MAX_LONG_SIDE
            )

            # ------------------------------------------------
            # 축소가 필요하지 않은 경우
            # ------------------------------------------------

            if not needs_resize:
                prepared_path = (
                    input_dir / source_path.name
                )

                shutil.copy2(
                    source_path,
                    prepared_path,
                )

                return {
                    "sourcePath": str(source_path),
                    "preparedPath": str(prepared_path),
                    "resized": False,

                    "originalWidth": original_width,
                    "originalHeight": original_height,
                    "originalPixels": original_pixels,

                    "preparedWidth": original_width,
                    "preparedHeight": original_height,
                    "preparedPixels": original_pixels,
                }

            # ------------------------------------------------
            # 축소 비율 계산
            # ------------------------------------------------

            long_side_scale = (
                float(MAX_LONG_SIDE)
                / float(original_long_side)
            )

            pixel_scale = math.sqrt(
                float(AUDIVERIS_MAX_PIXELS)
                / float(original_pixels)
            )

            scale = min(
                1.0,
                long_side_scale,
                pixel_scale,
            )

            new_width = max(
                1,
                int(
                    math.floor(
                        original_width * scale
                    )
                ),
            )

            new_height = max(
                1,
                int(
                    math.floor(
                        original_height * scale
                    )
                ),
            )

            # Pillow 버전 호환
            if hasattr(Image, "Resampling"):
                resample_filter = (
                    Image.Resampling.LANCZOS
                )
            else:
                resample_filter = Image.LANCZOS

            resized_image = image.resize(
                (
                    new_width,
                    new_height,
                ),
                resample_filter,
            )

            # Audiveris 입력 안정성을 위해 PNG로 저장
            # stem은 유지해서 결과명도 동일하게 맞춘다.
            prepared_path = (
                input_dir
                / (
                    source_path.stem
                    + ".png"
                )
            )

            # 다양한 이미지 모드 처리
            if resized_image.mode not in (
                "RGB",
                "L",
                "RGBA",
            ):
                resized_image = (
                    resized_image.convert("RGB")
                )

            resized_image.save(
                prepared_path,
                format="PNG",
                optimize=True,
            )

            prepared_pixels = (
                new_width * new_height
            )

            return {
                "sourcePath": str(source_path),
                "preparedPath": str(prepared_path),
                "resized": True,

                "originalWidth": original_width,
                "originalHeight": original_height,
                "originalPixels": original_pixels,

                "preparedWidth": new_width,
                "preparedHeight": new_height,
                "preparedPixels": prepared_pixels,
            }

    except AudiverisError:
        raise

    except Exception as exc:
        raise AudiverisError(
            "이미지 전처리에 실패했습니다: "
            + str(exc)
        )


# ============================================================
# 출력 파일 검색
# ============================================================

def find_output_file(
    run_dir: Path,
    stem: str,
    extension: str,
) -> Optional[Path]:
    """
    Audiveris 출력 폴더에서 결과 파일을 찾는다.

    우선 정확히:
        <stem>.mxl
        <stem>.omr

    을 찾고, 없으면 동일 확장자의 결과를 검색한다.
    """

    exact_path = (
        run_dir / (stem + extension)
    )

    if exact_path.exists():
        return exact_path.resolve()

    candidates = list(
        run_dir.rglob(
            "*" + extension
        )
    )

    candidates = [
        path
        for path in candidates
        if path.is_file()
    ]

    if not candidates:
        return None

    # stem이 같은 결과 우선
    stem_matches = [
        path
        for path in candidates
        if path.stem == stem
    ]

    if len(stem_matches) == 1:
        return stem_matches[0].resolve()

    if len(candidates) == 1:
        return candidates[0].resolve()

    return None


# ============================================================
# 로그 저장
# ============================================================

def save_process_logs(
    run_dir: Path,
    stdout_text: str,
    stderr_text: str,
) -> Dict:
    """
    subprocess stdout/stderr를 디버깅용으로 저장한다.
    """

    stdout_path = (
        run_dir / "runner_stdout.log"
    )

    stderr_path = (
        run_dir / "runner_stderr.log"
    )

    stdout_path.write_text(
        stdout_text or "",
        encoding="utf-8",
    )

    stderr_path.write_text(
        stderr_text or "",
        encoding="utf-8",
    )

    return {
        "stdout": str(stdout_path.resolve()),
        "stderr": str(stderr_path.resolve()),
    }


# ============================================================
# Audiveris 실행
# ============================================================

def run_audiveris(
    image_path,
    output_root="audiveris_runs",
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
) -> Dict:
    """
    이미지 하나를 Audiveris로 처리한다.

    Parameters
    ----------
    image_path:
        JPG / JPEG / PNG 파일

    output_root:
        작업 결과를 저장할 상위 디렉터리

    timeout_seconds:
        Audiveris 최대 실행 시간

    Returns
    -------
    dict
        mxlPath
        omrPath
        runDir
        preprocess
        audiveris 정보
    """

    source_path = (
        Path(image_path)
        .expanduser()
        .resolve()
    )

    validate_image_path(source_path)

    output_root = (
        Path(output_root)
        .expanduser()
        .resolve()
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 요청별 독립 작업 폴더
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%dT%H%M%S"
    )

    run_id = uuid4().hex[:8]

    run_dir = (
        output_root
        / (
            source_path.stem
            + "_"
            + timestamp
            + "_"
            + run_id
        )
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    input_dir = run_dir / "_input"

    # --------------------------------------------------------
    # 이미지 준비
    # --------------------------------------------------------

    preprocess_info = prepare_image(
        source_path=source_path,
        input_dir=input_dir,
    )

    prepared_path = Path(
        preprocess_info["preparedPath"]
    )

    # --------------------------------------------------------
    # Audiveris 실행 파일
    # --------------------------------------------------------

    audiveris_command = (
        resolve_audiveris_command()
    )

    command = [
        audiveris_command,

        "-batch",
        "-transcribe",
        "-export",
        "-save",

        "-output",
        str(run_dir),

        "--",
        str(prepared_path),
    ]

    # --------------------------------------------------------
    # 실행
    # --------------------------------------------------------

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:
        raise AudiverisError(
            "Audiveris 실행 시간이 "
            + str(timeout_seconds)
            + "초를 초과했습니다.\n"
            + "작업 폴더: "
            + str(run_dir)
        ) from exc

    except Exception as exc:
        raise AudiverisError(
            "Audiveris 실행 중 오류가 발생했습니다: "
            + str(exc)
        ) from exc

    # --------------------------------------------------------
    # 로그 저장
    # --------------------------------------------------------

    log_paths = save_process_logs(
        run_dir=run_dir,
        stdout_text=completed.stdout,
        stderr_text=completed.stderr,
    )

    # --------------------------------------------------------
    # return code 확인
    # --------------------------------------------------------

    if completed.returncode != 0:
        combined_log = (
            (completed.stdout or "")
            + "\n"
            + (completed.stderr or "")
        )

        last_lines = "\n".join(
            combined_log.splitlines()[-30:]
        )

        raise AudiverisError(
            "Audiveris가 정상 종료되지 않았습니다.\n"
            "Return code: "
            + str(completed.returncode)
            + "\n"
            + "작업 폴더: "
            + str(run_dir)
            + "\n\n"
            + "마지막 로그:\n"
            + last_lines
        )

    # --------------------------------------------------------
    # 결과 파일 확인
    # --------------------------------------------------------

    output_stem = prepared_path.stem

    mxl_path = find_output_file(
        run_dir=run_dir,
        stem=output_stem,
        extension=".mxl",
    )

    omr_path = find_output_file(
        run_dir=run_dir,
        stem=output_stem,
        extension=".omr",
    )

    if mxl_path is None:
        raise AudiverisError(
            "Audiveris는 종료됐지만 "
            ".mxl 파일이 생성되지 않았습니다.\n"
            "작업 폴더: "
            + str(run_dir)
        )

    if omr_path is None:
        raise AudiverisError(
            "Audiveris는 종료됐지만 "
            ".omr 파일이 생성되지 않았습니다.\n"
            "작업 폴더: "
            + str(run_dir)
        )

    # --------------------------------------------------------
    # 최종 결과
    # --------------------------------------------------------

    return {
        "success": True,

        "sourceImage": str(source_path),

        "runDir": str(run_dir.resolve()),

        "mxlPath": str(mxl_path),

        "omrPath": str(omr_path),

        "preprocess": preprocess_info,

        "audiveris": {
            "command": audiveris_command,
            "returnCode": completed.returncode,
            "timeoutSeconds": timeout_seconds,
        },

        "logs": log_paths,
    }


# ============================================================
# CLI
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "이미지를 Audiveris로 처리하여 "
            ".mxl + .omr을 생성합니다."
        )
    )

    parser.add_argument(
        "image",
        help="입력 JPG / JPEG / PNG 경로",
    )

    parser.add_argument(
        "--output-dir",
        default="audiveris_runs",
        help=(
            "결과 상위 폴더 "
            "(기본: audiveris_runs)"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "Audiveris timeout 초 "
            "(기본: 600)"
        ),
    )

    args = parser.parse_args()

    try:
        result = run_audiveris(
            image_path=args.image,
            output_root=args.output_dir,
            timeout_seconds=args.timeout,
        )

        print()
        print("=" * 70)
        print("AUDIVERIS SUCCESS")
        print("=" * 70)

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

        return 0

    except AudiverisError as exc:
        print()
        print("=" * 70)
        print("AUDIVERIS FAILED")
        print("=" * 70)
        print(str(exc))

        return 1


if __name__ == "__main__":
    sys.exit(main())
