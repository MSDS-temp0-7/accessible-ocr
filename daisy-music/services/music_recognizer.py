"""
services/music_recognizer.py

JPG / JPEG / PNG 악보 이미지를 입력받아

1. Audiveris 자동 실행
2. MusicXML(.mxl) + OMR(.omr) 생성
3. 기존 music_pipeline 실행
4. 풀스택 연동용 MusicContent JSON 생성

최종 흐름:

Image
  ↓
Audiveris
  ↓
MusicXML + OMR
  ↓
music_pipeline
  ↓
MusicContent JSON
"""

from __future__ import print_function

import argparse
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

from pathlib import Path
from typing import Any, Dict, Optional


# ============================================================
# 프로젝트 내부 import
# ============================================================

try:
    from .audiveris_runner import (
        run_audiveris,
        AudiverisError,
    )

    from .music_pipeline import analyze_music

except ImportError:
    from audiveris_runner import (
        run_audiveris,
        AudiverisError,
    )

    from music_pipeline import analyze_music


# ============================================================
# 예외
# ============================================================

class MusicRecognitionError(RuntimeError):
    """악보 전체 인식 파이프라인 실패."""

    pass


# ============================================================
# JSON 직렬화 보조
# ============================================================

def make_json_safe(value: Any) -> Any:
    """
    Path 등 JSON 직렬화가 되지 않는 객체를 변환한다.
    """

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            make_json_safe(item)
            for item in value
        ]

    return value


# ============================================================
# XML tag namespace 제거
# ============================================================

def local_name(tag: str) -> str:
    """
    XML namespace가 포함된 tag에서
    실제 tag 이름만 반환한다.
    """

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


# ============================================================
# .mxl → 내부 MusicXML 문자열
# ============================================================

def read_musicxml_from_mxl(
    mxl_path: Path,
) -> str:
    """
    Audiveris가 생성한 .mxl에서 실제 MusicXML을 읽는다.

    일반적인 compressed MusicXML:
        META-INF/container.xml
        → rootfile
        → 실제 XML

    container 정보가 없으면
    META-INF 외 첫 번째 XML을 사용한다.
    """

    mxl_path = mxl_path.resolve()

    if not mxl_path.exists():
        raise MusicRecognitionError(
            "MusicXML 파일을 찾을 수 없습니다: "
            + str(mxl_path)
        )

    try:
        with zipfile.ZipFile(
            mxl_path,
            "r",
        ) as archive:

            names = archive.namelist()

            rootfile_path: Optional[str] = None

            # ----------------------------------------------
            # 1. META-INF/container.xml 확인
            # ----------------------------------------------

            container_name = (
                "META-INF/container.xml"
            )

            if container_name in names:
                try:
                    container_bytes = archive.read(
                        container_name
                    )

                    container_root = ET.fromstring(
                        container_bytes
                    )

                    for element in container_root.iter():

                        if (
                            local_name(element.tag)
                            == "rootfile"
                        ):
                            candidate = (
                                element.attrib.get(
                                    "full-path"
                                )
                            )

                            if candidate:
                                rootfile_path = candidate
                                break

                except Exception:
                    rootfile_path = None

            # ----------------------------------------------
            # 2. container.xml에서 못 찾은 경우
            # ----------------------------------------------

            if (
                rootfile_path is None
                or rootfile_path not in names
            ):
                xml_candidates = [
                    name
                    for name in names
                    if name.lower().endswith(".xml")
                    and not name.startswith("META-INF/")
                ]

                if not xml_candidates:
                    raise MusicRecognitionError(
                        ".mxl 내부에 MusicXML 파일이 "
                        "존재하지 않습니다: "
                        + str(mxl_path)
                    )

                rootfile_path = xml_candidates[0]

            # ----------------------------------------------
            # 3. 실제 XML 읽기
            # ----------------------------------------------

            xml_bytes = archive.read(
                rootfile_path
            )

            try:
                return xml_bytes.decode("utf-8")

            except UnicodeDecodeError:
                return xml_bytes.decode(
                    "utf-8",
                    errors="replace",
                )

    except zipfile.BadZipFile:

        # 혹시 확장자는 .mxl이지만
        # plain XML인 경우 방어적으로 처리
        try:
            return mxl_path.read_text(
                encoding="utf-8",
            )

        except Exception as exc:
            raise MusicRecognitionError(
                "MusicXML을 읽을 수 없습니다: "
                + str(exc)
            ) from exc


# ============================================================
# MusicContent 생성
# ============================================================

def build_music_content(
    pipeline_result: Dict,
    audiveris_result: Dict,
    pipeline_output_path,
) -> Dict:
    """
    기존 music_pipeline 결과를
    풀스택/IR 연동용 MusicContent 구조로 변환한다.
    """

    mxl_path = Path(
        audiveris_result["mxlPath"]
    )

    omr_path = Path(
        audiveris_result["omrPath"]
    )

    music_xml = read_musicxml_from_mxl(
        mxl_path
    )

    # --------------------------------------------------------
    # 기존 pipeline 결과
    # --------------------------------------------------------

    status = pipeline_result.get(
        "status",
        "UNKNOWN",
    )

    summary = pipeline_result.get(
        "summary"
    )

    spoken_text = pipeline_result.get(
        "spokenText"
    )

    confidence = pipeline_result.get(
        "confidence"
    )

    review = pipeline_result.get(
        "review"
    )

    features = pipeline_result.get(
        "features"
    )

    mapping = pipeline_result.get(
        "mapping"
    )

    metadata = pipeline_result.get(
        "metadata",
        {},
    )

    measures = pipeline_result.get(
        "measures",
        [],
    )

    # --------------------------------------------------------
    # MusicContent
    # --------------------------------------------------------

    music_content = {

        "type": "music",

        "status": status,

        # ====================================================
        # 원본 음악 구조
        # ====================================================

        "musicXml": music_xml,

        "metadata": metadata,

        # ====================================================
        # 접근성 텍스트
        # ====================================================

        "spokenText": spoken_text,

        "summary": summary,

        "measures": measures,

        # ====================================================
        # 분석 결과
        # ====================================================

        "features": features,

        "confidence": confidence,

        "review": review,

        "mapping": mapping,

        # ====================================================
        # 향후 접근성 출력
        # ====================================================

        # 점자악보
        "brailleMusic": None,

        # 최종 문서 serializer
        "outputs": {

            "daisy": None,

            "hwp": None,
        },

        # 재생 기능은 MusicContent IR 이후 구현 예정
        "playback": None,

        # ====================================================
        # Backend 내부 artifact
        # ====================================================

        "artifacts": {

            "sourceImage":
                audiveris_result.get(
                    "sourceImage"
                ),

            "musicXmlPath":
                str(mxl_path),

            "omrProjectPath":
                str(omr_path),

            "pipelineOutputPath":
                (
                    str(pipeline_output_path)
                    if pipeline_output_path
                    else None
                ),
        },

        # ====================================================
        # Audiveris 실행 정보
        # ====================================================

        "recognition": {

            "preprocess":
                audiveris_result.get(
                    "preprocess"
                ),

            "audiveris":
                audiveris_result.get(
                    "audiveris"
                ),

            "logs":
                audiveris_result.get(
                    "logs"
                ),
        },
    }

    return make_json_safe(
        music_content
    )


# ============================================================
# 전체 이미지 → MusicContent
# ============================================================

def recognize_music(
    image_path,
    output_root="music_recognition_runs",
    audiveris_timeout=600,
) -> Dict:
    """
    이미지 하나를 입력받아 최종 MusicContent를 반환한다.

    Parameters
    ----------
    image_path:
        JPG / JPEG / PNG

    output_root:
        전체 작업 결과 저장 폴더

    audiveris_timeout:
        Audiveris timeout

    Returns
    -------
    dict
        success
        musicContent
        outputPath
        runDir
    """

    image_path = (
        Path(image_path)
        .expanduser()
        .resolve()
    )

    output_root = (
        Path(output_root)
        .expanduser()
        .resolve()
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # 1. Audiveris
    # ========================================================

    try:
        audiveris_result = run_audiveris(
            image_path=image_path,
            output_root=output_root,
            timeout_seconds=audiveris_timeout,
        )

    except AudiverisError as exc:
        raise MusicRecognitionError(
            "Audiveris 인식 실패:\n"
            + str(exc)
        ) from exc

    mxl_path = Path(
        audiveris_result["mxlPath"]
    )

    omr_path = Path(
        audiveris_result["omrPath"]
    )

    run_dir = Path(
        audiveris_result["runDir"]
    )

    # ========================================================
    # 2. 기존 Music Pipeline
    # ========================================================

    try:
        (
            pipeline_result,
            pipeline_output_path,
        ) = analyze_music(
            mxl_path=mxl_path,
            omr_path=omr_path,
        )

    except Exception as exc:
        raise MusicRecognitionError(
            "Music Pipeline 실행 실패:\n"
            + str(exc)
        ) from exc

    # ========================================================
    # 3. MusicContent
    # ========================================================

    music_content = build_music_content(
        pipeline_result=pipeline_result,
        audiveris_result=audiveris_result,
        pipeline_output_path=(
            pipeline_output_path
        ),
    )

    # ========================================================
    # 4. 최종 JSON 저장
    # ========================================================

    output_path = (
        run_dir
        / "music_content.json"
    )

    output_data = {

        "success": True,

        "musicContent": music_content,
    }

    output_path.write_text(
        json.dumps(
            output_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {

        "success": True,

        "musicContent":
            music_content,

        "outputPath":
            str(output_path.resolve()),

        "runDir":
            str(run_dir.resolve()),
    }


# ============================================================
# CLI 출력 요약
# ============================================================

def print_result(
    result: Dict,
) -> None:

    music_content = result[
        "musicContent"
    ]

    print()
    print("=" * 70)
    print("MUSIC RECOGNITION SUCCESS")
    print("=" * 70)

    print(
        "Status:",
        music_content.get(
            "status"
        ),
    )

    print()

    print(
        "Review:",
        music_content.get(
            "review"
        ),
    )

    print()

    print(
        "Confidence:",
        music_content.get(
            "confidence"
        ),
    )

    print()

    print("Summary:")

    summary = music_content.get(
        "summary"
    )

    if isinstance(
        summary,
        dict,
    ):
        print(
            summary.get(
                "text"
            )
        )

    else:
        print(summary)

    print()

    print(
        "MXL:",
        music_content[
            "artifacts"
        ].get(
            "musicXmlPath"
        ),
    )

    print(
        "OMR:",
        music_content[
            "artifacts"
        ].get(
            "omrProjectPath"
        ),
    )

    print(
        "MusicContent JSON:",
        result.get(
            "outputPath"
        ),
    )


# ============================================================
# CLI
# ============================================================

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "악보 이미지를 입력받아 "
            "Audiveris + Music Pipeline을 실행하고 "
            "MusicContent JSON을 생성합니다."
        )
    )

    parser.add_argument(
        "image",
        help=(
            "입력 JPG / JPEG / PNG"
        ),
    )

    parser.add_argument(
        "--output-dir",
        default="music_recognition_runs",
        help=(
            "결과 저장 폴더 "
            "(기본: music_recognition_runs)"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help=(
            "Audiveris timeout 초 "
            "(기본: 600)"
        ),
    )

    args = parser.parse_args()

    try:
        result = recognize_music(
            image_path=args.image,
            output_root=args.output_dir,
            audiveris_timeout=args.timeout,
        )

        print_result(result)

        return 0

    except MusicRecognitionError as exc:

        print()
        print("=" * 70)
        print("MUSIC RECOGNITION FAILED")
        print("=" * 70)

        print(str(exc))

        return 1


if __name__ == "__main__":
    sys.exit(main())