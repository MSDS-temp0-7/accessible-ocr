from pathlib import Path
import csv
import json


BASE_DIR = Path(__file__).resolve().parent.parent

EVALUATION_CSV = (
    BASE_DIR
    / "evaluation"
    / "omr_evaluation.csv"
)

CONFIDENCE_DIR = (
    BASE_DIR
    / "confidence_output"
)

OUTPUT_CSV = (
    BASE_DIR
    / "evaluation"
    / "confidence_validation.csv"
)


def load_evaluation():

    rows = []

    with open(
        EVALUATION_CSV,
        "r",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            rows.append(row)

    return rows


def load_confidence(sample, condition):

    path = (
        CONFIDENCE_DIR
        / f"{sample}_{condition}.json"
    )

    if not path.exists():
        return None

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def count_events(data):

    note_count = 0
    rest_count = 0

    for part in data.get("parts", []):

        for measure in part.get(
            "measures",
            []
        ):

            for event in measure.get(
                "events",
                []
            ):

                if event.get("type") == "note":
                    note_count += 1

                elif event.get("type") == "rest":
                    rest_count += 1

    return note_count, rest_count


def safe_float(value):

    if value in (
        None,
        "",
        "None",
    ):
        return None

    try:
        return float(value)

    except ValueError:
        return None


evaluation_rows = load_evaluation()

results = []


for row in evaluation_rows:

    sample = row["sample"]
    condition = row["condition"]

    confidence_data = load_confidence(
        sample,
        condition,
    )

    result = {
        "sample": sample,
        "condition": condition,

        "omr_status":
            row.get("status"),

        "pitch_accuracy":
            safe_float(
                row.get(
                    "pitch_accuracy"
                )
            ),

        "duration_accuracy":
            safe_float(
                row.get(
                    "duration_accuracy"
                )
            ),

        "rest_accuracy":
            safe_float(
                row.get(
                    "rest_accuracy"
                )
            ),

        "gt_notes":
            safe_float(
                row.get(
                    "gt_notes"
                )
            ),

        "pred_notes":
            safe_float(
                row.get(
                    "pred_notes"
                )
            ),

        "block_confidence_average":
            None,

        "block_confidence_minimum":
            None,

        "json_note_count":
            None,

        "json_rest_count":
            None,

        "note_mapping_exact":
            None,
    }

    if confidence_data:

        block_confidence = (
            confidence_data.get(
                "confidence"
            )
            or {}
        )

        result[
            "block_confidence_average"
        ] = block_confidence.get(
            "average"
        )

        result[
            "block_confidence_minimum"
        ] = block_confidence.get(
            "minimum"
        )

        note_count, rest_count = (
            count_events(
                confidence_data
            )
        )

        result["json_note_count"] = (
            note_count
        )

        result["json_rest_count"] = (
            rest_count
        )

        gt_notes = result["gt_notes"]

        if gt_notes is not None:

            result[
                "note_mapping_exact"
            ] = (
                note_count
                == int(gt_notes)
            )

    results.append(result)


fieldnames = [
    "sample",
    "condition",

    "omr_status",

    "pitch_accuracy",
    "duration_accuracy",
    "rest_accuracy",

    "gt_notes",
    "pred_notes",

    "json_note_count",
    "json_rest_count",

    "note_mapping_exact",

    "block_confidence_average",
    "block_confidence_minimum",
]


with open(
    OUTPUT_CSV,
    "w",
    newline="",
    encoding="utf-8-sig",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(results)


print("=" * 70)
print("Confidence Validation")
print("=" * 70)

print(
    f"전체 샘플: {len(results)}"
)

print()


for row in results:

    print(
        f"{row['sample']}_"
        f"{row['condition']}"
    )

    print(
        f"  Pitch     : "
        f"{row['pitch_accuracy']}"
    )

    print(
        f"  Conf avg  : "
        f"{row['block_confidence_average']}"
    )

    print(
        f"  Conf min  : "
        f"{row['block_confidence_minimum']}"
    )

    print(
        f"  Notes     : "
        f"{row['pred_notes']} / "
        f"{row['gt_notes']}"
    )

    print(
        f"  Exact     : "
        f"{row['note_mapping_exact']}"
    )

    print()


print(
    "결과:",
    OUTPUT_CSV
)