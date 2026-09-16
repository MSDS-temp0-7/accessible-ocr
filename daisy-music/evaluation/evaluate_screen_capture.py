from pathlib import Path

from collections import Counter
from difflib import SequenceMatcher

import argparse
import csv
import json
import math
import zipfile
import xml.etree.ElementTree as ET


# ============================================================
# XML Utility
# ============================================================

def clean_tag(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def get_child(element, name):
    for child in element:
        if clean_tag(child.tag) == name:
            return child

    return None


def get_children(element, name):
    return [
        child
        for child in element
        if clean_tag(child.tag) == name
    ]


def get_text(element, default=None):
    if element is None:
        return default

    if element.text is None:
        return default

    return element.text.strip()


# ============================================================
# MusicXML / MXL 읽기
# ============================================================

def load_musicxml_root(path):
    path = Path(path).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {path}"
        )

    # --------------------------------------------------------
    # 일반 XML / MusicXML
    # --------------------------------------------------------

    if path.suffix.lower() != ".mxl":
        return ET.parse(path).getroot()

    # --------------------------------------------------------
    # MXL
    # --------------------------------------------------------

    with zipfile.ZipFile(
        path,
        "r",
    ) as archive:

        root_file = None

        # ----------------------------------------------------
        # container.xml에서 실제 MusicXML 위치 찾기
        # ----------------------------------------------------

        if (
            "META-INF/container.xml"
            in archive.namelist()
        ):

            container_xml = archive.read(
                "META-INF/container.xml"
            )

            container_root = ET.fromstring(
                container_xml
            )

            for element in container_root.iter():
                if (
                    clean_tag(element.tag)
                    == "rootfile"
                ):

                    root_file = (
                        element.attrib.get(
                            "full-path"
                        )
                    )

                    if root_file:
                        break

        # ----------------------------------------------------
        # fallback
        # ----------------------------------------------------

        if not root_file:

            xml_files = [
                name
                for name in archive.namelist()
                if (
                    name.lower().endswith(".xml")
                    and not name.startswith(
                        "META-INF/"
                    )
                )
            ]

            if not xml_files:
                raise RuntimeError(
                    "MXL 내부에서 MusicXML 파일을 "
                    "찾지 못했습니다."
                )

            root_file = xml_files[0]

        xml_bytes = archive.read(
            root_file
        )

        return ET.fromstring(
            xml_bytes
        )


# ============================================================
# Pitch Utility
# ============================================================

STEP_TO_SEMITONE = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


def pitch_to_midi(
    step,
    alter,
    octave,
):
    if (
        step is None
        or octave is None
    ):
        return None

    return (
        12
        * (
            int(octave)
            + 1
        )
        + STEP_TO_SEMITONE[step]
        + int(
            alter
            or 0
        )
    )


def pitch_to_name(
    step,
    alter,
    octave,
):
    if (
        step is None
        or octave is None
    ):
        return None

    alter = int(
        alter
        or 0
    )

    if alter == 1:
        accidental = "#"

    elif alter == -1:
        accidental = "b"

    elif alter > 1:
        accidental = "#" * alter

    elif alter < -1:
        accidental = (
            "b"
            * abs(alter)
        )

    else:
        accidental = ""

    return (
        f"{step}"
        f"{accidental}"
        f"{octave}"
    )


# ============================================================
# Accidental
# ============================================================

def normalize_accidental(
    accidental_text,
    alter,
):
    if accidental_text:
        return (
            accidental_text
            .strip()
            .lower()
        )

    alter = int(
        alter
        or 0
    )

    if alter == 1:
        return "sharp"

    if alter == -1:
        return "flat"

    if alter == 2:
        return "double-sharp"

    if alter == -2:
        return "double-flat"

    return None


# ============================================================
# Note Parsing
# ============================================================

def parse_note(
    element,
    divisions,
):
    rest_element = get_child(
        element,
        "rest",
    )

    is_rest = (
        rest_element
        is not None
    )

    chord_continuation = (
        get_child(
            element,
            "chord",
        )
        is not None
    )

    # --------------------------------------------------------
    # Duration
    # --------------------------------------------------------

    duration_text = get_text(
        get_child(
            element,
            "duration",
        )
    )

    duration_quarter = None

    if (
        duration_text is not None
        and divisions
    ):

        duration_quarter = (
            float(duration_text)
            / float(divisions)
        )

    note_type = get_text(
        get_child(
            element,
            "type",
        )
    )

    dot_count = len(
        get_children(
            element,
            "dot",
        )
    )

    # --------------------------------------------------------
    # Pitch
    # --------------------------------------------------------

    step = None
    alter = 0
    octave = None

    pitch_element = get_child(
        element,
        "pitch",
    )

    if pitch_element is not None:

        step = get_text(
            get_child(
                pitch_element,
                "step",
            )
        )

        alter_text = get_text(
            get_child(
                pitch_element,
                "alter",
            ),
            "0",
        )

        octave_text = get_text(
            get_child(
                pitch_element,
                "octave",
            )
        )

        alter = int(
            float(
                alter_text
                or 0
            )
        )

        if octave_text is not None:
            octave = int(
                octave_text
            )

    pitch_name = None
    midi = None

    if not is_rest:

        pitch_name = pitch_to_name(
            step,
            alter,
            octave,
        )

        midi = pitch_to_midi(
            step,
            alter,
            octave,
        )

    # --------------------------------------------------------
    # Accidental
    # --------------------------------------------------------

    accidental = normalize_accidental(
        get_text(
            get_child(
                element,
                "accidental",
            )
        ),
        alter,
    )

    # --------------------------------------------------------
    # Tie
    # --------------------------------------------------------

    ties = []

    for tie in get_children(
        element,
        "tie",
    ):

        tie_type = (
            tie.attrib.get(
                "type"
            )
        )

        if tie_type:
            ties.append(
                tie_type
            )

    # --------------------------------------------------------
    # Notations
    # --------------------------------------------------------

    slurs = []

    notations = get_child(
        element,
        "notations",
    )

    if notations is not None:

        for notation in notations:

            tag = clean_tag(
                notation.tag
            )

            if tag == "tied":

                tie_type = (
                    notation.attrib.get(
                        "type"
                    )
                )

                if (
                    tie_type
                    and tie_type
                    not in ties
                ):
                    ties.append(
                        tie_type
                    )

            elif tag == "slur":

                slur_type = (
                    notation.attrib.get(
                        "type"
                    )
                )

                if slur_type:
                    slurs.append(
                        slur_type
                    )

    return {
        "rest":
            is_rest,

        "pitch":
            pitch_name,

        "midi":
            midi,

        "step":
            step,

        "alter":
            alter,

        "octave":
            octave,

        "accidental":
            accidental,

        "durationQuarter":
            duration_quarter,

        "type":
            note_type,

        "dots":
            dot_count,

        "chordContinuation":
            chord_continuation,

        "ties":
            sorted(
                set(ties)
            ),

        "slurs":
            sorted(
                slurs
            ),
    }


# ============================================================
# Score Parsing
# ============================================================

def parse_score(path):

    root = load_musicxml_root(
        path
    )

    result = {
        "path":
            str(
                Path(path).resolve()
            ),

        "parts":
            [],

        "measureCount":
            0,

        "pitchNoteCount":
            0,

        "restCount":
            0,

        "chordContinuationCount":
            0,

        "dynamics":
            [],

        "repeats":
            [],

        "tempos":
            [],
    }

    part_elements = [
        element
        for element in root.iter()
        if clean_tag(
            element.tag
        ) == "part"
    ]

    for (
        part_index,
        part_element,
    ) in enumerate(
        part_elements
    ):

        current_divisions = 1
        current_time = None

        # ====================================================
        # 중요 수정
        #
        # MusicXML에서 <key>가 아예 생략된 경우에도
        # 인쇄상 조표가 없는 상태로 취급.
        #
        # fifths 0 = C major / A minor 계열의
        # "조표 기호 0개" 상태.
        #
        # 따라서 최초 기본값을 None이 아니라 0으로 둔다.
        # ====================================================

        current_key = 0

        part_result = {
            "index":
                part_index,

            "measures":
                [],
        }

        # ----------------------------------------------------
        # Measure
        # ----------------------------------------------------

        for measure_element in part_element:

            if (
                clean_tag(
                    measure_element.tag
                )
                != "measure"
            ):
                continue

            measure_number = str(
                measure_element.attrib.get(
                    "number",
                    len(
                        part_result[
                            "measures"
                        ]
                    )
                    + 1,
                )
            )

            measure_result = {
                "number":
                    measure_number,

                "timeSignature":
                    current_time,

                "keySignature":
                    current_key,

                "keySignatureExplicit":
                    False,

                "notes":
                    [],

                "dynamics":
                    [],

                "repeats":
                    [],
            }

            # ------------------------------------------------
            # Attributes
            # ------------------------------------------------

            for attributes in get_children(
                measure_element,
                "attributes",
            ):

                divisions_text = get_text(
                    get_child(
                        attributes,
                        "divisions",
                    )
                )

                if divisions_text:

                    current_divisions = int(
                        divisions_text
                    )

                # --------------------------------------------
                # Time Signature
                # --------------------------------------------

                time_element = get_child(
                    attributes,
                    "time",
                )

                if time_element is not None:

                    beats = get_text(
                        get_child(
                            time_element,
                            "beats",
                        )
                    )

                    beat_type = get_text(
                        get_child(
                            time_element,
                            "beat-type",
                        )
                    )

                    if (
                        beats
                        and beat_type
                    ):

                        current_time = (
                            f"{beats}/"
                            f"{beat_type}"
                        )

                # --------------------------------------------
                # Key Signature
                # --------------------------------------------

                key_element = get_child(
                    attributes,
                    "key",
                )

                if key_element is not None:

                    fifths = get_text(
                        get_child(
                            key_element,
                            "fifths",
                        )
                    )

                    if fifths is not None:

                        current_key = int(
                            fifths
                        )

                        measure_result[
                            "keySignatureExplicit"
                        ] = True

            # ------------------------------------------------
            # 현재 상태 상속
            # ------------------------------------------------

            measure_result[
                "timeSignature"
            ] = current_time

            measure_result[
                "keySignature"
            ] = current_key

            onset_index = 0
            current_onset = None

            # ------------------------------------------------
            # 실제 Measure 요소
            # ------------------------------------------------

            for element in measure_element:

                tag = clean_tag(
                    element.tag
                )

                # ============================================
                # Direction
                # ============================================

                if tag == "direction":

                    for descendant in (
                        element.iter()
                    ):

                        descendant_tag = clean_tag(
                            descendant.tag
                        )

                        # ------------------------------------
                        # Dynamics
                        # ------------------------------------

                        if (
                            descendant_tag
                            == "dynamics"
                        ):

                            for dynamic in descendant:

                                value = clean_tag(
                                    dynamic.tag
                                )

                                entry = {
                                    "part":
                                        part_index,

                                    "measure":
                                        measure_number,

                                    "value":
                                        value,
                                }

                                measure_result[
                                    "dynamics"
                                ].append(
                                    entry
                                )

                                result[
                                    "dynamics"
                                ].append(
                                    entry
                                )

                        # ------------------------------------
                        # Tempo - sound
                        # ------------------------------------

                        elif (
                            descendant_tag
                            == "sound"
                        ):

                            tempo_value = (
                                descendant
                                .attrib
                                .get(
                                    "tempo"
                                )
                            )

                            if tempo_value:

                                entry = {
                                    "part":
                                        part_index,

                                    "measure":
                                        measure_number,

                                    "value":
                                        float(
                                            tempo_value
                                        ),
                                }

                                if (
                                    entry
                                    not in result[
                                        "tempos"
                                    ]
                                ):
                                    result[
                                        "tempos"
                                    ].append(
                                        entry
                                    )

                        # ------------------------------------
                        # Tempo - metronome
                        # ------------------------------------

                        elif (
                            descendant_tag
                            == "per-minute"
                        ):

                            tempo_value = get_text(
                                descendant
                            )

                            if tempo_value:

                                entry = {
                                    "part":
                                        part_index,

                                    "measure":
                                        measure_number,

                                    "value":
                                        float(
                                            tempo_value
                                        ),
                                }

                                if (
                                    entry
                                    not in result[
                                        "tempos"
                                    ]
                                ):
                                    result[
                                        "tempos"
                                    ].append(
                                        entry
                                    )

                # ============================================
                # Note
                # ============================================

                elif tag == "note":

                    note_data = parse_note(
                        element,
                        current_divisions,
                    )

                    # ----------------------------------------
                    # Chord onset
                    # ----------------------------------------

                    if (
                        note_data[
                            "chordContinuation"
                        ]
                        and current_onset
                        is not None
                    ):

                        onset = current_onset

                    else:

                        onset_index += 1

                        onset = onset_index

                        current_onset = onset

                    note_data[
                        "onset"
                    ] = onset

                    measure_result[
                        "notes"
                    ].append(
                        note_data
                    )

                    if note_data[
                        "rest"
                    ]:

                        result[
                            "restCount"
                        ] += 1

                    else:

                        result[
                            "pitchNoteCount"
                        ] += 1

                    if (
                        note_data[
                            "chordContinuation"
                        ]
                    ):

                        result[
                            "chordContinuationCount"
                        ] += 1

                # ============================================
                # Repeat
                # ============================================

                elif tag == "barline":

                    repeat_element = get_child(
                        element,
                        "repeat",
                    )

                    if (
                        repeat_element
                        is not None
                    ):

                        direction = (
                            repeat_element
                            .attrib
                            .get(
                                "direction"
                            )
                        )

                        entry = {
                            "part":
                                part_index,

                            "measure":
                                measure_number,

                            "direction":
                                direction,
                        }

                        measure_result[
                            "repeats"
                        ].append(
                            entry
                        )

                        result[
                            "repeats"
                        ].append(
                            entry
                        )

            part_result[
                "measures"
            ].append(
                measure_result
            )

        result[
            "parts"
        ].append(
            part_result
        )

    result[
        "measureCount"
    ] = sum(
        len(
            part[
                "measures"
            ]
        )
        for part in result[
            "parts"
        ]
    )

    return result


# ============================================================
# Symbol Token
# ============================================================

def symbol_token(note):

    if note[
        "rest"
    ]:
        return "REST"

    return (
        note.get(
            "pitch"
        )
        or "UNKNOWN"
    )


# ============================================================
# Measure Map
# ============================================================

def build_measure_map(
    score
):

    result = {}

    for part in score[
        "parts"
    ]:

        for measure in part[
            "measures"
        ]:

            key = (
                part[
                    "index"
                ],
                str(
                    measure[
                        "number"
                    ]
                ),
            )

            result[
                key
            ] = measure

    return result


# ============================================================
# Precision / Recall / F1
# ============================================================

def calculate_prf(
    correct,
    gt_total,
    pred_total,
):

    if gt_total == 0:

        recall = (
            1.0
            if pred_total == 0
            else 0.0
        )

    else:

        recall = (
            correct
            / gt_total
        )

    if pred_total == 0:

        precision = (
            1.0
            if gt_total == 0
            else 0.0
        )

    else:

        precision = (
            correct
            / pred_total
        )

    if (
        precision
        + recall
        == 0
    ):

        f1 = 0.0

    else:

        f1 = (
            2
            * precision
            * recall
            /
            (
                precision
                + recall
            )
        )

    return {
        "correct":
            correct,

        "gtTotal":
            gt_total,

        "predTotal":
            pred_total,

        "precision":
            round(
                precision,
                4,
            ),

        "recall":
            round(
                recall,
                4,
            ),

        "f1":
            round(
                f1,
                4,
            ),
    }


# ============================================================
# Multi-set 비교
# ============================================================

def count_common(
    gt_items,
    pred_items,
):

    gt_counter = Counter(
        gt_items
    )

    pred_counter = Counter(
        pred_items
    )

    common = (
        gt_counter
        & pred_counter
    )

    return sum(
        common.values()
    )


# ============================================================
# Float 비교
# ============================================================

def same_float(
    a,
    b,
):

    if (
        a is None
        or b is None
    ):

        return (
            a is None
            and b is None
        )

    return math.isclose(
        float(a),
        float(b),
        rel_tol=0.0,
        abs_tol=1e-6,
    )


# ============================================================
# Chord 추출
# ============================================================

def extract_chords(
    score
):

    chords = []

    for part in score[
        "parts"
    ]:

        for measure in part[
            "measures"
        ]:

            onset_map = {}

            for note in measure[
                "notes"
            ]:

                if note[
                    "rest"
                ]:
                    continue

                onset = note[
                    "onset"
                ]

                onset_map.setdefault(
                    onset,
                    []
                )

                onset_map[
                    onset
                ].append(
                    note[
                        "pitch"
                    ]
                )

            for pitches in (
                onset_map.values()
            ):

                if len(pitches) < 2:
                    continue

                chords.append(
                    (
                        part[
                            "index"
                        ],

                        str(
                            measure[
                                "number"
                            ]
                        ),

                        tuple(
                            sorted(
                                pitches
                            )
                        ),
                    )
                )

    return chords


# ============================================================
# Tie 추출
# ============================================================

def extract_ties(
    score
):

    events = []

    for part in score[
        "parts"
    ]:

        for measure in part[
            "measures"
        ]:

            for note in measure[
                "notes"
            ]:

                if note[
                    "rest"
                ]:
                    continue

                for tie_type in (
                    note[
                        "ties"
                    ]
                ):

                    events.append(
                        (
                            part[
                                "index"
                            ],

                            str(
                                measure[
                                    "number"
                                ]
                            ),

                            note[
                                "pitch"
                            ],

                            tie_type,
                        )
                    )

    return events


# ============================================================
# Slur 추출
# ============================================================

def extract_slurs(
    score
):

    events = []

    for part in score[
        "parts"
    ]:

        for measure in part[
            "measures"
        ]:

            for note in measure[
                "notes"
            ]:

                if note[
                    "rest"
                ]:
                    continue

                for slur_type in (
                    note[
                        "slurs"
                    ]
                ):

                    events.append(
                        (
                            part[
                                "index"
                            ],

                            str(
                                measure[
                                    "number"
                                ]
                            ),

                            note[
                                "pitch"
                            ],

                            slur_type,
                        )
                    )

    return events


# ============================================================
# Main Comparison
# ============================================================

def compare_scores(
    gt,
    pred,
):

    gt_measures = build_measure_map(
        gt
    )

    pred_measures = build_measure_map(
        pred
    )

    measure_keys = set(
        gt_measures.keys()
    )

    measure_keys.update(
        pred_measures.keys()
    )

    def measure_sort_key(item):

        part_index = item[0]
        number = item[1]

        try:
            numeric = int(
                number
            )

        except ValueError:
            numeric = 999999

        return (
            part_index,
            numeric,
            number,
        )

    measure_keys = sorted(
        measure_keys,
        key=measure_sort_key,
    )

    pitch_correct = 0
    rest_correct = 0

    duration_correct = 0
    duration_total = 0

    accidental_correct = 0
    accidental_total = 0

    time_correct = 0
    time_total = 0

    key_correct = 0
    key_total = 0

    per_measure = []

    # ========================================================
    # Measure 단위 비교
    # ========================================================

    for key in measure_keys:

        gt_measure = gt_measures.get(
            key
        )

        pred_measure = pred_measures.get(
            key
        )

        if gt_measure is None:

            gt_measure = {
                "notes": [],
                "timeSignature": None,
                "keySignature": 0,
                "keySignatureExplicit": False,
            }

        if pred_measure is None:

            pred_measure = {
                "notes": [],
                "timeSignature": None,
                "keySignature": 0,
                "keySignatureExplicit": False,
            }

        gt_notes = gt_measure[
            "notes"
        ]

        pred_notes = pred_measure[
            "notes"
        ]

        gt_tokens = [
            symbol_token(
                note
            )
            for note in gt_notes
        ]

        pred_tokens = [
            symbol_token(
                note
            )
            for note in pred_notes
        ]

        matcher = SequenceMatcher(
            None,
            gt_tokens,
            pred_tokens,
            autojunk=False,
        )

        missing = []
        extra = []

        measure_pitch_correct = 0
        measure_rest_correct = 0

        # ----------------------------------------------------
        # Alignment
        # ----------------------------------------------------

        for (
            tag,
            i1,
            i2,
            j1,
            j2,
        ) in matcher.get_opcodes():

            if tag == "equal":

                length = (
                    i2 - i1
                )

                for offset in range(
                    length
                ):

                    gt_note = gt_notes[
                        i1
                        + offset
                    ]

                    pred_note = pred_notes[
                        j1
                        + offset
                    ]

                    # -----------------------------------------
                    # Rest
                    # -----------------------------------------

                    if (
                        gt_note[
                            "rest"
                        ]
                        and pred_note[
                            "rest"
                        ]
                    ):

                        rest_correct += 1
                        measure_rest_correct += 1

                    # -----------------------------------------
                    # Pitch
                    # -----------------------------------------

                    elif (
                        not gt_note[
                            "rest"
                        ]
                        and not pred_note[
                            "rest"
                        ]
                    ):

                        pitch_correct += 1
                        measure_pitch_correct += 1

                    # -----------------------------------------
                    # Duration
                    # -----------------------------------------

                    duration_total += 1

                    if same_float(
                        gt_note[
                            "durationQuarter"
                        ],
                        pred_note[
                            "durationQuarter"
                        ],
                    ):

                        duration_correct += 1

                    # -----------------------------------------
                    # Accidental
                    # -----------------------------------------

                    if (
                        not gt_note[
                            "rest"
                        ]
                        and gt_note[
                            "accidental"
                        ]
                        is not None
                    ):

                        accidental_total += 1

                        if (
                            gt_note[
                                "accidental"
                            ]
                            ==
                            pred_note[
                                "accidental"
                            ]
                        ):

                            accidental_correct += 1

            elif tag == "delete":

                missing.extend(
                    gt_tokens[
                        i1:i2
                    ]
                )

            elif tag == "insert":

                extra.extend(
                    pred_tokens[
                        j1:j2
                    ]
                )

            elif tag == "replace":

                missing.extend(
                    gt_tokens[
                        i1:i2
                    ]
                )

                extra.extend(
                    pred_tokens[
                        j1:j2
                    ]
                )

        # ----------------------------------------------------
        # Time Signature
        # ----------------------------------------------------

        if (
            key in gt_measures
            and key in pred_measures
        ):

            time_total += 1

            if (
                gt_measure.get(
                    "timeSignature"
                )
                ==
                pred_measure.get(
                    "timeSignature"
                )
            ):

                time_correct += 1

            # ------------------------------------------------
            # Effective Key Signature
            # ------------------------------------------------

            key_total += 1

            gt_key = gt_measure.get(
                "keySignature",
                0,
            )

            pred_key = pred_measure.get(
                "keySignature",
                0,
            )

            # 방어적 정규화
            if gt_key is None:
                gt_key = 0

            if pred_key is None:
                pred_key = 0

            if (
                gt_key
                == pred_key
            ):

                key_correct += 1

        per_measure.append({
            "part":
                key[0],

            "measure":
                key[1],

            "gtPitchCount":
                sum(
                    1
                    for note in gt_notes
                    if not note[
                        "rest"
                    ]
                ),

            "predPitchCount":
                sum(
                    1
                    for note in pred_notes
                    if not note[
                        "rest"
                    ]
                ),

            "gtRestCount":
                sum(
                    1
                    for note in gt_notes
                    if note[
                        "rest"
                    ]
                ),

            "predRestCount":
                sum(
                    1
                    for note in pred_notes
                    if note[
                        "rest"
                    ]
                ),

            "pitchCorrect":
                measure_pitch_correct,

            "restCorrect":
                measure_rest_correct,

            "missing":
                missing,

            "extra":
                extra,

            "gtTimeSignature":
                gt_measure.get(
                    "timeSignature"
                ),

            "predTimeSignature":
                pred_measure.get(
                    "timeSignature"
                ),

            "gtKeySignature":
                gt_measure.get(
                    "keySignature",
                    0,
                ),

            "predKeySignature":
                pred_measure.get(
                    "keySignature",
                    0,
                ),

            "gtKeySignatureExplicit":
                gt_measure.get(
                    "keySignatureExplicit",
                    False,
                ),

            "predKeySignatureExplicit":
                pred_measure.get(
                    "keySignatureExplicit",
                    False,
                ),
        })

    # ========================================================
    # Pitch
    # ========================================================

    pitch_metric = calculate_prf(
        pitch_correct,
        gt[
            "pitchNoteCount"
        ],
        pred[
            "pitchNoteCount"
        ],
    )

    # ========================================================
    # Rest
    # ========================================================

    rest_metric = calculate_prf(
        rest_correct,
        gt[
            "restCount"
        ],
        pred[
            "restCount"
        ],
    )

    # ========================================================
    # Duration
    # ========================================================

    duration_accuracy = (
        duration_correct
        / duration_total
        if duration_total
        else 1.0
    )

    # ========================================================
    # Accidental
    # ========================================================

    accidental_accuracy = (
        accidental_correct
        / accidental_total
        if accidental_total
        else 1.0
    )

    # ========================================================
    # Time Signature
    # ========================================================

    time_accuracy = (
        time_correct
        / time_total
        if time_total
        else 1.0
    )

    # ========================================================
    # Key Signature
    # ========================================================

    key_accuracy = (
        key_correct
        / key_total
        if key_total
        else 1.0
    )

    # ========================================================
    # Chord
    # ========================================================

    gt_chords = extract_chords(
        gt
    )

    pred_chords = extract_chords(
        pred
    )

    chord_correct = count_common(
        gt_chords,
        pred_chords,
    )

    chord_metric = calculate_prf(
        chord_correct,
        len(gt_chords),
        len(pred_chords),
    )

    # ========================================================
    # Tie
    # ========================================================

    gt_ties = extract_ties(
        gt
    )

    pred_ties = extract_ties(
        pred
    )

    tie_correct = count_common(
        gt_ties,
        pred_ties,
    )

    tie_metric = calculate_prf(
        tie_correct,
        len(gt_ties),
        len(pred_ties),
    )

    # ========================================================
    # Slur
    # ========================================================

    gt_slurs = extract_slurs(
        gt
    )

    pred_slurs = extract_slurs(
        pred
    )

    slur_correct = count_common(
        gt_slurs,
        pred_slurs,
    )

    slur_metric = calculate_prf(
        slur_correct,
        len(gt_slurs),
        len(pred_slurs),
    )

    # ========================================================
    # Dynamics
    # ========================================================

    gt_dynamics = [
        (
            item[
                "part"
            ],
            item[
                "measure"
            ],
            item[
                "value"
            ],
        )
        for item in gt[
            "dynamics"
        ]
    ]

    pred_dynamics = [
        (
            item[
                "part"
            ],
            item[
                "measure"
            ],
            item[
                "value"
            ],
        )
        for item in pred[
            "dynamics"
        ]
    ]

    dynamic_correct = count_common(
        gt_dynamics,
        pred_dynamics,
    )

    dynamic_metric = calculate_prf(
        dynamic_correct,
        len(gt_dynamics),
        len(pred_dynamics),
    )

    # ========================================================
    # Repeat
    # ========================================================

    gt_repeats = [
        (
            item[
                "part"
            ],
            item[
                "measure"
            ],
            item[
                "direction"
            ],
        )
        for item in gt[
            "repeats"
        ]
    ]

    pred_repeats = [
        (
            item[
                "part"
            ],
            item[
                "measure"
            ],
            item[
                "direction"
            ],
        )
        for item in pred[
            "repeats"
        ]
    ]

    repeat_correct = count_common(
        gt_repeats,
        pred_repeats,
    )

    repeat_metric = calculate_prf(
        repeat_correct,
        len(gt_repeats),
        len(pred_repeats),
    )

    # ========================================================
    # Tempo
    # ========================================================

    gt_tempo = None
    pred_tempo = None

    if gt[
        "tempos"
    ]:

        gt_tempo = (
            gt[
                "tempos"
            ][0][
                "value"
            ]
        )

    if pred[
        "tempos"
    ]:

        pred_tempo = (
            pred[
                "tempos"
            ][0][
                "value"
            ]
        )

    tempo_match = same_float(
        gt_tempo,
        pred_tempo,
    )

    # ========================================================
    # Prediction Empty Measure
    # ========================================================

    pred_empty_measures = []

    for part in pred[
        "parts"
    ]:

        for measure in part[
            "measures"
        ]:

            if len(
                measure[
                    "notes"
                ]
            ) == 0:

                pred_empty_measures.append({
                    "part":
                        part[
                            "index"
                        ],

                    "measure":
                        str(
                            measure[
                                "number"
                            ]
                        ),
                })

    return {
        "measure": {
            "gtCount":
                gt[
                    "measureCount"
                ],

            "predCount":
                pred[
                    "measureCount"
                ],

            "match":
                (
                    gt[
                        "measureCount"
                    ]
                    ==
                    pred[
                        "measureCount"
                    ]
                ),
        },

        "pitch":
            pitch_metric,

        "rest":
            rest_metric,

        "duration": {
            "correct":
                duration_correct,

            "totalCompared":
                duration_total,

            "accuracy":
                round(
                    duration_accuracy,
                    4,
                ),
        },

        "accidental": {
            "correct":
                accidental_correct,

            "gtEvaluated":
                accidental_total,

            "accuracy":
                round(
                    accidental_accuracy,
                    4,
                ),
        },

        "timeSignature": {
            "correct":
                time_correct,

            "total":
                time_total,

            "accuracy":
                round(
                    time_accuracy,
                    4,
                ),
        },

        "keySignature": {
            "correct":
                key_correct,

            "total":
                key_total,

            "accuracy":
                round(
                    key_accuracy,
                    4,
                ),

            "normalization":
                (
                    "Missing initial <key> "
                    "is treated as fifths=0"
                ),
        },

        "chord":
            chord_metric,

        "tie":
            tie_metric,

        "slur":
            slur_metric,

        "dynamic":
            dynamic_metric,

        "repeat":
            repeat_metric,

        "tempo": {
            "gt":
                gt_tempo,

            "pred":
                pred_tempo,

            "match":
                tempo_match,
        },

        "predEmptyMeasures":
            pred_empty_measures,

        "perMeasure":
            per_measure,
    }


# ============================================================
# 저장
# ============================================================

def save_result(
    result,
    output_dir,
    name,
):

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = (
        output_dir
        / f"{name}_evaluation.json"
    )

    csv_path = (
        output_dir
        / f"{name}_evaluation.csv"
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    with open(
        json_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    row = {
        "name":
            name,

        "measure_gt":
            result[
                "measure"
            ][
                "gtCount"
            ],

        "measure_pred":
            result[
                "measure"
            ][
                "predCount"
            ],

        "pitch_precision":
            result[
                "pitch"
            ][
                "precision"
            ],

        "pitch_recall":
            result[
                "pitch"
            ][
                "recall"
            ],

        "pitch_f1":
            result[
                "pitch"
            ][
                "f1"
            ],

        "rest_precision":
            result[
                "rest"
            ][
                "precision"
            ],

        "rest_recall":
            result[
                "rest"
            ][
                "recall"
            ],

        "rest_f1":
            result[
                "rest"
            ][
                "f1"
            ],

        "duration_accuracy":
            result[
                "duration"
            ][
                "accuracy"
            ],

        "accidental_accuracy":
            result[
                "accidental"
            ][
                "accuracy"
            ],

        "time_signature_accuracy":
            result[
                "timeSignature"
            ][
                "accuracy"
            ],

        "key_signature_accuracy":
            result[
                "keySignature"
            ][
                "accuracy"
            ],

        "chord_f1":
            result[
                "chord"
            ][
                "f1"
            ],

        "tie_f1":
            result[
                "tie"
            ][
                "f1"
            ],

        "slur_f1":
            result[
                "slur"
            ][
                "f1"
            ],

        "dynamic_f1":
            result[
                "dynamic"
            ][
                "f1"
            ],

        "repeat_f1":
            result[
                "repeat"
            ][
                "f1"
            ],

        "tempo_match":
            result[
                "tempo"
            ][
                "match"
            ],

        "empty_measures":
            json.dumps(
                result[
                    "predEmptyMeasures"
                ],
                ensure_ascii=False,
            ),
    }

    with open(
        csv_path,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(
                row.keys()
            ),
        )

        writer.writeheader()

        writer.writerow(
            row
        )

    return (
        json_path,
        csv_path,
    )


# ============================================================
# 출력 Utility
# ============================================================

def print_prf(
    name,
    metric,
):

    print(
        f"{name}: "
        f"P={metric['precision']:.4f}, "
        f"R={metric['recall']:.4f}, "
        f"F1={metric['f1']:.4f} "
        f"| correct={metric['correct']} "
        f"/ GT={metric['gtTotal']} "
        f"/ Pred={metric['predTotal']}"
    )


# ============================================================
# 결과 출력
# ============================================================

def print_result(
    result,
):

    print()

    print(
        "=" * 72
    )

    print(
        "Ground Truth Accuracy Evaluation"
    )

    print(
        "=" * 72
    )

    print(
        "Measure:",
        result[
            "measure"
        ],
    )

    print()

    print_prf(
        "Pitch",
        result[
            "pitch"
        ],
    )

    print_prf(
        "Rest",
        result[
            "rest"
        ],
    )

    print()

    print(
        "Duration Accuracy:",
        result[
            "duration"
        ][
            "accuracy"
        ],
    )

    print(
        "Accidental Accuracy:",
        result[
            "accidental"
        ][
            "accuracy"
        ],
    )

    print(
        "Time Signature Accuracy:",
        result[
            "timeSignature"
        ][
            "accuracy"
        ],
    )

    print(
        "Key Signature Accuracy:",
        result[
            "keySignature"
        ][
            "accuracy"
        ],
    )

    print()

    print_prf(
        "Chord",
        result[
            "chord"
        ],
    )

    print_prf(
        "Tie",
        result[
            "tie"
        ],
    )

    print_prf(
        "Slur",
        result[
            "slur"
        ],
    )

    print_prf(
        "Dynamic",
        result[
            "dynamic"
        ],
    )

    print_prf(
        "Repeat",
        result[
            "repeat"
        ],
    )

    print()

    print(
        "Tempo:",
        result[
            "tempo"
        ],
    )

    print()

    print(
        "Prediction Empty Measures:",
        result[
            "predEmptyMeasures"
        ],
    )

    print()

    print(
        "마디별 누락 / 추가:"
    )

    found_issue = False

    for measure in result[
        "perMeasure"
    ]:

        if (
            measure[
                "missing"
            ]
            or measure[
                "extra"
            ]
        ):

            found_issue = True

            print(
                f"Part {measure['part']} "
                f"/ Measure {measure['measure']} "
                f"/ missing={measure['missing']} "
                f"/ extra={measure['extra']}"
            )

    if not found_issue:

        print(
            "없음"
        )


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Ground Truth MusicXML과 "
            "Audiveris 결과 MusicXML을 비교합니다."
        )
    )

    parser.add_argument(
        "--gt",
        required=True,
        help=(
            "Ground Truth "
            ".musicxml/.xml/.mxl"
        ),
    )

    parser.add_argument(
        "--pred",
        required=True,
        help=(
            "Audiveris 결과 "
            ".mxl/.musicxml/.xml"
        ),
    )

    parser.add_argument(
        "--name",
        default=None,
        help=(
            "실험 이름. "
            "생략 시 prediction 파일명 사용"
        ),
    )

    parser.add_argument(
        "--output-dir",
        default=(
            "evaluation/"
            "screen_capture"
        ),
    )

    args = parser.parse_args()

    gt_path = Path(
        args.gt
    )

    pred_path = Path(
        args.pred
    )

    name = (
        args.name
        or pred_path.stem
    )

    print(
        "Ground Truth:",
        gt_path.resolve(),
    )

    print(
        "Prediction:",
        pred_path.resolve(),
    )

    print()

    # --------------------------------------------------------
    # Parse
    # --------------------------------------------------------

    gt = parse_score(
        gt_path
    )

    pred = parse_score(
        pred_path
    )

    print(
        "GT:"
    )

    print(
        "  Measure:",
        gt[
            "measureCount"
        ],
    )

    print(
        "  Pitch:",
        gt[
            "pitchNoteCount"
        ],
    )

    print(
        "  Rest:",
        gt[
            "restCount"
        ],
    )

    print()

    print(
        "Prediction:"
    )

    print(
        "  Measure:",
        pred[
            "measureCount"
        ],
    )

    print(
        "  Pitch:",
        pred[
            "pitchNoteCount"
        ],
    )

    print(
        "  Rest:",
        pred[
            "restCount"
        ],
    )

    # --------------------------------------------------------
    # Compare
    # --------------------------------------------------------

    result = compare_scores(
        gt,
        pred,
    )

    result = {
        "name":
            name,

        "groundTruth":
            str(
                gt_path.resolve()
            ),

        "prediction":
            str(
                pred_path.resolve()
            ),

        **result,
    }

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    (
        json_path,
        csv_path,
    ) = save_result(
        result,
        args.output_dir,
        name,
    )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print_result(
        result
    )

    print()

    print(
        "JSON:",
        json_path.resolve(),
    )

    print(
        "CSV:",
        csv_path.resolve(),
    )


if __name__ == "__main__":
    main()