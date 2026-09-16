from pathlib import Path
from collections import Counter, defaultdict
import json
from statistics import mean


BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# Event 정렬
# ============================================================

def sort_events(events):

    return sorted(
        events,
        key=lambda event: (
            float(event.get("offset", 0) or 0),
            str(event.get("voice", 1)),
        )
    )


# ============================================================
# Pitch 데이터 수집
# ============================================================

def collect_note_sequence(part):

    sequence = []

    for measure in part.get("measures", []):

        measure_number = measure.get("number")

        for event in sort_events(
            measure.get("events", [])
        ):

            if event.get("type") != "note":
                continue

            pitch = event.get("pitch") or {}

            midi = pitch.get("midi")

            if midi is None:
                continue

            sequence.append({
                "measure": measure_number,
                "offset": event.get("offset", 0),
                "midi": midi,
                "name": pitch.get("name"),
                "duration": (
                    event.get("duration") or {}
                ).get("quarterLength"),
            })

    return sequence


# ============================================================
# 선율 진행 분석
# ============================================================

def analyze_contour(note_sequence):

    ascending = 0
    descending = 0
    repeated = 0

    intervals = []

    for previous, current in zip(
        note_sequence,
        note_sequence[1:],
    ):

        diff = (
            current["midi"]
            - previous["midi"]
        )

        intervals.append(diff)

        if diff > 0:
            ascending += 1

        elif diff < 0:
            descending += 1

        else:
            repeated += 1

    total = (
        ascending
        + descending
        + repeated
    )

    if total == 0:

        direction = "INSUFFICIENT_DATA"

    elif (
        ascending > descending
        and ascending > repeated
    ):

        direction = "ASCENDING"

    elif (
        descending > ascending
        and descending > repeated
    ):

        direction = "DESCENDING"

    elif (
        repeated > ascending
        and repeated > descending
    ):

        direction = "REPEATED"

    else:

        direction = "MIXED"

    absolute_intervals = [
        abs(value)
        for value in intervals
    ]

    return {
        "ascendingCount": ascending,
        "descendingCount": descending,
        "repeatedCount": repeated,
        "dominantDirection": direction,
        "averageIntervalSemitones": (
            round(
                mean(absolute_intervals),
                2
            )
            if absolute_intervals
            else 0
        ),
        "maxIntervalSemitones": (
            max(absolute_intervals)
            if absolute_intervals
            else 0
        ),
    }


# ============================================================
# 음역 분석
# ============================================================

def analyze_pitch_range(note_sequence):

    if not note_sequence:

        return {
            "minimumMidi": None,
            "maximumMidi": None,
            "minimumPitch": None,
            "maximumPitch": None,
            "rangeSemitones": 0,
        }

    lowest = min(
        note_sequence,
        key=lambda note: note["midi"]
    )

    highest = max(
        note_sequence,
        key=lambda note: note["midi"]
    )

    return {
        "minimumMidi":
            lowest["midi"],

        "maximumMidi":
            highest["midi"],

        "minimumPitch":
            lowest["name"],

        "maximumPitch":
            highest["name"],

        "rangeSemitones":
            highest["midi"]
            - lowest["midi"],
    }


# ============================================================
# Duration 이름
# ============================================================

def duration_token(event):

    event_type = event.get(
        "type",
        "unknown"
    )

    duration = (
        event.get("duration")
        or {}
    )

    quarter_length = duration.get(
        "quarterLength"
    )

    return (
        f"{event_type}:"
        f"{quarter_length}"
    )


# ============================================================
# 리듬 분석
# ============================================================

def analyze_rhythm(part):

    duration_counter = Counter()

    note_count = 0
    rest_count = 0
    chord_count = 0

    total_measures = len(
        part.get("measures", [])
    )

    active_measures = 0

    measure_patterns = defaultdict(
        list
    )

    for measure in part.get(
        "measures",
        []
    ):

        events = sort_events(
            measure.get(
                "events",
                []
            )
        )

        measure_number = measure.get(
            "number"
        )

        pattern = []

        measure_note_count = 0

        for event in events:

            event_type = event.get(
                "type"
            )

            if event_type == "note":

                note_count += 1
                measure_note_count += 1

            elif event_type == "rest":

                rest_count += 1

            elif event_type == "chord":

                chord_count += 1
                measure_note_count += 1

            duration = (
                event.get("duration")
                or {}
            )

            quarter_length = (
                duration.get(
                    "quarterLength"
                )
            )

            if quarter_length is not None:

                duration_counter[
                    str(quarter_length)
                ] += 1

            pattern.append(
                duration_token(event)
            )

        if measure_note_count > 0:
            active_measures += 1

        pattern_key = "|".join(
            pattern
        )

        if pattern_key:

            measure_patterns[
                pattern_key
            ].append(
                measure_number
            )

    # --------------------------------------------------------
    # 반복되는 마디 리듬
    # --------------------------------------------------------

    repeated_patterns = []

    for pattern, measures in (
        measure_patterns.items()
    ):

        if len(measures) < 2:
            continue

        repeated_patterns.append({
            "pattern": pattern,
            "measures": measures,
            "repeatCount": len(measures),
        })

    repeated_patterns.sort(
        key=lambda item: item[
            "repeatCount"
        ],
        reverse=True,
    )

    return {
        "totalMeasures":
            total_measures,

        "activeMeasures":
            active_measures,

        "noteCount":
            note_count,

        "restCount":
            rest_count,

        "chordCount":
            chord_count,

        "notesPerMeasure":
            (
                round(
                    note_count
                    / total_measures,
                    2
                )
                if total_measures
                else 0
            ),

        "notesPerActiveMeasure":
            (
                round(
                    note_count
                    / active_measures,
                    2
                )
                if active_measures
                else 0
            ),

        "durationHistogram":
            dict(
                duration_counter
            ),

        "repeatedRhythmPatterns":
            repeated_patterns,
    }


# ============================================================
# Measure별 특징
# ============================================================

def analyze_measures(part):

    results = []

    for measure in part.get(
        "measures",
        []
    ):

        notes = []
        rests = 0
        chords = 0

        events = sort_events(
            measure.get(
                "events",
                []
            )
        )

        for event in events:

            event_type = event.get(
                "type"
            )

            if event_type == "note":

                pitch = (
                    event.get("pitch")
                    or {}
                )

                if pitch.get("midi") is not None:

                    notes.append(
                        pitch.get("midi")
                    )

            elif event_type == "rest":

                rests += 1

            elif event_type == "chord":

                chords += 1

        if notes:

            pitch_min = min(notes)
            pitch_max = max(notes)

        else:

            pitch_min = None
            pitch_max = None

        results.append({

            "measure":
                measure.get("number"),

            "noteCount":
                len(notes),

            "restCount":
                rests,

            "chordCount":
                chords,

            "minimumMidi":
                pitch_min,

            "maximumMidi":
                pitch_max,

            "pitchRangeSemitones":
                (
                    pitch_max
                    - pitch_min
                    if (
                        pitch_min
                        is not None
                        and pitch_max
                        is not None
                    )
                    else 0
                ),

            "confidence":
                measure.get(
                    "confidence"
                ),
        })

    return results


# ============================================================
# Part 분석
# ============================================================

def analyze_part(part):

    note_sequence = (
        collect_note_sequence(
            part
        )
    )

    return {

        "id":
            part.get("id"),

        "name":
            part.get("name"),

        "pitchRange":
            analyze_pitch_range(
                note_sequence
            ),

        "melodicContour":
            analyze_contour(
                note_sequence
            ),

        "rhythm":
            analyze_rhythm(
                part
            ),

        "measures":
            analyze_measures(
                part
            ),
    }


# ============================================================
# 전체 분석
# ============================================================

def analyze_music_features(data):
    """
    Web/Pipeline에서 사용할 핵심 함수

    MusicStructure dict
            ↓
    Feature dict
    """

    parts = []

    for part in data.get(
        "parts",
        []
    ):

        parts.append(
            analyze_part(part)
        )

    total_notes = sum(
        part["rhythm"]["noteCount"]
        for part in parts
    )

    total_rests = sum(
        part["rhythm"]["restCount"]
        for part in parts
    )

    return {

        "analysisType":
            "rule_based_music_features",

        "partCount":
            len(parts),

        "totalNoteCount":
            total_notes,

        "totalRestCount":
            total_rests,

        "parts":
            parts,
    }


# ============================================================
# 파일 테스트용
# ============================================================

def analyze_feature_file(
    input_path,
    output_path,
):

    input_path = Path(
        input_path
    )

    output_path = Path(
        output_path
    )

    with open(
        input_path,
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(
            file
        )

    features = (
        analyze_music_features(
            data
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            features,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return features


# ============================================================
# 단일 테스트
# ============================================================

if __name__ == "__main__":

    input_file = (
        BASE_DIR
        / "confidence_output"
        / "M01_original.json"
    )

    output_file = (
        BASE_DIR
        / "feature_output"
        / "M01_original.json"
    )

    print(
        "=" * 70
    )

    print(
        "Music Feature Analyzer"
    )

    print(
        "=" * 70
    )

    features = analyze_feature_file(
        input_file,
        output_file,
    )

    print()

    print(
        "Part 수:",
        features["partCount"]
    )

    print(
        "총 Note:",
        features["totalNoteCount"]
    )

    print(
        "총 Rest:",
        features["totalRestCount"]
    )

    for part in features["parts"]:

        print()
        print(
            "Part:",
            part["name"]
        )

        print(
            "Pitch Range:",
            part["pitchRange"]
        )

        print(
            "Contour:",
            part["melodicContour"]
        )

        print(
            "Rhythm:",
            {
                "notesPerMeasure":
                    part[
                        "rhythm"
                    ][
                        "notesPerMeasure"
                    ],

                "notesPerActiveMeasure":
                    part[
                        "rhythm"
                    ][
                        "notesPerActiveMeasure"
                    ],
            }
        )

    print()

    print(
        "출력:",
        output_file
    )

    print(
        "✅ Music Feature 분석 완료"
    )