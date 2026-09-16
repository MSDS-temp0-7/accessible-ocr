from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher
import csv

from music21 import converter, note, meter, key, stream, chord


# ============================================================
# 1. 경로 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

GT_DIR = BASE_DIR / "ground_truth"
PRED_DIR = BASE_DIR / "audiveris_output"
RESULT_DIR = BASE_DIR / "evaluation"

RESULT_DIR.mkdir(exist_ok=True)


# 평가 조건
CONDITIONS = [
    "original",
    "small",
    "tilt",
    "lowq",
]


# ============================================================
# 2. MusicXML 읽기
# ============================================================

def load_score(path: Path):
    """
    MusicXML(.mxl)을 music21 Score 객체로 읽는다.
    """
    return converter.parse(path)


# ============================================================
# 3. 음표 정보 추출
# ============================================================

def extract_notes(score):
    """
    음표 정보를 순서대로 추출한다.

    반환 예:
    [
        {
            "pitch": "C4",
            "duration": 1.0,
            "accidental": None
        },
        ...
    ]

    chord가 있을 경우 chord 내부 음도 각각 하나의 pitch로 처리한다.
    """

    result = []

    for element in score.recurse().notes:

        # ----------------------------------------------------
        # 일반 Note
        # ----------------------------------------------------
        if isinstance(element, note.Note):

            accidental = None

            if element.pitch.accidental is not None:
                accidental = element.pitch.accidental.name

            result.append({
                "pitch": element.pitch.nameWithOctave,
                "duration": float(element.duration.quarterLength),
                "accidental": accidental,
            })

        # ----------------------------------------------------
        # Chord
        # ----------------------------------------------------
        elif isinstance(element, chord.Chord):

            for pitch in element.pitches:

                accidental = None

                if pitch.accidental is not None:
                    accidental = pitch.accidental.name

                result.append({
                    "pitch": pitch.nameWithOctave,
                    "duration": float(element.duration.quarterLength),
                    "accidental": accidental,
                })

    return result


# ============================================================
# 4. Rest 정보 추출
# ============================================================

def extract_rest_events(score):
    """
    쉼표를 단순 개수/길이만 비교하지 않고,

    - Part
    - Measure
    - Measure 내 offset
    - Duration

    기준으로 추출한다.

    예:
    (0, "1", 2.0, 1.0)

    의미:
    part 0
    1마디
    offset 2.0
    quarterLength 1.0의 쉼표
    """

    events = []

    parts = list(score.parts)

    # Part 구조가 없는 MusicXML 대비
    if not parts:
        parts = [score]

    for part_index, part in enumerate(parts):

        measures = part.recurse().getElementsByClass(
            stream.Measure
        )

        for measure in measures:

            rests = measure.recurse().getElementsByClass(
                note.Rest
            )

            for rest in rests:

                try:
                    offset = float(
                        rest.getOffsetInHierarchy(measure)
                    )
                except Exception:
                    offset = float(rest.offset)

                duration = float(
                    rest.duration.quarterLength
                )

                events.append((
                    part_index,
                    str(measure.number),
                    round(offset, 3),
                    round(duration, 3),
                ))

    return events


# ============================================================
# 5. Time Signature 추출
# ============================================================

def extract_time_signature(score):
    """
    첫 번째 박자표를 반환한다.

    예:
    4/4
    3/4
    6/8
    """

    signatures = list(
        score.recurse().getElementsByClass(
            meter.TimeSignature
        )
    )

    if not signatures:
        return None

    return signatures[0].ratioString


# ============================================================
# 6. Key Signature 추출
# ============================================================

def extract_key_signature(score):
    """
    KeySignature의 sharps 값을 반환한다.

     0  -> 조표 없음
     1  -> sharp 1개
     2  -> sharp 2개
    -1  -> flat 1개
    -2  -> flat 2개
    """

    signatures = list(
        score.recurse().getElementsByClass(
            key.KeySignature
        )
    )

    if not signatures:
        return None

    return signatures[0].sharps


# ============================================================
# 7. 음표 Sequence Alignment
# ============================================================

def align_notes(gt_notes, pred_notes):
    """
    GT와 Audiveris 음표를 pitch 순서를 기준으로 정렬한다.

    단순 index 비교를 사용하면 Audiveris가 음표 하나를 놓쳤을 때
    이후 음표가 전부 밀리는 문제가 발생한다.

    SequenceMatcher를 이용해 일치하는 음표 구간을 찾는다.
    """

    gt_pitch = [
        n["pitch"]
        for n in gt_notes
    ]

    pred_pitch = [
        n["pitch"]
        for n in pred_notes
    ]

    matcher = SequenceMatcher(
        None,
        gt_pitch,
        pred_pitch,
        autojunk=False,
    )

    aligned = []

    for block in matcher.get_matching_blocks():

        for offset in range(block.size):

            gt_index = block.a + offset
            pred_index = block.b + offset

            aligned.append((
                gt_notes[gt_index],
                pred_notes[pred_index],
            ))

    return aligned


# ============================================================
# 8. 정확도 계산
# ============================================================

def safe_accuracy(correct, total):
    """
    percentage 계산.

    평가할 대상 자체가 없으면 None을 반환한다.
    """

    if total == 0:
        return None

    return round(
        (correct / total) * 100,
        2,
    )


# ============================================================
# 9. 한 쌍의 GT / Prediction 평가
# ============================================================

def evaluate(gt_path: Path, pred_path: Path):

    gt_score = load_score(gt_path)
    pred_score = load_score(pred_path)

    gt_notes = extract_notes(gt_score)
    pred_notes = extract_notes(pred_score)

    aligned = align_notes(
        gt_notes,
        pred_notes,
    )

    # ========================================================
    # Pitch Accuracy
    #
    # 음높이를 제대로 읽었는가?
    #
    # C4 → C4 : 정답
    # C4 → D4 : 오답
    # ========================================================

    pitch_correct = sum(
        1
        for gt, pred in aligned
        if gt["pitch"] == pred["pitch"]
    )

    pitch_accuracy = safe_accuracy(
        pitch_correct,
        len(gt_notes),
    )


    # ========================================================
    # Duration Accuracy
    #
    # 음표 길이를 제대로 읽었는가?
    #
    # quarterLength:
    # 1.0 = 4분음표
    # 2.0 = 2분음표
    # 0.5 = 8분음표
    # ========================================================

    duration_correct = sum(
        1
        for gt, pred in aligned
        if gt["duration"] == pred["duration"]
    )

    duration_accuracy = safe_accuracy(
        duration_correct,
        len(gt_notes),
    )


    # ========================================================
    # Accidental Accuracy
    #
    # sharp / flat / natural 등의 임시표 인식
    #
    # GT에 임시표가 하나도 없다면 평가 대상이 아니므로 None
    # ========================================================

    gt_accidental_notes = [
        n
        for n in gt_notes
        if n["accidental"] is not None
    ]

    if len(gt_accidental_notes) == 0:

        accidental_accuracy = None

    else:

        accidental_correct = sum(
            1
            for gt, pred in aligned
            if (
                gt["accidental"] is not None
                and
                gt["accidental"] == pred["accidental"]
            )
        )

        accidental_accuracy = safe_accuracy(
            accidental_correct,
            len(gt_accidental_notes),
        )


    # ========================================================
    # Rest Accuracy
    #
    # Part + Measure + Offset + Duration이 모두 일치하는
    # 쉼표를 정답으로 처리
    # ========================================================

    gt_rests = extract_rest_events(gt_score)
    pred_rests = extract_rest_events(pred_score)

    gt_rest_counter = Counter(gt_rests)
    pred_rest_counter = Counter(pred_rests)

    matched_rests = sum(
        (gt_rest_counter & pred_rest_counter).values()
    )

    rest_accuracy = safe_accuracy(
        matched_rests,
        len(gt_rests),
    )


    # ========================================================
    # Time Signature Accuracy
    #
    # 4/4 → 4/4 : 100
    # 4/4 → 3/4 : 0
    # ========================================================

    gt_time = extract_time_signature(gt_score)
    pred_time = extract_time_signature(pred_score)

    if gt_time is None:

        time_signature_accuracy = None

    else:

        time_signature_accuracy = (
            100.0
            if gt_time == pred_time
            else 0.0
        )


    # ========================================================
    # Key Signature Accuracy
    #
    # 현재 PoC에서는
    #
    # None과 0을 음악적으로
    # "sharp/flat이 없는 상태"로 동일하게 처리
    # ========================================================

    gt_key = extract_key_signature(gt_score)
    pred_key = extract_key_signature(pred_score)

    gt_key_normalized = (
        0
        if gt_key is None
        else gt_key
    )

    pred_key_normalized = (
        0
        if pred_key is None
        else pred_key
    )

    key_signature_accuracy = (
        100.0
        if gt_key_normalized == pred_key_normalized
        else 0.0
    )


    # ========================================================
    # 결과
    # ========================================================

    return {

        "gt_notes": len(gt_notes),
        "pred_notes": len(pred_notes),

        "gt_rests": len(gt_rests),
        "pred_rests": len(pred_rests),

        "pitch_accuracy": pitch_accuracy,
        "duration_accuracy": duration_accuracy,
        "accidental_accuracy": accidental_accuracy,
        "rest_accuracy": rest_accuracy,

        "key_signature_accuracy": key_signature_accuracy,
        "time_signature_accuracy": time_signature_accuracy,

        "gt_key": gt_key,
        "pred_key": pred_key,

        "gt_time": gt_time,
        "pred_time": pred_time,
    }


# ============================================================
# 10. Audiveris 실패 단계 확인
# ============================================================

def detect_failed_stage(model, condition):
    """
    MusicXML이 생성되지 않았을 경우
    Audiveris 로그를 읽어서 실패 단계를 추정한다.

    현재 M04_tilt / M05_tilt는
    GridBuilder 오류이므로 GRID로 잡힌다.
    """

    log_files = list(
        PRED_DIR.glob(
            f"{model}_{condition}-*.log"
        )
    )

    if not log_files:
        return None

    # 가장 최근 로그
    latest_log = max(
        log_files,
        key=lambda path: path.stat().st_mtime,
    )

    try:

        text = latest_log.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception:

        return None

    if (
        "GridBuilder" in text
        or "Error in GridBuilder" in text
    ):
        return "GRID"

    if "Error in reaching step PAGE" in text:
        return "PAGE"

    if "Too large image" in text:
        return "LOAD"

    return "UNKNOWN"


# ============================================================
# 11. 전체 20개 평가
# ============================================================

results = []


for number in range(1, 6):

    model = f"M{number:02d}"

    gt_path = (
        GT_DIR /
        f"{model}.mxl"
    )

    for condition in CONDITIONS:

        pred_path = (
            PRED_DIR /
            f"{model}_{condition}.mxl"
        )

        print(
            f"평가 중: {model} / {condition}"
        )

        # ----------------------------------------------------
        # Ground Truth 없음
        # ----------------------------------------------------

        if not gt_path.exists():

            results.append({

                "sample": model,
                "condition": condition,

                "status": "GT_MISSING",
                "mxl_generated": False,
                "failed_stage": None,

                "gt_notes": None,
                "pred_notes": None,

                "gt_rests": None,
                "pred_rests": None,

                "pitch_accuracy": None,
                "duration_accuracy": None,
                "accidental_accuracy": None,
                "rest_accuracy": None,

                "key_signature_accuracy": None,
                "time_signature_accuracy": None,

                "gt_key": None,
                "pred_key": None,

                "gt_time": None,
                "pred_time": None,
            })

            continue


        # ----------------------------------------------------
        # Audiveris MusicXML 생성 실패
        # ----------------------------------------------------

        if not pred_path.exists():

            failed_stage = detect_failed_stage(
                model,
                condition,
            )

            results.append({

                "sample": model,
                "condition": condition,

                "status": "OMR_FAILED",
                "mxl_generated": False,
                "failed_stage": failed_stage,

                "gt_notes": None,
                "pred_notes": None,

                "gt_rests": None,
                "pred_rests": None,

                "pitch_accuracy": None,
                "duration_accuracy": None,
                "accidental_accuracy": None,
                "rest_accuracy": None,

                "key_signature_accuracy": None,
                "time_signature_accuracy": None,

                "gt_key": None,
                "pred_key": None,

                "gt_time": None,
                "pred_time": None,
            })

            continue


        # ----------------------------------------------------
        # 정상 평가
        # ----------------------------------------------------

        try:

            result = evaluate(
                gt_path,
                pred_path,
            )

            result.update({

                "sample": model,
                "condition": condition,

                "status": "SUCCESS",
                "mxl_generated": True,
                "failed_stage": None,
            })

            results.append(result)


        # ----------------------------------------------------
        # MusicXML은 있지만 Python 평가 과정에서 오류
        # ----------------------------------------------------

        except Exception as e:

            print(
                f"[평가 오류] "
                f"{model}_{condition}: {e}"
            )

            results.append({

                "sample": model,
                "condition": condition,

                "status": "EVALUATION_FAILED",
                "mxl_generated": True,
                "failed_stage": "EVALUATION",

                "gt_notes": None,
                "pred_notes": None,

                "gt_rests": None,
                "pred_rests": None,

                "pitch_accuracy": None,
                "duration_accuracy": None,
                "accidental_accuracy": None,
                "rest_accuracy": None,

                "key_signature_accuracy": None,
                "time_signature_accuracy": None,

                "gt_key": None,
                "pred_key": None,

                "gt_time": None,
                "pred_time": None,
            })


# ============================================================
# 12. 상세 평가 CSV 저장
# ============================================================

detail_csv_path = (
    RESULT_DIR /
    "omr_evaluation.csv"
)


fieldnames = [

    "sample",
    "condition",

    "status",
    "mxl_generated",
    "failed_stage",

    "gt_notes",
    "pred_notes",

    "gt_rests",
    "pred_rests",

    "pitch_accuracy",
    "duration_accuracy",
    "accidental_accuracy",
    "rest_accuracy",

    "key_signature_accuracy",
    "time_signature_accuracy",

    "gt_key",
    "pred_key",

    "gt_time",
    "pred_time",
]


with open(
    detail_csv_path,
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


# ============================================================
# 13. 조건별 평균 계산
# ============================================================

def average(values):
    """
    None을 제외하고 평균 계산
    """

    valid_values = [
        value
        for value in values
        if value is not None
    ]

    if not valid_values:
        return None

    return round(
        sum(valid_values) / len(valid_values),
        2,
    )


summary_results = []


for condition in CONDITIONS:

    condition_rows = [
        row
        for row in results
        if row["condition"] == condition
    ]

    success_rows = [
        row
        for row in condition_rows
        if row["status"] == "SUCCESS"
    ]

    total_count = len(condition_rows)
    success_count = len(success_rows)

    mxl_success_rate = safe_accuracy(
        success_count,
        total_count,
    )

    summary_results.append({

        "condition": condition,

        "total_samples": total_count,
        "mxl_success_count": success_count,
        "mxl_failed_count": (
            total_count - success_count
        ),
        "mxl_success_rate": mxl_success_rate,

        "pitch_accuracy_avg": average([
            row["pitch_accuracy"]
            for row in success_rows
        ]),

        "duration_accuracy_avg": average([
            row["duration_accuracy"]
            for row in success_rows
        ]),

        "accidental_accuracy_avg": average([
            row["accidental_accuracy"]
            for row in success_rows
        ]),

        "rest_accuracy_avg": average([
            row["rest_accuracy"]
            for row in success_rows
        ]),

        "key_signature_accuracy_avg": average([
            row["key_signature_accuracy"]
            for row in success_rows
        ]),

        "time_signature_accuracy_avg": average([
            row["time_signature_accuracy"]
            for row in success_rows
        ]),
    })


# ============================================================
# 14. 조건별 요약 CSV 저장
# ============================================================

summary_csv_path = (
    RESULT_DIR /
    "omr_condition_summary.csv"
)


summary_fieldnames = [

    "condition",

    "total_samples",
    "mxl_success_count",
    "mxl_failed_count",
    "mxl_success_rate",

    "pitch_accuracy_avg",
    "duration_accuracy_avg",
    "accidental_accuracy_avg",
    "rest_accuracy_avg",

    "key_signature_accuracy_avg",
    "time_signature_accuracy_avg",
]


with open(
    summary_csv_path,
    "w",
    newline="",
    encoding="utf-8-sig",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=summary_fieldnames,
    )

    writer.writeheader()
    writer.writerows(summary_results)


# ============================================================
# 15. 콘솔 결과 출력
# ============================================================

success_count = sum(
    1
    for row in results
    if row["status"] == "SUCCESS"
)

omr_failed_count = sum(
    1
    for row in results
    if row["status"] == "OMR_FAILED"
)

evaluation_failed_count = sum(
    1
    for row in results
    if row["status"] == "EVALUATION_FAILED"
)


print()
print("=" * 60)
print("OMR 평가 완료")
print("=" * 60)

print(
    f"전체 평가 개수 : {len(results)}"
)

print(
    f"MXL 생성 성공   : {success_count}"
)

print(
    f"OMR 실패        : {omr_failed_count}"
)

print(
    f"평가 코드 실패  : {evaluation_failed_count}"
)

print()
print(
    f"상세 결과 : {detail_csv_path}"
)

print(
    f"조건별 요약: {summary_csv_path}"
)


print()
print("=" * 60)
print("조건별 결과")
print("=" * 60)


for row in summary_results:

    print()
    print(
        f"[{row['condition']}]"
    )

    print(
        f"MXL 성공률 : "
        f"{row['mxl_success_rate']}%"
    )

    print(
        f"Pitch      : "
        f"{row['pitch_accuracy_avg']}"
    )

    print(
        f"Duration   : "
        f"{row['duration_accuracy_avg']}"
    )

    print(
        f"Accidental : "
        f"{row['accidental_accuracy_avg']}"
    )

    print(
        f"Rest       : "
        f"{row['rest_accuracy_avg']}"
    )

    print(
        f"Key        : "
        f"{row['key_signature_accuracy_avg']}"
    )

    print(
        f"Time       : "
        f"{row['time_signature_accuracy_avg']}"
    )