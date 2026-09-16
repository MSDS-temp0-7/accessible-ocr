from pathlib import Path

import json
import zipfile
import xml.etree.ElementTree as ET

from statistics import mean


# ============================================================
# 기본 설정
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

MIN_CONFIDENCE_THRESHOLD = 0.67


# ============================================================
# XML 유틸
# ============================================================

def clean_tag(tag):

    if "}" in tag:
        return tag.split(
            "}",
            1,
        )[1]

    return tag


def get_confidence(element):

    ctx_grade = (
        element.attrib.get(
            "ctx-grade"
        )
    )

    grade = (
        element.attrib.get(
            "grade"
        )
    )

    if ctx_grade is not None:
        return float(
            ctx_grade
        )

    if grade is not None:
        return float(
            grade
        )

    return None


def get_bounds(element):

    for child in element:

        if clean_tag(
            child.tag
        ) != "bounds":
            continue

        x = int(
            child.attrib.get(
                "x",
                0,
            )
        )

        y = int(
            child.attrib.get(
                "y",
                0,
            )
        )

        w = int(
            child.attrib.get(
                "w",
                0,
            )
        )

        h = int(
            child.attrib.get(
                "h",
                0,
            )
        )

        return {
            "x":
                x,

            "y":
                y,

            "w":
                w,

            "h":
                h,

            "centerX":
                x + (
                    w / 2
                ),

            "centerY":
                y + (
                    h / 2
                ),
        }

    return None


# ============================================================
# OMR 데이터 추출
# ============================================================

def extract_omr_elements(
    omr_path
):

    omr_path = Path(
        omr_path
    )

    if not omr_path.exists():

        raise FileNotFoundError(
            f"OMR 파일을 찾을 수 없습니다: "
            f"{omr_path}"
        )

    all_elements = []

    with zipfile.ZipFile(
        omr_path,
        "r",
    ) as archive:

        sheet_files = [
            name
            for name
            in archive.namelist()
            if (
                name.startswith(
                    "sheet#"
                )
                and name.endswith(
                    ".xml"
                )
            )
        ]

        if not sheet_files:

            raise RuntimeError(
                "OMR 내부에서 sheet XML을 "
                "찾지 못했습니다."
            )

        for sheet_file in sheet_files:

            xml_bytes = (
                archive.read(
                    sheet_file
                )
            )

            root = ET.fromstring(
                xml_bytes
            )

            for element in root.iter():

                tag = clean_tag(
                    element.tag
                )

                if tag not in {
                    "head",
                    "head-chord",
                    "stem",
                    "rest",
                    "rest-chord",
                    "time-pair",
                    "clef",
                }:
                    continue

                confidence = (
                    get_confidence(
                        element
                    )
                )

                bounds = (
                    get_bounds(
                        element
                    )
                )

                if confidence is None:
                    continue

                all_elements.append({
                    "tag":
                        tag,

                    "id":
                        element.attrib.get(
                            "id"
                        ),

                    "staff":
                        element.attrib.get(
                            "staff"
                        ),

                    "shape":
                        element.attrib.get(
                            "shape"
                        ),

                    "grade":
                        (
                            float(
                                element.attrib[
                                    "grade"
                                ]
                            )
                            if "grade"
                            in element.attrib
                            else None
                        ),

                    "ctxGrade":
                        (
                            float(
                                element.attrib[
                                    "ctx-grade"
                                ]
                            )
                            if "ctx-grade"
                            in element.attrib
                            else None
                        ),

                    "confidence":
                        confidence,

                    "bounds":
                        bounds,

                    "sheet":
                        sheet_file,
                })

    return all_elements


# ============================================================
# OMR 순서 정렬
# ============================================================

def sort_by_musical_order(
    elements
):

    def sort_key(item):

        staff = (
            item.get(
                "staff"
            )
        )

        try:

            staff_number = int(
                staff
            )

        except (
            TypeError,
            ValueError,
        ):

            staff_number = 9999

        bounds = (
            item.get(
                "bounds"
            )
            or {}
        )

        return (
            staff_number,

            bounds.get(
                "centerX",
                999999,
            ),

            bounds.get(
                "centerY",
                999999,
            ),
        )

    return sorted(
        elements,
        key=sort_key,
    )


# ============================================================
# 가장 가까운 구조 요소
# ============================================================

def find_nearest(
    target,
    candidates,
    max_distance=100,
):

    target_bounds = (
        target.get(
            "bounds"
        )
    )

    if not target_bounds:
        return None

    tx = (
        target_bounds[
            "centerX"
        ]
    )

    ty = (
        target_bounds[
            "centerY"
        ]
    )

    best = None
    best_distance = None

    for candidate in candidates:

        bounds = (
            candidate.get(
                "bounds"
            )
        )

        if not bounds:
            continue

        if (
            target.get(
                "staff"
            )
            and candidate.get(
                "staff"
            )
            and target[
                "staff"
            ]
            != candidate[
                "staff"
            ]
        ):
            continue

        cx = (
            bounds[
                "centerX"
            ]
        )

        cy = (
            bounds[
                "centerY"
            ]
        )

        distance = (
            (
                (
                    tx - cx
                )
                ** 2
            )
            +
            (
                (
                    ty - cy
                )
                ** 2
            )
        ) ** 0.5

        if (
            best_distance
            is None
            or distance
            < best_distance
        ):

            best = (
                candidate
            )

            best_distance = (
                distance
            )

    if (
        best_distance
        is not None
        and best_distance
        <= max_distance
    ):

        return best

    return None


# ============================================================
# MusicXML 읽기
# ============================================================

def read_musicxml_root(
    mxl_path
):

    mxl_path = Path(
        mxl_path
    )

    if not mxl_path.exists():
        return None

    if (
        mxl_path.suffix.lower()
        == ".mxl"
    ):

        with zipfile.ZipFile(
            mxl_path,
            "r",
        ) as archive:

            xml_files = [
                name
                for name
                in archive.namelist()
                if (
                    name.lower()
                    .endswith(
                        ".xml"
                    )
                    and not name.startswith(
                        "META-INF/"
                    )
                )
            ]

            if not xml_files:
                return None

            xml_bytes = (
                archive.read(
                    xml_files[0]
                )
            )

            return ET.fromstring(
                xml_bytes
            )

    return ET.parse(
        mxl_path
    ).getroot()


# ============================================================
# MusicXML 실제 기호 수량
# ============================================================

def extract_musicxml_symbol_counts(
    mxl_path
):

    root = (
        read_musicxml_root(
            mxl_path
        )
    )

    if root is None:
        return None

    pitch_count = 0
    rest_count = 0

    chord_continuation_count = 0

    empty_measures = []

    parts = [
        element
        for element
        in root.iter()
        if clean_tag(
            element.tag
        ) == "part"
    ]

    for part_index, part in enumerate(
        parts
    ):

        part_id = (
            part.attrib.get(
                "id"
            )
            or f"part_{part_index + 1}"
        )

        for measure in part:

            if (
                clean_tag(
                    measure.tag
                )
                != "measure"
            ):
                continue

            measure_number = (
                measure.attrib.get(
                    "number"
                )
            )

            measure_pitch_count = 0
            measure_rest_count = 0

            for element in measure:

                if (
                    clean_tag(
                        element.tag
                    )
                    != "note"
                ):
                    continue

                child_tags = {
                    clean_tag(
                        child.tag
                    )
                    for child
                    in element
                }

                if (
                    "rest"
                    in child_tags
                ):

                    rest_count += 1

                    measure_rest_count += 1

                elif (
                    "pitch"
                    in child_tags
                    or "unpitched"
                    in child_tags
                ):

                    pitch_count += 1

                    measure_pitch_count += 1

                    if (
                        "chord"
                        in child_tags
                    ):

                        (
                            chord_continuation_count
                        ) += 1

            if (
                measure_pitch_count
                == 0
                and measure_rest_count
                == 0
            ):

                empty_measures.append({
                    "part":
                        part_id,

                    "measure":
                        measure_number,
                })

    return {
        "pitchNoteCount":
            pitch_count,

        "restCount":
            rest_count,

        "chordContinuationCount":
            chord_continuation_count,

        "emptyMeasures":
            empty_measures,
    }


# ============================================================
# 대응 MusicXML 찾기
# ============================================================

def find_corresponding_musicxml(
    json_path,
    data,
):

    json_path = Path(
        json_path
    )

    candidates = [
        BASE_DIR
        / "audiveris_output"
        / f"{json_path.stem}.mxl",

        BASE_DIR
        / "audiveris_output"
        / f"{json_path.stem}.musicxml",

        BASE_DIR
        / "audiveris_output"
        / f"{json_path.stem}.xml",
    ]

    source = (
        data.get(
            "source",
            {},
        )
        or {}
    )

    source_name = (
        source.get(
            "fileName"
        )
    )

    if source_name:

        candidates.append(
            BASE_DIR
            / "audiveris_output"
            / Path(
                source_name
            ).name
        )

    for candidate in candidates:

        if candidate.exists():
            return candidate

    return None


# ============================================================
# JSON Event 수집
# ============================================================

def pitch_midi_value(
    pitch
):

    if not isinstance(
        pitch,
        dict,
    ):
        return -999999

    midi = (
        pitch.get(
            "midi"
        )
    )

    try:
        return int(
            midi
        )

    except (
        TypeError,
        ValueError,
    ):

        return -999999


def collect_json_events(
    data
):

    """
    일반 note는 1 notehead.

    chord는 pitches 개수만큼
    notehead-equivalent로 확장한다.
    """

    notehead_units = []

    rest_events = []

    note_event_count = 0

    chord_event_count = 0

    for part_index, part in enumerate(
        data.get(
            "parts",
            [],
        )
    ):

        for measure in part.get(
            "measures",
            [],
        ):

            measure_number = (
                measure.get(
                    "number"
                )
            )

            events = sorted(
                measure.get(
                    "events",
                    [],
                ),
                key=lambda event: (
                    event.get(
                        "offset",
                        0,
                    ),
                    str(
                        event.get(
                            "voice",
                            1,
                        )
                    ),
                ),
            )

            for event_index, event in enumerate(
                events
            ):

                event_type = (
                    event.get(
                        "type"
                    )
                )

                base_reference = {
                    "partIndex":
                        part_index,

                    "measure":
                        measure_number,

                    "eventIndex":
                        event_index,

                    "event":
                        event,
                }

                # ------------------------------------------------
                # Note
                # ------------------------------------------------

                if event_type == "note":

                    note_event_count += 1

                    reference = dict(
                        base_reference
                    )

                    reference.update({
                        "unitType":
                            "note",

                        "pitchIndex":
                            None,

                        "pitch":
                            event.get(
                                "pitch"
                            ),
                    })

                    notehead_units.append(
                        reference
                    )

                # ------------------------------------------------
                # Chord
                # ------------------------------------------------

                elif event_type == "chord":

                    chord_event_count += 1

                    pitches = (
                        event.get(
                            "pitches",
                            [],
                        )
                        or []
                    )

                    indexed_pitches = list(
                        enumerate(
                            pitches
                        )
                    )

                    # OMR에서는 같은 x에서 y가 작은 음표가
                    # 높은 음이므로 높은 MIDI부터 정렬
                    indexed_pitches.sort(
                        key=lambda pair:
                            pitch_midi_value(
                                pair[1]
                            ),
                        reverse=True,
                    )

                    if not indexed_pitches:

                        indexed_pitches = [
                            (
                                None,
                                event.get(
                                    "pitch"
                                ),
                            )
                        ]

                    for (
                        pitch_index,
                        pitch,
                    ) in indexed_pitches:

                        reference = dict(
                            base_reference
                        )

                        reference.update({
                            "unitType":
                                "chord_pitch",

                            "pitchIndex":
                                pitch_index,

                            "pitch":
                                pitch,
                        })

                        notehead_units.append(
                            reference
                        )

                # ------------------------------------------------
                # Rest
                # ------------------------------------------------

                elif event_type == "rest":

                    reference = dict(
                        base_reference
                    )

                    reference.update({
                        "unitType":
                            "rest",
                    })

                    rest_events.append(
                        reference
                    )

    stats = {
        "noteEventCount":
            note_event_count,

        "chordEventCount":
            chord_event_count,

        "noteheadEquivalentCount":
            len(
                notehead_units
            ),

        "restEventCount":
            len(
                rest_events
            ),
    }

    return (
        notehead_units,
        rest_events,
        stats,
    )


# ============================================================
# Note Confidence
# ============================================================

def build_note_confidence(
    head,
    head_chord,
    stem,
):

    symbol_confidence = (
        head.get(
            "confidence"
        )
    )

    structure_confidence = (
        head_chord.get(
            "confidence"
        )
        if head_chord
        else None
    )

    stem_confidence = (
        stem.get(
            "confidence"
        )
        if stem
        else None
    )

    values = [
        value
        for value
        in [
            symbol_confidence,
            structure_confidence,
            stem_confidence,
        ]
        if value is not None
    ]

    overall = (
        min(
            values
        )
        if values
        else None
    )

    return {
        "symbol":
            symbol_confidence,

        "structure":
            structure_confidence,

        "stem":
            stem_confidence,

        "overall":
            overall,

        "source":
            "audiveris_ctx_grade",

        "matchMethod":
            "staff_x_order",

        "omrInterId":
            head.get(
                "id"
            ),
    }


def minimum_or_none(
    values
):

    values = [
        value
        for value
        in values
        if value is not None
    ]

    if not values:
        return None

    return min(
        values
    )


# ============================================================
# Note Confidence 연결
# ============================================================

def enrich_notes(
    notehead_units,
    heads,
    head_chords,
    stems,
):

    heads = (
        sort_by_musical_order(
            heads
        )
    )

    print(
        f"JSON Notehead Equivalent: "
        f"{len(notehead_units)} "
        f"/ OMR Head: "
        f"{len(heads)}"
    )

    match_count = min(
        len(
            notehead_units
        ),
        len(
            heads
        ),
    )

    chord_accumulator = {}

    for index in range(
        match_count
    ):

        json_ref = (
            notehead_units[
                index
            ]
        )

        event = (
            json_ref[
                "event"
            ]
        )

        head = (
            heads[
                index
            ]
        )

        head_chord = (
            find_nearest(
                head,
                head_chords,
                max_distance=120,
            )
        )

        stem = (
            find_nearest(
                head,
                stems,
                max_distance=120,
            )
        )

        confidence = (
            build_note_confidence(
                head,
                head_chord,
                stem,
            )
        )

        if (
            json_ref.get(
                "unitType"
            )
            == "note"
        ):

            event[
                "confidence"
            ] = confidence

        else:

            event_id = id(
                event
            )

            chord_accumulator.setdefault(
                event_id,
                {
                    "event":
                        event,

                    "items":
                        [],
                }
            )

            chord_accumulator[
                event_id
            ][
                "items"
            ].append({
                "pitchIndex":
                    json_ref.get(
                        "pitchIndex"
                    ),

                "pitch":
                    json_ref.get(
                        "pitch"
                    ),

                "confidence":
                    confidence,
            })

    # --------------------------------------------------------
    # Chord Event Confidence 집계
    # --------------------------------------------------------

    for group in (
        chord_accumulator.values()
    ):

        event = (
            group[
                "event"
            ]
        )

        items = (
            group[
                "items"
            ]
        )

        event[
            "noteheadConfidences"
        ] = items

        event[
            "confidence"
        ] = {
            "symbol":
                minimum_or_none([
                    (
                        item.get(
                            "confidence",
                            {},
                        )
                        or {}
                    ).get(
                        "symbol"
                    )
                    for item
                    in items
                ]),

            "structure":
                minimum_or_none([
                    (
                        item.get(
                            "confidence",
                            {},
                        )
                        or {}
                    ).get(
                        "structure"
                    )
                    for item
                    in items
                ]),

            "stem":
                minimum_or_none([
                    (
                        item.get(
                            "confidence",
                            {},
                        )
                        or {}
                    ).get(
                        "stem"
                    )
                    for item
                    in items
                ]),

            "overall":
                minimum_or_none([
                    (
                        item.get(
                            "confidence",
                            {},
                        )
                        or {}
                    ).get(
                        "overall"
                    )
                    for item
                    in items
                ]),

            "source":
                "audiveris_ctx_grade",

            "matchMethod":
                "staff_x_order_chord_aggregate",

            "noteheadCount":
                len(
                    items
                ),

            "omrInterIds": [
                (
                    item.get(
                        "confidence",
                        {},
                    )
                    or {}
                ).get(
                    "omrInterId"
                )
                for item
                in items
            ],
        }


# ============================================================
# Rest Confidence 연결
# ============================================================

def enrich_rests(
    rest_events,
    rests,
):

    rests = (
        sort_by_musical_order(
            rests
        )
    )

    print(
        f"JSON Rest: "
        f"{len(rest_events)} "
        f"/ OMR Rest: "
        f"{len(rests)}"
    )

    match_count = min(
        len(
            rest_events
        ),
        len(
            rests
        ),
    )

    for index in range(
        match_count
    ):

        json_ref = (
            rest_events[
                index
            ]
        )

        event = (
            json_ref[
                "event"
            ]
        )

        omr_rest = (
            rests[
                index
            ]
        )

        confidence = (
            omr_rest.get(
                "confidence"
            )
        )

        event[
            "confidence"
        ] = {
            "symbol":
                confidence,

            "overall":
                confidence,

            "source":
                "audiveris_ctx_grade",

            "matchMethod":
                "staff_x_order",

            "omrInterId":
                omr_rest.get(
                    "id"
                ),
        }


# ============================================================
# Measure Confidence
# ============================================================

def calculate_measure_confidence(
    data
):

    for part in data.get(
        "parts",
        [],
    ):

        for measure in part.get(
            "measures",
            [],
        ):

            confidence_values = []

            for event in measure.get(
                "events",
                [],
            ):

                confidence = (
                    event.get(
                        "confidence",
                        {},
                    )
                    or {}
                )

                overall = (
                    confidence.get(
                        "overall"
                    )
                )

                if overall is not None:

                    confidence_values.append(
                        overall
                    )

            if confidence_values:

                measure[
                    "confidence"
                ] = {
                    "average":
                        round(
                            mean(
                                confidence_values
                            ),
                            3,
                        ),

                    "minimum":
                        round(
                            min(
                                confidence_values
                            ),
                            3,
                        ),

                    "eventCount":
                        len(
                            confidence_values
                        ),
                }

            else:

                measure[
                    "confidence"
                ] = None


# ============================================================
# Block Confidence
# ============================================================

def calculate_block_confidence(
    data
):

    values = []

    for part in data.get(
        "parts",
        [],
    ):

        for measure in part.get(
            "measures",
            [],
        ):

            confidence = (
                measure.get(
                    "confidence"
                )
            )

            if not confidence:
                continue

            minimum = (
                confidence.get(
                    "minimum"
                )
            )

            if minimum is not None:

                values.append(
                    minimum
                )

    if not values:
        return None

    return {
        "average":
            round(
                mean(
                    values
                ),
                3,
            ),

        "minimum":
            round(
                min(
                    values
                ),
                3,
            ),

        "measureCount":
            len(
                values
            ),
    }


# ============================================================
# Review 판정
# ============================================================

def build_review_info(
    *,
    json_notehead_count,
    json_rest_count,
    omr_head_count,
    omr_rest_count,
    block_confidence,
    musicxml_counts=None,
):

    reasons = []

    # --------------------------------------------------------
    # MusicXML이 있는 경우
    # --------------------------------------------------------

    if musicxml_counts:

        musicxml_head_count = (
            musicxml_counts.get(
                "pitchNoteCount"
            )
        )

        musicxml_rest_count = (
            musicxml_counts.get(
                "restCount"
            )
        )

        empty_measures = (
            musicxml_counts.get(
                "emptyMeasures",
                [],
            )
            or []
        )

        # ====================================================
        # 빈 마디
        #
        # Audiveris가 마디에서 아무 음표/쉼표도
        # MusicXML로 내보내지 못했다.
        # 반드시 검수 대상.
        # ====================================================

        if empty_measures:

            reasons.append(
                "EMPTY_MEASURE_IN_MUSICXML"
            )

        # ----------------------------------------------------
        # OMR ↔ MusicXML
        # ----------------------------------------------------

        if (
            musicxml_head_count
            is not None
            and omr_head_count
            != musicxml_head_count
        ):

            reasons.append(
                "OMR_HEAD_MUSICXML_PITCH_COUNT_MISMATCH"
            )

        if (
            musicxml_rest_count
            is not None
            and omr_rest_count
            != musicxml_rest_count
        ):

            reasons.append(
                "OMR_REST_MUSICXML_REST_COUNT_MISMATCH"
            )

        # ----------------------------------------------------
        # MusicXML ↔ JSON
        # ----------------------------------------------------

        if (
            musicxml_head_count
            is not None
            and json_notehead_count
            != musicxml_head_count
        ):

            reasons.append(
                "MUSICXML_PITCH_JSON_NOTEHEAD_COUNT_MISMATCH"
            )

        if (
            musicxml_rest_count
            is not None
            and json_rest_count
            != musicxml_rest_count
        ):

            reasons.append(
                "MUSICXML_REST_JSON_REST_COUNT_MISMATCH"
            )

    # --------------------------------------------------------
    # MusicXML 못 찾은 경우 fallback
    # --------------------------------------------------------

    else:

        if (
            json_notehead_count
            != omr_head_count
        ):

            reasons.append(
                "OMR_HEAD_JSON_NOTEHEAD_COUNT_MISMATCH"
            )

        if (
            json_rest_count
            != omr_rest_count
        ):

            reasons.append(
                "OMR_REST_JSON_REST_COUNT_MISMATCH"
            )

    # --------------------------------------------------------
    # 구조 문제 → HIGH
    # --------------------------------------------------------

    if reasons:

        return {
            "needsReview":
                True,

            "level":
                "HIGH",

            "reasons":
                reasons,

            "threshold":
                MIN_CONFIDENCE_THRESHOLD,

            "emptyMeasures":
                (
                    musicxml_counts.get(
                        "emptyMeasures",
                        [],
                    )
                    if musicxml_counts
                    else []
                ),
        }

    # --------------------------------------------------------
    # Confidence 없음
    # --------------------------------------------------------

    if not block_confidence:

        return {
            "needsReview":
                True,

            "level":
                "HIGH",

            "reasons": [
                "CONFIDENCE_NOT_AVAILABLE"
            ],

            "threshold":
                MIN_CONFIDENCE_THRESHOLD,
        }

    minimum = (
        block_confidence.get(
            "minimum"
        )
    )

    # --------------------------------------------------------
    # 최소 confidence 낮음 → MEDIUM
    # --------------------------------------------------------

    if (
        minimum is not None
        and minimum
        <= MIN_CONFIDENCE_THRESHOLD
    ):

        return {
            "needsReview":
                True,

            "level":
                "MEDIUM",

            "reasons": [
                "LOW_MINIMUM_CONFIDENCE"
            ],

            "threshold":
                MIN_CONFIDENCE_THRESHOLD,
        }

    # --------------------------------------------------------
    # 정상
    # --------------------------------------------------------

    return {
        "needsReview":
            False,

        "level":
            "LOW",

        "reasons":
            [],

        "threshold":
            MIN_CONFIDENCE_THRESHOLD,
    }


# ============================================================
# Confidence Enrichment
# ============================================================

def enrich_confidence(
    json_path,
    omr_path,
    output_path,
):

    json_path = Path(
        json_path
    )

    omr_path = Path(
        omr_path
    )

    output_path = Path(
        output_path
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    if not json_path.exists():

        raise FileNotFoundError(
            f"JSON 파일을 찾을 수 없습니다: "
            f"{json_path}"
        )

    with open(
        json_path,
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(
            file
        )

    # --------------------------------------------------------
    # OMR
    # --------------------------------------------------------

    omr_elements = (
        extract_omr_elements(
            omr_path
        )
    )

    heads = [
        item
        for item
        in omr_elements
        if item[
            "tag"
        ] == "head"
    ]

    head_chords = [
        item
        for item
        in omr_elements
        if item[
            "tag"
        ] == "head-chord"
    ]

    stems = [
        item
        for item
        in omr_elements
        if item[
            "tag"
        ] == "stem"
    ]

    rests = [
        item
        for item
        in omr_elements
        if item[
            "tag"
        ] == "rest"
    ]

    # --------------------------------------------------------
    # JSON Event
    # --------------------------------------------------------

    (
        notehead_units,
        rest_events,
        json_stats,
    ) = collect_json_events(
        data
    )

    json_notehead_count = (
        json_stats[
            "noteheadEquivalentCount"
        ]
    )

    json_rest_count = (
        json_stats[
            "restEventCount"
        ]
    )

    omr_head_count = len(
        heads
    )

    omr_rest_count = len(
        rests
    )

    # --------------------------------------------------------
    # 원본 MusicXML
    # --------------------------------------------------------

    musicxml_path = (
        find_corresponding_musicxml(
            json_path,
            data,
        )
    )

    musicxml_counts = None

    if musicxml_path is not None:

        musicxml_counts = (
            extract_musicxml_symbol_counts(
                musicxml_path
            )
        )

    # --------------------------------------------------------
    # Confidence 연결
    # --------------------------------------------------------

    enrich_notes(
        notehead_units,
        heads,
        head_chords,
        stems,
    )

    enrich_rests(
        rest_events,
        rests,
    )

    calculate_measure_confidence(
        data
    )

    data[
        "confidence"
    ] = (
        calculate_block_confidence(
            data
        )
    )

    # --------------------------------------------------------
    # Mapping
    # --------------------------------------------------------

    mapping = {
        "omrHeadCount":
            omr_head_count,

        "jsonNoteCount":
            json_notehead_count,

        "noteCountMatch":
            (
                omr_head_count
                == json_notehead_count
            ),

        "omrRestCount":
            omr_rest_count,

        "jsonRestCount":
            json_rest_count,

        "restCountMatch":
            (
                omr_rest_count
                == json_rest_count
            ),

        "jsonNoteEventCount":
            json_stats[
                "noteEventCount"
            ],

        "jsonChordEventCount":
            json_stats[
                "chordEventCount"
            ],

        "jsonNoteheadEquivalentCount":
            json_notehead_count,
    }

    if (
        musicxml_path is not None
        and musicxml_counts is not None
    ):

        mapping.update({
            "musicXmlPath":
                str(
                    musicxml_path
                ),

            "musicXmlPitchNoteCount":
                musicxml_counts.get(
                    "pitchNoteCount"
                ),

            "musicXmlRestCount":
                musicxml_counts.get(
                    "restCount"
                ),

            "musicXmlChordContinuationCount":
                musicxml_counts.get(
                    "chordContinuationCount"
                ),

            "musicXmlEmptyMeasures":
                musicxml_counts.get(
                    "emptyMeasures",
                    [],
                ),

            "omrMusicXmlHeadCountMatch":
                (
                    omr_head_count
                    == musicxml_counts.get(
                        "pitchNoteCount"
                    )
                ),

            "omrMusicXmlRestCountMatch":
                (
                    omr_rest_count
                    == musicxml_counts.get(
                        "restCount"
                    )
                ),

            "musicXmlJsonHeadCountMatch":
                (
                    json_notehead_count
                    == musicxml_counts.get(
                        "pitchNoteCount"
                    )
                ),

            "musicXmlJsonRestCountMatch":
                (
                    json_rest_count
                    == musicxml_counts.get(
                        "restCount"
                    )
                ),
        })

    data[
        "mapping"
    ] = mapping

    # --------------------------------------------------------
    # Review
    # --------------------------------------------------------

    data[
        "review"
    ] = build_review_info(
        json_notehead_count=
            json_notehead_count,

        json_rest_count=
            json_rest_count,

        omr_head_count=
            omr_head_count,

        omr_rest_count=
            omr_rest_count,

        block_confidence=
            data.get(
                "confidence"
            ),

        musicxml_counts=
            musicxml_counts,
    )

    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

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
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return data


# ============================================================
# 단독 테스트
# ============================================================

if __name__ == "__main__":

    input_json = (
        BASE_DIR
        / "parsed_output"
        / "M01_original.json"
    )

    input_omr = (
        BASE_DIR
        / "audiveris_output"
        / "M01_original.omr"
    )

    output_json = (
        BASE_DIR
        / "confidence_output"
        / "M01_original.json"
    )

    print(
        "=" * 70
    )

    print(
        "Confidence Enricher"
    )

    print(
        "=" * 70
    )

    result = enrich_confidence(
        input_json,
        input_omr,
        output_json,
    )

    print()

    print(
        "전체 confidence:"
    )

    print(
        result.get(
            "confidence"
        )
    )

    print()

    print(
        "Mapping:"
    )

    print(
        result.get(
            "mapping"
        )
    )

    print()

    print(
        "Review:"
    )

    print(
        result.get(
            "review"
        )
    )

    print()

    print(
        "출력:",
        output_json
    )

    print()

    print(
        "✅ Confidence + Review 연결 완료"
    )