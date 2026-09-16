from pathlib import Path
import csv
import json
import traceback

from music_pipeline import analyze_music


# ============================================================
# 기본 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

AUDIVERIS_DIR = BASE_DIR / "audiveris_output"
PARSED_DIR = BASE_DIR / "parsed_output"
EVALUATION_DIR = BASE_DIR / "evaluation"

EVALUATION_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RESULT_JSON = (
    EVALUATION_DIR
    / "batch_pipeline_results.json"
)

RESULT_CSV = (
    EVALUATION_DIR
    / "batch_pipeline_results.csv"
)


# ============================================================
# Utility
# ============================================================

def save_json(
    data,
    path: Path,
):

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


def detect_condition(
    name: str,
):
    """
    M01_original
    M01_small
    M01_tilt
    M01_lowq

    → condition 추출
    """

    conditions = [
        "original",
        "small",
        "tilt",
        "lowq",
    ]

    for condition in conditions:

        if name.endswith(
            f"_{condition}"
        ):

            return condition

    return "unknown"


def get_sample_id(
    name: str,
):
    """
    M01_original → M01
    """

    condition = detect_condition(
        name
    )

    suffix = (
        f"_{condition}"
    )

    if (
        condition != "unknown"
        and name.endswith(
            suffix
        )
    ):

        return name[
            :-len(suffix)
        ]

    return name


# ============================================================
# Result 추출
# ============================================================

def extract_result_row(
    name,
    result,
):

    review = (
        result.get(
            "review",
            {},
        )
        or {}
    )

    confidence = (
        result.get(
            "confidence",
            {},
        )
        or {}
    )

    mapping = (
        result.get(
            "mapping",
            {},
        )
        or {}
    )

    summary = (
        result.get(
            "summary",
            {},
        )
        or {}
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

    claims = (
        summary.get(
            "claims",
            [],
        )
        or []
    )

    warnings = (
        result.get(
            "warnings",
            [],
        )
        or []
    )

    return {

        "sample":
            name,

        "baseSample":
            get_sample_id(
                name
            ),

        "condition":
            detect_condition(
                name
            ),

        "pipelineStatus":
            result.get(
                "status"
            ),

        # ----------------------------------------------------
        # Review
        # ----------------------------------------------------

        "reviewLevel":
            review.get(
                "level"
            ),

        "needsReview":
            review.get(
                "needsReview"
            ),

        "reviewReasons":
            "|".join(
                review.get(
                    "reasons",
                    [],
                )
                or []
            ),

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        "confidenceAverage":
            confidence.get(
                "average"
            ),

        "confidenceMinimum":
            confidence.get(
                "minimum"
            ),

        # ----------------------------------------------------
        # Mapping
        # ----------------------------------------------------

        "noteCountMatch":
            mapping.get(
                "noteCountMatch"
            ),

        "restCountMatch":
            mapping.get(
                "restCountMatch"
            ),

        "jsonNoteCount":
            mapping.get(
                "jsonNoteCount"
            ),

        "omrHeadCount":
            mapping.get(
                "omrHeadCount"
            ),

        "jsonRestCount":
            mapping.get(
                "jsonRestCount"
            ),

        "omrRestCount":
            mapping.get(
                "omrRestCount"
            ),

        # ----------------------------------------------------
        # Grounded Summary
        # ----------------------------------------------------

        "summaryGenerated":
            bool(
                summary.get(
                    "text"
                )
            ),

        "summaryValidation":
            validation.get(
                "passed"
            ),

        "retry":
            validation.get(
                "retried"
            ),

        "fallback":
            validation.get(
                "fallbackUsed"
            ),

        "claimCount":
            len(
                claims
            ),

        "optionalSelectedBy":
            selection.get(
                "optionalSelectedBy"
            ),

        "mandatoryFactIds":
            "|".join(
                selection.get(
                    "mandatoryFactIds",
                    [],
                )
                or []
            ),

        "optionalFactIds":
            "|".join(
                selection.get(
                    "optionalFactIds",
                    [],
                )
                or []
            ),

        # ----------------------------------------------------
        # Warning
        # ----------------------------------------------------

        "warningCount":
            len(
                warnings
            ),

        "warnings":
            "|".join(
                warnings
            ),

        # ----------------------------------------------------
        # Summary Text
        # ----------------------------------------------------

        "summaryText":
            summary.get(
                "text"
            ),
    }


# ============================================================
# 실패 Result
# ============================================================

def build_error_row(
    name,
    error,
):

    return {

        "sample":
            name,

        "baseSample":
            get_sample_id(
                name
            ),

        "condition":
            detect_condition(
                name
            ),

        "pipelineStatus":
            "FAILED",

        "reviewLevel":
            None,

        "needsReview":
            None,

        "reviewReasons":
            None,

        "confidenceAverage":
            None,

        "confidenceMinimum":
            None,

        "noteCountMatch":
            None,

        "restCountMatch":
            None,

        "jsonNoteCount":
            None,

        "omrHeadCount":
            None,

        "jsonRestCount":
            None,

        "omrRestCount":
            None,

        "summaryGenerated":
            False,

        "summaryValidation":
            False,

        "retry":
            None,

        "fallback":
            None,

        "claimCount":
            0,

        "optionalSelectedBy":
            None,

        "mandatoryFactIds":
            None,

        "optionalFactIds":
            None,

        "warningCount":
            1,

        "warnings":
            str(error),

        "summaryText":
            None,
    }


# ============================================================
# CSV 저장
# ============================================================

def save_csv(
    rows,
    path,
):

    if not rows:
        return

    fieldnames = list(
        rows[0].keys()
    )

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


# ============================================================
# Condition Summary
# ============================================================

def build_condition_summary(
    rows,
):

    conditions = {}

    for row in rows:

        condition = (
            row.get(
                "condition",
                "unknown",
            )
        )

        if condition not in conditions:

            conditions[
                condition
            ] = {

                "total":
                    0,

                "pipelineDone":
                    0,

                "pipelineFailed":
                    0,

                "summaryPass":
                    0,

                "summaryFail":
                    0,

                "retryCount":
                    0,

                "fallbackCount":
                    0,

                "reviewLow":
                    0,

                "reviewMedium":
                    0,

                "reviewHigh":
                    0,
            }

        stats = (
            conditions[
                condition
            ]
        )

        stats["total"] += 1

        if (
            row.get(
                "pipelineStatus"
            )
            == "DONE"
        ):

            stats[
                "pipelineDone"
            ] += 1

        else:

            stats[
                "pipelineFailed"
            ] += 1

        if row.get(
            "summaryValidation"
        ) is True:

            stats[
                "summaryPass"
            ] += 1

        else:

            stats[
                "summaryFail"
            ] += 1

        if row.get(
            "retry"
        ) is True:

            stats[
                "retryCount"
            ] += 1

        if row.get(
            "fallback"
        ) is True:

            stats[
                "fallbackCount"
            ] += 1

        review_level = (
            row.get(
                "reviewLevel"
            )
        )

        if review_level == "LOW":

            stats[
                "reviewLow"
            ] += 1

        elif review_level == "MEDIUM":

            stats[
                "reviewMedium"
            ] += 1

        elif review_level == "HIGH":

            stats[
                "reviewHigh"
            ] += 1

    return conditions


# ============================================================
# Console Table
# ============================================================

def print_result_table(
    rows,
):

    print()
    print(
        "=" * 110
    )

    print(
        "Batch Pipeline 결과"
    )

    print(
        "=" * 110
    )

    header = (
        f"{'Sample':<16}"
        f"{'Pipeline':<10}"
        f"{'Review':<9}"
        f"{'Summary':<10}"
        f"{'Retry':<8}"
        f"{'Fallback':<10}"
        f"{'Claims':<8}"
        f"{'NoteMap':<9}"
        f"{'RestMap':<9}"
    )

    print(
        header
    )

    print(
        "-" * 110
    )

    for row in rows:

        summary_status = (
            "PASS"
            if row.get(
                "summaryValidation"
            )
            else "FAIL"
        )

        print(
            f"{str(row.get('sample')):<16}"
            f"{str(row.get('pipelineStatus')):<10}"
            f"{str(row.get('reviewLevel')):<9}"
            f"{summary_status:<10}"
            f"{str(row.get('retry')):<8}"
            f"{str(row.get('fallback')):<10}"
            f"{str(row.get('claimCount')):<8}"
            f"{str(row.get('noteCountMatch')):<9}"
            f"{str(row.get('restCountMatch')):<9}"
        )


# ============================================================
# Condition 결과 출력
# ============================================================

def print_condition_summary(
    condition_summary,
):

    print()
    print(
        "=" * 90
    )

    print(
        "조건별 요약"
    )

    print(
        "=" * 90
    )

    for condition, stats in sorted(
        condition_summary.items()
    ):

        print()
        print(
            f"[{condition}]"
        )

        print(
            "전체:",
            stats["total"],
        )

        print(
            "Pipeline DONE:",
            stats[
                "pipelineDone"
            ],
        )

        print(
            "Pipeline FAILED:",
            stats[
                "pipelineFailed"
            ],
        )

        print(
            "Summary PASS:",
            stats[
                "summaryPass"
            ],
        )

        print(
            "Summary FAIL:",
            stats[
                "summaryFail"
            ],
        )

        print(
            "Retry:",
            stats[
                "retryCount"
            ],
        )

        print(
            "Fallback:",
            stats[
                "fallbackCount"
            ],
        )

        print(
            "Review LOW/MEDIUM/HIGH:",
            (
                stats[
                    "reviewLow"
                ]
            ),
            "/",
            (
                stats[
                    "reviewMedium"
                ]
            ),
            "/",
            (
                stats[
                    "reviewHigh"
                ]
            ),
        )


# ============================================================
# Main Batch
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "Music Pipeline Batch Validation"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # MXL 기준으로 성공한 Audiveris 결과 탐색
    # --------------------------------------------------------

    mxl_files = sorted(
        AUDIVERIS_DIR.glob(
            "*.mxl"
        )
    )

    if not mxl_files:

        raise FileNotFoundError(
            "audiveris_output에 "
            "MXL 파일이 없습니다."
        )

    print()
    print(
        "MXL 발견:",
        len(mxl_files),
    )

    rows = []

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    # ========================================================
    # 각 악보 실행
    # ========================================================

    for index, mxl_path in enumerate(
        mxl_files,
        start=1,
    ):

        name = (
            mxl_path.stem
        )

        omr_path = (
            AUDIVERIS_DIR
            / f"{name}.omr"
        )

        parsed_path = (
            PARSED_DIR
            / f"{name}.json"
        )

        print()
        print(
            "#" * 70
        )

        print(
            f"[{index}/{len(mxl_files)}] "
            f"{name}"
        )

        print(
            "#" * 70
        )

        # ----------------------------------------------------
        # OMR이 없으면 skip
        # ----------------------------------------------------

        if not omr_path.exists():

            print(
                "⚠️ OMR 파일 없음 → SKIP"
            )

            skipped_count += 1

            continue

        try:

            # Parsed JSON이 있으면 재사용
            if parsed_path.exists():

                parsed_arg = (
                    parsed_path
                )

            else:

                parsed_arg = None

            result, _ = analyze_music(
                mxl_path=mxl_path,
                omr_path=omr_path,
                parsed_json_path=
                    parsed_arg,
            )

            row = (
                extract_result_row(
                    name,
                    result,
                )
            )

            rows.append(
                row
            )

            processed_count += 1

            print()
            print(
                "✅ Batch Sample 완료:",
                name,
            )

        except Exception as e:

            failed_count += 1

            print()
            print(
                "❌ Sample 실패:",
                name,
            )

            print(
                type(e).__name__,
                ":",
                e,
            )

            traceback.print_exc()

            rows.append(
                build_error_row(
                    name,
                    e,
                )
            )

    # ========================================================
    # 결과 저장
    # ========================================================

    condition_summary = (
        build_condition_summary(
            rows
        )
    )

    output = {

        "totalMxlFiles":
            len(mxl_files),

        "processed":
            processed_count,

        "skipped":
            skipped_count,

        "failed":
            failed_count,

        "conditionSummary":
            condition_summary,

        "samples":
            rows,
    }

    save_json(
        output,
        RESULT_JSON,
    )

    save_csv(
        rows,
        RESULT_CSV,
    )

    # ========================================================
    # Console 결과
    # ========================================================

    print_result_table(
        rows
    )

    print_condition_summary(
        condition_summary
    )

    print()
    print(
        "=" * 70
    )

    print(
        "Batch 완료"
    )

    print(
        "=" * 70
    )

    print(
        "MXL:",
        len(mxl_files),
    )

    print(
        "처리 성공:",
        processed_count,
    )

    print(
        "처리 실패:",
        failed_count,
    )

    print(
        "Skip:",
        skipped_count,
    )

    print()

    print(
        "JSON:",
        RESULT_JSON,
    )

    print(
        "CSV:",
        RESULT_CSV,
    )


if __name__ == "__main__":
    main()