"""
api/music_api.py

OCR-DAISY 악보 분석용 FastAPI 서버

주요 API
--------
GET  /api/music/health
POST /api/music/recognize

전체 흐름
---------
악보 이미지
    ↓
FastAPI
    ↓
music_recognizer.py
    ↓
audiveris_runner.py
    ↓
Audiveris
    ↓
MusicXML(.mxl) + OMR(.omr)
    ↓
music_pipeline.py
    ↓
MusicContent JSON
"""

import os

from functools import partial
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    UploadFile,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from fastapi.responses import (
    JSONResponse,
)

from starlette.concurrency import (
    run_in_threadpool,
)


# ============================================================
# 프로젝트 내부 모듈
# ============================================================

from services.audiveris_runner import (
    AudiverisError,
    resolve_audiveris_command,
)

from services.music_recognizer import (
    MusicRecognitionError,
    recognize_music,
)


# ============================================================
# 프로젝트 기본 경로
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


# ============================================================
# Upload 저장 폴더
# ============================================================

UPLOAD_ROOT = Path(
    os.getenv(
        "MUSIC_UPLOAD_ROOT",
        str(
            BASE_DIR
            / "api_uploads"
        ),
    )
).expanduser().resolve()


# ============================================================
# Music API 결과 저장 폴더
# ============================================================

RECOGNITION_ROOT = Path(
    os.getenv(
        "MUSIC_RECOGNITION_ROOT",
        str(
            BASE_DIR
            / "music_api_runs"
        ),
    )
).expanduser().resolve()


# ============================================================
# Audiveris Timeout
# ============================================================

AUDIVERIS_TIMEOUT = int(
    os.getenv(
        "AUDIVERIS_TIMEOUT",
        "600",
    )
)


# ============================================================
# 최대 Upload 크기
#
# 기본:
# 50 MB
#
# 이미지 pixel 제한 / resize는
# audiveris_runner.py가 추가로 처리한다.
# ============================================================

MAX_UPLOAD_BYTES = int(
    os.getenv(
        "MAX_MUSIC_UPLOAD_BYTES",
        str(
            50
            * 1024
            * 1024
        ),
    )
)


# ============================================================
# Ollama
# ============================================================

OLLAMA_BASE_URL = (
    os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )
    .rstrip("/")
)


# ============================================================
# 지원 이미지 확장자
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


# ============================================================
# CORS
#
# 개발 기본값:
# React 3000
# Vite 5173
# ============================================================

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,"
    "http://127.0.0.1:3000,"
    "http://localhost:5173,"
    "http://127.0.0.1:5173"
)


CORS_ORIGINS = [
    origin.strip()
    for origin
    in os.getenv(
        "CORS_ORIGINS",
        DEFAULT_CORS_ORIGINS,
    ).split(",")
    if origin.strip()
]


# ============================================================
# 런타임 폴더 생성
# ============================================================

UPLOAD_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

RECOGNITION_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title=(
        "OCR-DAISY Music API"
    ),

    version="0.1.0",

    description=(
        "악보 이미지를 Audiveris로 인식하고 "
        "MusicXML, 접근성 설명, Confidence, "
        "Review, Grounded Summary를 생성하는 API"
    ),
)


# ============================================================
# CORS Middleware
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=(
        CORS_ORIGINS
    ),

    allow_credentials=True,

    allow_methods=[
        "GET",
        "POST",
    ],

    allow_headers=[
        "*",
    ],
)


# ============================================================
# Ollama 상태 확인
# ============================================================

def is_ollama_reachable():
    """
    Ollama API가 현재 응답하는지 확인한다.

    Ollama가 꺼져 있어도
    Grounded Summary는 deterministic fallback이 가능하므로
    전체 Music API를 DOWN 처리하지 않는다.
    """

    try:

        with urlopen(
            (
                OLLAMA_BASE_URL
                + "/api/tags"
            ),
            timeout=2,
        ) as response:

            return (
                200
                <= response.status
                < 300
            )

    except (
        URLError,
        TimeoutError,
        OSError,
    ):

        return False


# ============================================================
# 파일 확장자 검사
# ============================================================

def get_upload_extension(
    filename: Optional[str],
):
    """
    업로드된 파일 이름에서 확장자를 추출하고
    지원 형식인지 검사한다.
    """

    if not filename:

        raise ValueError(
            "파일 이름이 없습니다."
        )

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if (
        extension
        not in SUPPORTED_EXTENSIONS
    ):

        raise ValueError(
            "지원하지 않는 파일 형식입니다. "
            "JPG, JPEG, PNG만 지원합니다."
        )

    return extension


# ============================================================
# Upload 파일 저장
# ============================================================

async def save_upload_file(
    upload_file: UploadFile,
    destination: Path,
):
    """
    업로드 파일을 1MB chunk 단위로 저장한다.

    전체 파일을 메모리에 한 번에 올리지 않는다.

    MAX_UPLOAD_BYTES보다 큰 경우 중단한다.
    """

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    written_bytes = 0

    chunk_size = (
        1024
        * 1024
    )

    try:

        with destination.open(
            "wb"
        ) as output:

            while True:

                chunk = (
                    await upload_file.read(
                        chunk_size
                    )
                )

                if not chunk:
                    break

                written_bytes += (
                    len(chunk)
                )

                if (
                    written_bytes
                    > MAX_UPLOAD_BYTES
                ):

                    raise OverflowError(
                        "업로드 파일이 허용 용량을 "
                        "초과했습니다."
                    )

                output.write(
                    chunk
                )

    except Exception:

        if destination.exists():

            destination.unlink(
                missing_ok=True
            )

        raise

    finally:

        await upload_file.close()

    return written_bytes


# ============================================================
# Root
# ============================================================

@app.get("/")
def root():

    return {

        "service":
            "OCR-DAISY Music API",

        "version":
            "0.1.0",

        "status":
            "running",
    }


# ============================================================
# Health Check
# ============================================================

@app.get(
    "/api/music/health"
)
def health():
    """
    Music API 의존성 상태 확인.

    healthy
        Audiveris O
        Ollama O

    degraded
        Audiveris O
        Ollama X
        → deterministic fallback 가능

    unhealthy
        Audiveris X
    """

    audiveris_available = False

    audiveris_command = None


    # --------------------------------------------------------
    # Audiveris 확인
    # --------------------------------------------------------

    try:

        audiveris_command = (
            resolve_audiveris_command()
        )

        audiveris_available = True

    except AudiverisError:

        audiveris_available = False


    # --------------------------------------------------------
    # Ollama 확인
    # --------------------------------------------------------

    ollama_available = (
        is_ollama_reachable()
    )


    # --------------------------------------------------------
    # 전체 상태
    # --------------------------------------------------------

    if not audiveris_available:

        service_status = (
            "unhealthy"
        )

    elif not ollama_available:

        service_status = (
            "degraded"
        )

    else:

        service_status = (
            "healthy"
        )


    return {

        "status":
            service_status,

        "audiveris": {

            "available":
                audiveris_available,

            "command":
                audiveris_command,
        },

        "ollama": {

            "available":
                ollama_available,

            "baseUrl":
                OLLAMA_BASE_URL,

            "fallbackAvailable":
                True,
        },
    }


# ============================================================
# Music Recognition API
# ============================================================

@app.post(
    "/api/music/recognize"
)
async def recognize(
    image_file: UploadFile = File(...),
):
    """
    악보 이미지 하나를 업로드하여
    최종 MusicContent를 생성한다.

    Request
    -------
    multipart/form-data

    image_file:
        JPG / JPEG / PNG


    Response
    --------
    {
        "success": true,
        "requestId": "...",
        "musicContent": {...}
    }
    """


    # ========================================================
    # 1. 확장자 검사
    # ========================================================

    try:

        extension = (
            get_upload_extension(
                image_file.filename
            )
        )

    except ValueError as exc:

        return JSONResponse(

            status_code=400,

            content={

                "success":
                    False,

                "error": {

                    "code":
                        "INVALID_FILE_TYPE",

                    "message":
                        str(exc),
                },
            },
        )


    # ========================================================
    # 2. Request ID 생성
    # ========================================================

    request_id = (
        uuid4().hex
    )


    # ========================================================
    # 3. Upload 폴더
    # ========================================================

    request_upload_dir = (
        UPLOAD_ROOT
        / request_id
    )

    request_upload_dir.mkdir(
        parents=True,
        exist_ok=False,
    )


    upload_path = (
        request_upload_dir
        / (
            "input"
            + extension
        )
    )


    # ========================================================
    # 4. Upload 저장
    # ========================================================

    try:

        upload_size = (
            await save_upload_file(
                upload_file=(
                    image_file
                ),

                destination=(
                    upload_path
                ),
            )
        )


    except OverflowError:

        return JSONResponse(

            status_code=413,

            content={

                "success":
                    False,

                "requestId":
                    request_id,

                "error": {

                    "code":
                        "FILE_TOO_LARGE",

                    "message":
                        (
                            "업로드 가능한 최대 "
                            "파일 크기를 초과했습니다."
                        ),

                    "maxBytes":
                        MAX_UPLOAD_BYTES,
                },
            },
        )


    except Exception as exc:

        return JSONResponse(

            status_code=500,

            content={

                "success":
                    False,

                "requestId":
                    request_id,

                "error": {

                    "code":
                        "UPLOAD_SAVE_FAILED",

                    "message":
                        str(exc),
                },
            },
        )


    # ========================================================
    # 5. Music Recognition
    #
    # Audiveris/music21/LLM 분석은 시간이 오래 걸릴 수 있으므로
    # FastAPI event loop에서 직접 실행하지 않는다.
    # ========================================================

    recognition_job = partial(

        recognize_music,

        image_path=(
            upload_path
        ),

        output_root=(
            RECOGNITION_ROOT
            / request_id
        ),

        audiveris_timeout=(
            AUDIVERIS_TIMEOUT
        ),
    )


    try:

        result = (
            await run_in_threadpool(
                recognition_job
            )
        )


    # ========================================================
    # Music Recognition 실패
    # ========================================================

    except MusicRecognitionError as exc:

        message = (
            str(exc)
        )

        lower_message = (
            message.lower()
        )

        if (
            "timeout"
            in lower_message
            or "시간 초과"
            in message
        ):

            error_code = (
                "MUSIC_RECOGNITION_TIMEOUT"
            )

            status_code = 504

        else:

            error_code = (
                "MUSIC_RECOGNITION_FAILED"
            )

            status_code = 422


        return JSONResponse(

            status_code=(
                status_code
            ),

            content={

                "success":
                    False,

                "requestId":
                    request_id,

                "error": {

                    "code":
                        error_code,

                    "message":
                        message,
                },
            },
        )


    # ========================================================
    # 예상하지 못한 서버 오류
    # ========================================================

    except Exception as exc:

        return JSONResponse(

            status_code=500,

            content={

                "success":
                    False,

                "requestId":
                    request_id,

                "error": {

                    "code":
                        "INTERNAL_SERVER_ERROR",

                    "message":
                        str(exc),
                },
            },
        )


    # ========================================================
    # 6. 성공 Response
    # ========================================================

    return {

        "success":
            True,

        "requestId":
            request_id,

        "upload": {

            "filename":
                image_file.filename,

            "sizeBytes":
                upload_size,
        },

        "musicContent":
            result.get(
                "musicContent"
            ),

        # --------------------------------------------
        # 아래 path들은 현재 개발/디버깅용.
        #
        # 운영에서는 일반 사용자에게 노출하지 않고
        # artifact ID / download endpoint 방식으로
        # 변경하는 것을 권장한다.
        # --------------------------------------------

        "outputPath":
            result.get(
                "outputPath"
            ),

        "runDir":
            result.get(
                "runDir"
            ),
    }