from pathlib import Path
import json
import subprocess
import sys

# ============================================================
# Local service imports
#
# 두 실행 방식 모두 지원:
#
# 1. python services/music_pipeline.py
# 2. from services.music_pipeline import analyze_music
# ============================================================

try:
    # package 형태로 import할 때
    from .music_describer import MusicDescriber
    from .confidence_enricher import enrich_confidence
    from .music_feature_analyzer import analyze_music_features
    from .local_llm_summarizer import summarize_music

except ImportError:
    # 파일을 직접 실행할 때
    from music_describer import MusicDescriber
    from confidence_enricher import enrich_confidence
    from music_feature_analyzer import analyze_music_features
    from local_llm_summarizer import summarize_music


# ============================================================
# 기본 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
SERVICES_DIR = BASE_DIR / "services"

AUDIVERIS_DIR = BASE_DIR / "audiveris_output"
PARSED_DIR = BASE_DIR / "parsed_output"
CONFIDENCE_DIR = BASE_DIR / "confidence_output"
FEATURE_DIR = BASE_DIR / "feature_output"
SPOKEN_DIR = BASE_DIR / "spoken_output"
SUMMARY_DIR = BASE_DIR / "summary_output"
PIPELINE_DIR = BASE_DIR / "pipeline_output"


for directory in [
    PARSED_DIR,
    CONFIDENCE_DIR,
    FEATURE_DIR,
    SPOKEN_DIR,
    SUMMARY_DIR,
    PIPELINE_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# JSON Utility
# ============================================================

def load_json(path: Path):
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def save_json(data, path: Path):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# Stage 1
# MusicXML → MusicStructure JSON
# ============================================================

def run_musicxml_parser(
    mxl_path: Path,
):
    """
    MusicXML → MusicStructure JSON
    """

    name = mxl_path.stem

    output_path = (
        PARSED_DIR
        / f"{name}.json"
    )

    parser_script = (
        SERVICES_DIR
        / "musicxml_parser.py"
    )

    print("MusicXML Parser 실행")

    command = [
        sys.executable,
        str(parser_script),
        str(mxl_path),
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print()
        print("MusicXML Parser stderr:")
        print(result.stderr)

        raise RuntimeError(
            "MusicXML Parser 실행 실패"
        )

    if not output_path.exists():
        raise FileNotFoundError(
            f"Parser 결과 JSON 없음: "
            f"{output_path}"
        )

    structure = load_json(
        output_path
    )

    return (
        output_path,
        structure,
    )


# ============================================================
# Stage 2
# Confidence / Review
# ============================================================

def run_confidence(
    parsed_json_path: Path,
    omr_path: Path,
):
    """
    Audiveris .omr의 symbol confidence를
    MusicStructure에 연결한다.

    실제 confidence_enricher.py 함수:
    enrich_confidence(
        parsed_json_path,
        omr_path,
        output_path,
    )
    """

    name = parsed_json_path.stem

    output_path = (
        CONFIDENCE_DIR
        / f"{name}.json"
    )

    result = enrich_confidence(
        parsed_json_path,
        omr_path,
        output_path,
    )

    # enrich_confidence()가 dict를 반환하는 경우
    if isinstance(
        result,
        dict,
    ):
        structure = result

    # 파일만 저장하고 None을 반환하는 경우
    elif output_path.exists():
        structure = load_json(
            output_path
        )

    else:
        raise RuntimeError(
            "Confidence 결과를 "
            "생성하지 못했습니다: "
            f"{output_path}"
        )

    return (
        output_path,
        structure,
    )


# ============================================================
# Stage 3
# Feature Analysis
# ============================================================

def run_feature_analysis(
    structure,
    name,
):
    """
    MIDI-PHOR-inspired
    symbolic music feature 분석.
    """

    output_path = (
        FEATURE_DIR
        / f"{name}.json"
    )

    features = analyze_music_features(
        structure
    )

    save_json(
        features,
        output_path,
    )

    return (
        output_path,
        features,
    )


# ============================================================
# Stage 4
# SpokenText
# ============================================================

def run_describer(
    confidence_json_path: Path,
):
    """
    Rule-based 상세 악보 읽기 생성.
    """

    name = confidence_json_path.stem

    output_path = (
        SPOKEN_DIR
        / f"{name}.txt"
    )

    describer = MusicDescriber(
        confidence_json_path
    )

    spoken_text = describer.save_text(
        output_path
    )

    # save_text()가 파일만 만들고
    # None을 반환하는 경우 대응
    if spoken_text is None:

        if output_path.exists():
            spoken_text = (
                output_path.read_text(
                    encoding="utf-8"
                )
            )

        else:
            spoken_text = ""

    return (
        output_path,
        spoken_text,
    )


# ============================================================
# Stage 5
# Grounded LLM Summary
# ============================================================

def run_grounded_summary(
    structure,
    features,
    name,
):
    """
    Grounded Summary

    Feature
      ↓
    Atomic Fact
      ↓
    Mandatory Fact
      ↓
    Qwen Optional Selection
      ↓
    Evidence Pointer
      ↓
    Validation
    """

    output_path = (
        SUMMARY_DIR
        / f"{name}.json"
    )

    summary = summarize_music(
        structure,
        features,
    )

    save_json(
        summary,
        output_path,
    )

    return (
        output_path,
        summary,
    )


# ============================================================
# Feature Log Utility
# ============================================================

def print_feature_summary(
    features,
):
    """
    Feature Analyzer 결과를
    터미널에서 보기 쉽게 출력한다.
    """

    feature_parts = (
        features.get(
            "parts",
            [],
        )
        or []
    )

    total_note_count = 0
    total_rest_count = 0

    for part in feature_parts:

        rhythm = (
            part.get(
                "rhythm",
                {},
            )
            or {}
        )

        total_note_count += (
            rhythm.get(
                "noteCount",
                0,
            )
            or 0
        )

        total_rest_count += (
            rhythm.get(
                "restCount",
                0,
            )
            or 0
        )

    print(
        "Part 수:",
        len(feature_parts),
    )

    print(
        "총 Note:",
        total_note_count,
    )

    print(
        "총 Rest:",
        total_rest_count,
    )

    for index, part in enumerate(
        feature_parts,
        start=1,
    ):

        print()

        print(
            f"Part {index}:",
            part.get(
                "name"
            ),
        )

        print(
            "Pitch Range:",
            part.get(
                "pitchRange"
            ),
        )

        print(
            "Contour:",
            part.get(
                "melodicContour"
            ),
        )


# ============================================================
# Pipeline Result
# ============================================================

def build_pipeline_result(
    *,
    name,
    mxl_path,
    omr_path,
    parsed_json_path,
    confidence_json_path,
    feature_json_path,
    spoken_text_path,
    summary_json_path,
    structure,
    features,
    spoken_text,
    summary,
    warnings=None,
):
    """
    전체 악보 Pipeline 결과 JSON 생성.
    """

    warnings = (
        warnings
        or []
    )

    return {
        "id": name,

        "status": "DONE",

        "source": {
            "musicXml":
                str(mxl_path),

            "omr":
                str(omr_path),
        },

        "artifacts": {
            "parsedJson":
                str(parsed_json_path),

            "confidenceJson":
                str(
                    confidence_json_path
                ),

            "featureJson":
                str(feature_json_path),

            "spokenTextFile":
                str(spoken_text_path),

            "summaryJson":
                (
                    str(summary_json_path)
                    if summary_json_path
                    else None
                ),
        },

        "metadata":
            structure.get(
                "metadata",
                {},
            ),

        "confidence":
            structure.get(
                "confidence",
                {},
            ),

        "mapping":
            structure.get(
                "mapping",
                {},
            ),

        "review":
            structure.get(
                "review",
                {},
            ),

        "spokenText":
            spoken_text,

        "features":
            features,

        "summary":
            summary,

        "warnings":
            warnings,
    }


# ============================================================
# Main Pipeline
# ============================================================

def analyze_music(
    mxl_path,
    omr_path,
    parsed_json_path=None,
):
    """
    악보 전체 Core Pipeline.

    1. MusicXML → MusicStructure
    2. Confidence / Review
    3. Feature Analysis
    4. SpokenText
    5. Grounded LLM Summary

    Grounded Summary 단계가 실패해도
    앞 단계의 결과는 유지한다.
    """

    mxl_path = Path(
        mxl_path
    )

    omr_path = Path(
        omr_path
    )

    if not mxl_path.exists():
        raise FileNotFoundError(
            f"MusicXML 없음: "
            f"{mxl_path}"
        )

    if not omr_path.exists():
        raise FileNotFoundError(
            f"OMR 없음: "
            f"{omr_path}"
        )

    name = mxl_path.stem

    print("=" * 70)
    print(
        f"Music Pipeline 시작: "
        f"{name}"
    )
    print("=" * 70)

    warnings = []

    # ========================================================
    # [1/5]
    # MusicXML → JSON
    # ========================================================

    print()
    print(
        "[1/5] MusicXML → "
        "MusicStructure JSON"
    )

    if parsed_json_path:

        parsed_json_path = Path(
            parsed_json_path
        )

        if not parsed_json_path.exists():
            raise FileNotFoundError(
                "기존 Parsed JSON 없음: "
                f"{parsed_json_path}"
            )

        print(
            "기존 JSON 사용:",
            parsed_json_path.name,
        )

        # 파일 정상 여부 확인
        load_json(
            parsed_json_path
        )

    else:

        (
            parsed_json_path,
            _,
        ) = run_musicxml_parser(
            mxl_path
        )

        print(
            "Parser 완료:",
            parsed_json_path.name,
        )

    # ========================================================
    # [2/5]
    # Confidence / Review
    # ========================================================

    print()
    print(
        "[2/5] Confidence / Review"
    )

    (
        confidence_json_path,
        structure,
    ) = run_confidence(
        parsed_json_path,
        omr_path,
    )

    confidence = (
        structure.get(
            "confidence",
            {},
        )
        or {}
    )

    mapping = (
        structure.get(
            "mapping",
            {},
        )
        or {}
    )

    review = (
        structure.get(
            "review",
            {},
        )
        or {}
    )

    print(
        "Confidence:",
        confidence,
    )

    print(
        "Mapping:",
        mapping,
    )

    print(
        "Review:",
        review,
    )

    # ========================================================
    # [3/5]
    # Feature Analysis
    # ========================================================

    print()
    print(
        "[3/5] Music Feature Analysis"
    )

    (
        feature_json_path,
        features,
    ) = run_feature_analysis(
        structure,
        name,
    )

    print(
        "Feature 분석 완료"
    )

    print_feature_summary(
        features
    )

    # ========================================================
    # [4/5]
    # SpokenText
    # ========================================================

    print()
    print(
        "[4/5] SpokenText"
    )

    (
        spoken_text_path,
        spoken_text,
    ) = run_describer(
        confidence_json_path
    )

    print(
        "생성 완료:",
        spoken_text_path.name,
    )

    # ========================================================
    # [5/5]
    # Grounded Summary
    # ========================================================

    print()
    print(
        "[5/5] Grounded LLM Summary"
    )

    summary = None
    summary_json_path = None

    try:

        (
            summary_json_path,
            summary,
        ) = run_grounded_summary(
            structure,
            features,
            name,
        )

        validation = (
            summary.get(
                "validation",
                {},
            )
            or {}
        )

        selection = (
            summary.get(
                "selection",
                {},
            )
            or {}
        )

        print(
            "Summary 생성 완료"
        )

        print(
            "Validation:",
            (
                "PASS"
                if validation.get(
                    "passed"
                )
                else "FAIL"
            ),
        )

        print(
            "Mandatory:",
            selection.get(
                "mandatoryFactIds"
            ),
        )

        print(
            "Optional:",
            selection.get(
                "optionalFactIds"
            ),
        )

        print(
            "Optional Selected By:",
            selection.get(
                "optionalSelectedBy"
            ),
        )

        print(
            "Retry:",
            validation.get(
                "retried"
            ),
        )

        print(
            "Fallback:",
            validation.get(
                "fallbackUsed"
            ),
        )

        # Grounding 검증 실패
        if not validation.get(
            "passed",
            False,
        ):

            warnings.append(
                "GROUNDED_SUMMARY_VALIDATION_FAILED"
            )

        # LLM 대신 deterministic fallback 사용
        if validation.get(
            "fallbackUsed",
            False,
        ):

            fallback_issues = (
                validation.get(
                    "issues",
                    [],
                )
                or []
            )

            if fallback_issues:
                warnings.append(
                    "GROUNDED_SUMMARY_FALLBACK:"
                    + " | ".join(
                        str(issue)
                        for issue
                        in fallback_issues
                    )
                )

            else:
                warnings.append(
                    "GROUNDED_SUMMARY_FALLBACK_USED"
                )

    except Exception as e:

        # LLM Summary가 완전히 실패해도
        # Core Pipeline은 유지
        warning = (
            "GROUNDED_SUMMARY_FAILED:"
            + type(e).__name__
            + ":"
            + str(e)
        )

        warnings.append(
            warning
        )

        summary = {
            "text": None,

            "claims": [],

            "source":
                "midi_phor_inspired_grounded_summary",

            "model": None,

            "selection": {
                "mandatoryFactIds": [],
                "optionalFactIds": [],
                "selectedFactIds": [],
                "optionalSelectedBy":
                    "failed",
            },

            "validation": {
                "passed": False,

                "issues": [
                    warning
                ],

                "retried": False,

                "fallbackUsed": False,
            },
        }

        print(
            "⚠️ Grounded Summary 생성 실패"
        )

        print(
            warning
        )

        print(
            "SpokenText와 Feature 결과는 "
            "정상적으로 유지됩니다."
        )

    # ========================================================
    # Pipeline Result
    # ========================================================

    final_result = (
        build_pipeline_result(
            name=name,

            mxl_path=mxl_path,

            omr_path=omr_path,

            parsed_json_path=
                parsed_json_path,

            confidence_json_path=
                confidence_json_path,

            feature_json_path=
                feature_json_path,

            spoken_text_path=
                spoken_text_path,

            summary_json_path=
                summary_json_path,

            structure=
                structure,

            features=
                features,

            spoken_text=
                spoken_text,

            summary=
                summary,

            warnings=
                warnings,
        )
    )

    final_output_path = (
        PIPELINE_DIR
        / f"{name}.json"
    )

    save_json(
        final_result,
        final_output_path,
    )

    # ========================================================
    # 완료 로그
    # ========================================================

    print()
    print("=" * 70)
    print("Pipeline 완료")
    print("=" * 70)

    print(
        "최종 결과:",
        final_output_path,
    )

    print()

    print(
        "Review:",
        final_result.get(
            "review"
        ),
    )

    print(
        "Features:",
        (
            "생성 완료"
            if final_result.get(
                "features"
            )
            else "없음"
        ),
    )

    summary_result = (
        final_result.get(
            "summary",
            {},
        )
        or {}
    )

    print(
        "Summary:",
        (
            "생성 완료"
            if summary_result.get(
                "text"
            )
            else "생성 실패 또는 없음"
        ),
    )

    if warnings:

        print(
            "Warnings:",
            warnings,
        )

    return (
        final_result,
        final_output_path,
    )


# ============================================================
# Standalone Test
# ============================================================

def main():

    mxl_path = (
        AUDIVERIS_DIR
        / "M01_original.mxl"
    )

    omr_path = (
        AUDIVERIS_DIR
        / "M01_original.omr"
    )

    parsed_json_path = (
        PARSED_DIR
        / "M01_original.json"
    )

    result, output_path = (
        analyze_music(
            mxl_path=mxl_path,

            omr_path=omr_path,

            parsed_json_path=
                parsed_json_path,
        )
    )

    print()
    print("=" * 70)
    print("최종 확인")
    print("=" * 70)

    print(
        "Status:",
        result.get(
            "status"
        ),
    )

    print(
        "Review:",
        result.get(
            "review"
        ),
    )

    print(
        "Features:",
        (
            "OK"
            if result.get(
                "features"
            )
            else "NONE"
        ),
    )

    summary = (
        result.get(
            "summary",
            {},
        )
        or {}
    )

    if summary.get(
        "text"
    ):

        print(
            "Summary:",
            summary.get(
                "text"
            ),
        )

        validation = (
            summary.get(
                "validation",
                {},
            )
            or {}
        )

        print(
            "Summary Validation:",
            (
                "PASS"
                if validation.get(
                    "passed"
                )
                else "FAIL"
            ),
        )

        print(
            "Retry:",
            validation.get(
                "retried"
            ),
        )

        print(
            "Fallback:",
            validation.get(
                "fallbackUsed"
            ),
        )

        print(
            "Claims:",
            len(
                summary.get(
                    "claims",
                    [],
                )
            ),
        )

    else:

        print(
            "Summary:",
            None,
        )

    if result.get(
        "warnings"
    ):

        print(
            "Warnings:",
            result.get(
                "warnings"
            ),
        )

    print()
    print(
        "Pipeline JSON:",
        output_path,
    )


if __name__ == "__main__":
    main()