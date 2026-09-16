from pathlib import Path
import json
import os
import re

import requests


# ============================================================
# 기본 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIDENCE_DIR = BASE_DIR / "confidence_output"
FEATURE_DIR = BASE_DIR / "feature_output"
SUMMARY_DIR = BASE_DIR / "summary_output"

SUMMARY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Local LLM 설정
# ============================================================

LOCAL_LLM_BASE_URL = os.getenv(
    "LOCAL_LLM_BASE_URL",
    "http://localhost:11434",
)

LOCAL_LLM_MODEL = os.getenv(
    "LOCAL_LLM_MODEL",
    "qwen3:8b",
)

# 기존 120초 → 180초
LOCAL_LLM_TIMEOUT = int(
    os.getenv(
        "LOCAL_LLM_TIMEOUT",
        "180",
    )
)


# 최종 전체 요약에 들어갈 Fact 최대 개수
MAX_SUMMARY_FACTS = 4


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


def save_json(
    data,
    path: Path,
):

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
# 접근성 표현 Utility
# ============================================================

NOTE_NAMES_KO = {
    "C": "도",
    "D": "레",
    "E": "미",
    "F": "파",
    "G": "솔",
    "A": "라",
    "B": "시",
}


DURATION_NAMES_KO = {
    "whole": "온음표",
    "half": "2분음표",
    "quarter": "4분음표",
    "eighth": "8분음표",
    "16th": "16분음표",
    "32nd": "32분음표",
    "64th": "64분음표",
}


def format_number(value):
    """
    4.0 -> 4
    1.75 -> 1.75
    """

    if value is None:
        return None

    try:

        value = float(value)

        if value.is_integer():
            return str(
                int(value)
            )

        return str(
            round(
                value,
                2,
            )
        )

    except Exception:

        return str(value)


def pitch_to_accessible_text(
    pitch,
):
    """
    예:
    C4  -> 가온 도(C4)
    D4  -> 레(D4)
    C#4 -> 올림 도(C#4)
    Bb4 -> 내림 시(Bb4)
    """

    if not pitch:
        return None

    pitch = str(pitch)

    match = re.match(
        r"^([A-G])([#b]?)(-?\d+)$",
        pitch,
    )

    if not match:
        return pitch

    step = match.group(1)
    accidental = match.group(2)
    octave = match.group(3)

    korean = NOTE_NAMES_KO.get(
        step,
        step,
    )

    if accidental == "#":

        korean = (
            "올림 "
            + korean
        )

    elif accidental == "b":

        korean = (
            "내림 "
            + korean
        )

    # Middle C
    if (
        step == "C"
        and accidental == ""
        and octave == "4"
    ):

        korean = "가온 도"

    return (
        f"{korean}({pitch})"
    )


def time_signature_to_text(
    value,
):
    """
    4/4 -> 4분의 4박자
    3/4 -> 4분의 3박자
    """

    if not value:
        return None

    value = str(value)

    match = re.match(
        r"^(\d+)/(\d+)$",
        value,
    )

    if not match:
        return value

    numerator = match.group(1)
    denominator = match.group(2)

    return (
        f"{denominator}분의 "
        f"{numerator}박자"
    )


# ============================================================
# Atomic Fact Catalog
# ============================================================

def build_fact_catalog(
    structure,
    features,
):
    """
    MusicStructure + Feature를
    검증 가능한 Atomic Fact 목록으로 변환한다.

    중요:
    LLM이 음악적 사실을 직접 만드는 것이 아니다.

    Python이 미리:
    - Fact
    - 사용자용 접근성 문장
    - Evidence Pointer

    를 생성한다.

    LLM은 이미 존재하는 Fact 중
    어떤 Fact를 요약에 넣을지만 선택한다.
    """

    catalog = []

    fact_counter = 1

    def add_fact(
        fact_type,
        source,
        path,
        value,
        accessible_text,
        priority=50,
        part=None,
    ):

        nonlocal fact_counter

        fact_id = (
            f"F{fact_counter:03d}"
        )

        fact_counter += 1

        fact = {
            "id": fact_id,
            "type": fact_type,
            "source": source,
            "path": path,
            "value": value,
            "accessibleText": accessible_text,
            "priority": priority,
        }

        if part is not None:
            fact["part"] = part

        catalog.append(
            fact
        )

    # ========================================================
    # Metadata
    # ========================================================

    metadata = (
        structure.get(
            "metadata",
            {},
        )
        or {}
    )

    # --------------------------------------------------------
    # Time Signature
    # --------------------------------------------------------

    time_signature = (
        metadata.get(
            "timeSignature"
        )
    )

    if time_signature:

        readable_ts = (
            time_signature_to_text(
                time_signature
            )
        )

        add_fact(
            fact_type="time_signature",
            source="music_structure",
            path="metadata.timeSignature",
            value=time_signature,
            accessible_text=(
                f"박자는 "
                f"{readable_ts}입니다."
            ),
            priority=85,
        )

    # --------------------------------------------------------
    # Tempo
    # --------------------------------------------------------

    tempo = (
        metadata.get(
            "tempo"
        )
    )

    # 실제 숫자 tempo가 있을 때만 생성
    if isinstance(
        tempo,
        (int, float),
    ):

        add_fact(
            fact_type="tempo",
            source="music_structure",
            path="metadata.tempo",
            value=tempo,
            accessible_text=(
                f"템포는 분당 "
                f"{format_number(tempo)}박입니다."
            ),
            priority=55,
        )

    # ========================================================
    # Feature Parts
    # ========================================================

    parts = (
        features.get(
            "parts",
            [],
        )
        or []
    )

    for part_index, part in enumerate(
        parts
    ):

        part_name = (
            part.get("name")
            or f"Part {part_index + 1}"
        )

        # ====================================================
        # Pitch Range
        # ====================================================

        pitch_range = (
            part.get(
                "pitchRange",
                {},
            )
            or {}
        )

        minimum_pitch = (
            pitch_range.get(
                "minimumPitch"
            )
        )

        maximum_pitch = (
            pitch_range.get(
                "maximumPitch"
            )
        )

        range_semitones = (
            pitch_range.get(
                "rangeSemitones"
            )
        )

        if (
            minimum_pitch
            and maximum_pitch
        ):

            min_text = (
                pitch_to_accessible_text(
                    minimum_pitch
                )
            )

            max_text = (
                pitch_to_accessible_text(
                    maximum_pitch
                )
            )

            # C4 → C5 특수 표현
            if (
                minimum_pitch == "C4"
                and maximum_pitch == "C5"
                and range_semitones == 12
            ):

                accessible_text = (
                    "가장 낮은 음은 "
                    "가온 도(C4)이고, "
                    "가장 높은 음은 "
                    "가온 도보다 한 옥타브 높은 "
                    "도(C5)입니다."
                )

            elif range_semitones == 12:

                accessible_text = (
                    f"가장 낮은 음은 "
                    f"{min_text}이고, "
                    f"가장 높은 음은 "
                    f"{max_text}이며, "
                    f"두 음의 간격은 "
                    f"한 옥타브입니다."
                )

            else:

                accessible_text = (
                    f"가장 낮은 음은 "
                    f"{min_text}이고, "
                    f"가장 높은 음은 "
                    f"{max_text}입니다."
                )

            add_fact(
                fact_type="pitch_range",
                source="feature",
                path=(
                    f"parts[{part_index}]"
                    f".pitchRange"
                ),
                value={
                    "minimumPitch":
                        minimum_pitch,

                    "maximumPitch":
                        maximum_pitch,

                    "rangeSemitones":
                        range_semitones,
                },
                accessible_text=(
                    accessible_text
                ),
                priority=100,
                part=part_name,
            )

        # ====================================================
        # Melodic Contour
        # ====================================================

        contour = (
            part.get(
                "melodicContour",
                {},
            )
            or {}
        )

        direction = (
            contour.get(
                "dominantDirection"
            )
        )

        contour_text_map = {

            "ASCENDING":
                (
                    "음은 전체적으로 "
                    "낮은 쪽에서 높은 쪽으로 "
                    "진행합니다."
                ),

            "DESCENDING":
                (
                    "음은 전체적으로 "
                    "높은 쪽에서 낮은 쪽으로 "
                    "진행합니다."
                ),

            "REPEATED":
                (
                    "같은 높이의 음이 "
                    "반복되는 진행이 "
                    "두드러집니다."
                ),

            "MIXED":
                (
                    "음의 상승과 하강 진행이 "
                    "함께 나타납니다."
                ),
        }

        if direction in contour_text_map:

            add_fact(
                fact_type="melodic_contour",
                source="feature",
                path=(
                    f"parts[{part_index}]"
                    f".melodicContour"
                    f".dominantDirection"
                ),
                value=direction,
                accessible_text=(
                    contour_text_map[
                        direction
                    ]
                ),
                priority=95,
                part=part_name,
            )

        # ====================================================
        # Rhythm
        # ====================================================

        rhythm = (
            part.get(
                "rhythm",
                {},
            )
            or {}
        )

        # ----------------------------------------------------
        # Active Measures
        # ----------------------------------------------------

        total_measures = (
            rhythm.get(
                "totalMeasures"
            )
        )

        active_measures = (
            rhythm.get(
                "activeMeasures"
            )
        )

        if (
            total_measures is not None
            and active_measures is not None
        ):

            add_fact(
                fact_type="active_measures",
                source="feature",
                path=(
                    f"parts[{part_index}]"
                    f".rhythm.activeMeasures"
                ),
                value={
                    "activeMeasures":
                        active_measures,

                    "totalMeasures":
                        total_measures,
                },
                accessible_text=(
                    f"전체 "
                    f"{format_number(total_measures)}마디 중 "
                    f"음표가 있는 마디는 "
                    f"{format_number(active_measures)}"
                    f"마디입니다."
                ),
                priority=80,
                part=part_name,
            )

        # ----------------------------------------------------
        # Notes Per Active Measure
        # ----------------------------------------------------

        notes_per_active = (
            rhythm.get(
                "notesPerActiveMeasure"
            )
        )

        if (
            notes_per_active is not None
            and notes_per_active > 0
        ):

            add_fact(
                fact_type=(
                    "notes_per_active_measure"
                ),
                source="feature",
                path=(
                    f"parts[{part_index}]"
                    f".rhythm"
                    f".notesPerActiveMeasure"
                ),
                value=notes_per_active,
                accessible_text=(
                    f"음표가 있는 마디에는 "
                    f"평균 "
                    f"{format_number(notes_per_active)}개의 "
                    f"음표가 있습니다."
                ),
                priority=75,
                part=part_name,
            )

        # ----------------------------------------------------
        # Duration Histogram
        # ----------------------------------------------------

        duration_histogram = (
            rhythm.get(
                "durationHistogram",
                {},
            )
            or {}
        )

        if duration_histogram:

            try:

                max_count = max(
                    duration_histogram.values()
                )

                dominant = [
                    name
                    for name, count
                    in duration_histogram.items()
                    if count == max_count
                ]

                # 가장 많이 등장하는 음표 길이가
                # 하나로 명확할 경우에만 Fact 생성
                if len(dominant) == 1:

                    duration_name = (
                        dominant[0]
                    )

                    readable_duration = (
                        DURATION_NAMES_KO.get(
                            duration_name,
                            duration_name,
                        )
                    )

                    add_fact(
                        fact_type=(
                            "dominant_duration"
                        ),
                        source="feature",
                        path=(
                            f"parts[{part_index}]"
                            f".rhythm"
                            f".durationHistogram"
                        ),
                        value={
                            "duration":
                                duration_name,

                            "count":
                                max_count,
                        },
                        accessible_text=(
                            f"음표 길이 중 "
                            f"{readable_duration}가 "
                            f"가장 많이 나타납니다."
                        ),
                        priority=70,
                        part=part_name,
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # Repeated Rhythm
        # ----------------------------------------------------

        repeated_count = (
            rhythm.get(
                "repeatedRhythmPatternCount"
            )
        )

        if repeated_count is None:

            repeated_patterns = (
                rhythm.get(
                    "repeatedRhythmPatterns",
                    [],
                )
                or []
            )

            if isinstance(
                repeated_patterns,
                (list, dict),
            ):

                repeated_count = len(
                    repeated_patterns
                )

        if (
            repeated_count is not None
            and repeated_count > 0
        ):

            add_fact(
                fact_type="repeated_rhythm",
                source="feature",
                path=(
                    f"parts[{part_index}]"
                    f".rhythm"
                    f".repeatedRhythmPatterns"
                ),
                value=repeated_count,
                accessible_text=(
                    f"반복되는 리듬 형태가 "
                    f"{format_number(repeated_count)}개 "
                    f"확인됩니다."
                ),
                priority=65,
                part=part_name,
            )

        # ----------------------------------------------------
        # Note / Rest Count
        # ----------------------------------------------------

        note_count = (
            rhythm.get(
                "noteCount"
            )
        )

        rest_count = (
            rhythm.get(
                "restCount"
            )
        )

        if (
            note_count is not None
            and rest_count is not None
        ):

            add_fact(
                fact_type="note_rest_count",
                source="feature",
                path=(
                    f"parts[{part_index}]"
                    f".rhythm"
                ),
                value={
                    "noteCount":
                        note_count,

                    "restCount":
                        rest_count,
                },
                accessible_text=(
                    f"이 파트에는 "
                    f"음표 "
                    f"{format_number(note_count)}개와 "
                    f"쉼표 "
                    f"{format_number(rest_count)}개가 "
                    f"있습니다."
                ),
                priority=45,
                part=part_name,
            )

    # ========================================================
    # Review Warning
    # ========================================================

    review = (
        structure.get(
            "review",
            {},
        )
        or {}
    )

    review_level = (
        review.get(
            "level"
        )
    )

    if review_level in {
        "MEDIUM",
        "HIGH",
    }:

        add_fact(
            fact_type="review_warning",
            source="music_structure",
            path="review",
            value={
                "level":
                    review_level,

                "reasons":
                    review.get(
                        "reasons",
                        [],
                    ),
            },
            accessible_text=(
                "악보 인식 결과에는 "
                "확인이 필요한 부분이 있습니다."
            ),
            priority=110,
        )

    return catalog


# ============================================================
# Mandatory Fact Selection
# ============================================================

def get_mandatory_fact_ids(
    catalog,
):
    """
    접근성 요약에서 반드시 포함해야 할 정보.

    현재 정책:
    1. review_warning
    2. pitch_range
    3. melodic_contour

    해당 Fact가 있을 때만 선택한다.
    """

    mandatory_types = [
        "review_warning",
        "pitch_range",
        "melodic_contour",
    ]

    selected = []

    for fact_type in mandatory_types:

        candidates = [
            fact
            for fact in catalog
            if fact["type"] == fact_type
        ]

        if not candidates:
            continue

        candidates = sorted(
            candidates,
            key=lambda x:
                x.get(
                    "priority",
                    0,
                ),
            reverse=True,
        )

        fact_id = (
            candidates[0]["id"]
        )

        if fact_id not in selected:
            selected.append(
                fact_id
            )

    return selected


# ============================================================
# Optional Fact
# ============================================================

def get_optional_catalog(
    catalog,
    mandatory_ids,
):

    mandatory_set = set(
        mandatory_ids
    )

    return [
        fact
        for fact in catalog
        if fact["id"]
        not in mandatory_set
    ]


# ============================================================
# LLM Fact View
# ============================================================

def build_llm_fact_view(
    catalog,
):
    """
    LLM에게는 필요한 정보만 제공.
    Evidence path는 Python 내부에서 유지한다.
    """

    return [
        {
            "id":
                fact["id"],

            "type":
                fact["type"],

            "description":
                fact["accessibleText"],

            "value":
                fact["value"],
        }

        for fact in catalog
    ]


# ============================================================
# Prompt
# ============================================================

def build_system_prompt(
    selection_count,
):

    return f"""
당신은 시각장애 사용자를 위한 악보 요약 정보 선택기입니다.

중요:
당신은 새로운 음악 설명 문장을 만들지 않습니다.

핵심 정보인 음역과 선율 진행 방향,
그리고 필요한 경우 악보 인식 검수 경고는
이미 시스템이 자동으로 선택했습니다.

당신은 남아 있는 Fact 중
악보 전체 구조를 이해하는 데 도움이 되는
추가 Fact ID만 선택해야 합니다.

규칙:

1. 제공된 Fact 목록에 존재하는 ID만 선택하세요.

2. 새로운 사실을 만들거나 추론하지 마세요.

3. 정확히 {selection_count}개의 Fact를 선택하세요.

4. 같은 Fact ID를 중복 선택하지 마세요.

5. 단순한 음표/쉼표 개수보다
   악보 전체의 구조를 이해하는 데
   도움이 되는 정보를 우선하세요.

6. 일반적으로 다음 순서로 우선합니다.

   - 박자
   - 실제 음표가 있는 마디 정보
   - 음표가 있는 마디의 평균 음표 수
   - 주요 음표 길이
   - 반복 리듬 정보
   - 템포
   - 단순 음표/쉼표 개수

7. 분위기, 감정, 장르,
   연주 난이도, 작곡가 의도는
   판단하지 마세요.

8. 쉼표가 많다는 이유만으로
   음악이 느리다고 판단하지 마세요.

9. Fact의 description에 없는 내용을
   임의로 해석하지 마세요.

반드시 아래 JSON 형식으로만 출력하세요.

{{
  "selectedFactIds": [
    "F001",
    "F002"
  ]
}}

설명이나 추가 문장을 출력하지 마세요.
""".strip()


def build_user_prompt(
    optional_catalog,
    selection_count,
):

    facts = (
        build_llm_fact_view(
            optional_catalog
        )
    )

    return f"""
다음 Fact 중에서
악보 전체 구조를 이해하는 데
가장 도움이 되는 Fact를
정확히 {selection_count}개 선택하세요.

Fact 목록:

{json.dumps(
    facts,
    ensure_ascii=False,
    indent=2,
)}

위 목록에 실제 존재하는
Fact ID만 선택하세요.
""".strip()


# ============================================================
# Ollama
# ============================================================

def call_local_llm(
    system_prompt,
    user_prompt,
):
    """
    Ollama /api/chat 호출.
    """

    url = (
        LOCAL_LLM_BASE_URL.rstrip("/")
        + "/api/chat"
    )

    payload = {
        "model":
            LOCAL_LLM_MODEL,

        "stream":
            False,

        "format":
            "json",

        "messages": [
            {
                "role":
                    "system",

                "content":
                    system_prompt,
            },
            {
                "role":
                    "user",

                "content":
                    user_prompt,
            },
        ],

        "options": {
            "temperature":
                0.0,
        },
    }

    response = requests.post(
        url,
        json=payload,
        timeout=LOCAL_LLM_TIMEOUT,
    )

    response.raise_for_status()

    result = (
        response.json()
    )

    message = (
        result.get(
            "message",
            {},
        )
        or {}
    )

    content = (
        message.get(
            "content"
        )
    )

    if not content:

        raise RuntimeError(
            "Local LLM 응답에서 "
            "message.content가 없습니다."
        )

    return content.strip()


# ============================================================
# LLM JSON Parsing
# ============================================================

def parse_llm_json(
    text,
):

    if not text:
        raise ValueError(
            "LLM 응답이 비어 있습니다."
        )

    text = (
        text.strip()
    )

    # ```json
    text = re.sub(
        r"^```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # ```
    text = re.sub(
        r"```$",
        "",
        text,
    )

    text = (
        text.strip()
    )

    try:

        return json.loads(
            text
        )

    except json.JSONDecodeError:

        # 앞뒤에 쓸데없는 설명이 붙어도
        # 첫 { ~ 마지막 }를 시도
        start = text.find("{")
        end = text.rfind("}")

        if (
            start != -1
            and end != -1
            and end > start
        ):

            return json.loads(
                text[
                    start:end + 1
                ]
            )

        raise


# ============================================================
# Hallucination / Selection Guard
# ============================================================

def validate_optional_selection(
    result,
    optional_catalog,
    selection_count,
):
    """
    LLM Optional Fact 선택 검증.

    검사:
    - JSON 구조
    - selectedFactIds 존재
    - 정확한 개수
    - 실제 존재하는 ID인지
    - 중복 여부
    """

    issues = []

    if not isinstance(
        result,
        dict,
    ):

        return [
            "INVALID_JSON_STRUCTURE"
        ]

    selected = (
        result.get(
            "selectedFactIds"
        )
    )

    if not isinstance(
        selected,
        list,
    ):

        return [
            "SELECTED_FACT_IDS_NOT_LIST"
        ]

    # --------------------------------------------------------
    # 선택 개수
    # --------------------------------------------------------

    if len(selected) != selection_count:

        issues.append(
            "INVALID_SELECTION_COUNT:"
            f"{len(selected)}"
            f"_EXPECTED:"
            f"{selection_count}"
        )

    # --------------------------------------------------------
    # 허용된 Fact ID
    # --------------------------------------------------------

    valid_ids = {
        fact["id"]
        for fact in optional_catalog
    }

    string_ids = []

    for fact_id in selected:

        if not isinstance(
            fact_id,
            str,
        ):

            issues.append(
                "INVALID_FACT_ID_TYPE"
            )

            continue

        string_ids.append(
            fact_id
        )

        if fact_id not in valid_ids:

            issues.append(
                f"UNKNOWN_FACT_ID:"
                f"{fact_id}"
            )

    # --------------------------------------------------------
    # 중복
    # --------------------------------------------------------

    if len(
        string_ids
    ) != len(
        set(string_ids)
    ):

        issues.append(
            "DUPLICATE_FACT_ID"
        )

    return list(
        dict.fromkeys(
            issues
        )
    )


# ============================================================
# Selection Error Retry
# ============================================================

def retry_optional_selection(
    optional_catalog,
    selection_count,
    previous_output,
    previous_issues,
):
    """
    LLM이 응답은 했지만
    Guard를 통과하지 못했을 때 1회 재요청.
    """

    facts = (
        build_llm_fact_view(
            optional_catalog
        )
    )

    system_prompt = (
        build_system_prompt(
            selection_count
        )
    )

    user_prompt = f"""
이전 Fact 선택 결과가
검증을 통과하지 못했습니다.

문제:

{json.dumps(
    previous_issues,
    ensure_ascii=False,
)}

이전 출력:

{previous_output}

허용된 Fact 목록:

{json.dumps(
    facts,
    ensure_ascii=False,
    indent=2,
)}

위 목록에 실제 존재하는
서로 다른 Fact ID를
정확히 {selection_count}개 선택하세요.

반드시 JSON만 출력하세요.

{{
  "selectedFactIds": [
    "F001",
    "F002"
  ]
}}
""".strip()

    return call_local_llm(
        system_prompt,
        user_prompt,
    )


# ============================================================
# Deterministic Fallback
# ============================================================

def deterministic_optional_selection(
    optional_catalog,
    selection_count,
):
    """
    LLM을 사용할 수 없거나
    검증에 계속 실패할 경우
    Python priority 기반으로 선택한다.
    """

    sorted_facts = sorted(
        optional_catalog,
        key=lambda x:
            x.get(
                "priority",
                0,
            ),
        reverse=True,
    )

    return [
        fact["id"]
        for fact in sorted_facts[
            :selection_count
        ]
    ]


# ============================================================
# Optional Fact Selection Main
# ============================================================

def select_optional_fact_ids(
    optional_catalog,
    selection_count,
):
    """
    Optional Fact 선택 흐름.

    1. LLM 1차
    2-A. 응답은 왔지만 Guard FAIL → 1회 Retry
    2-B. Timeout → 동일 요청 1회 Retry
    3. 그래도 실패 → deterministic fallback
    """

    # --------------------------------------------------------
    # 선택할 optional fact가 없음
    # --------------------------------------------------------

    if (
        selection_count <= 0
        or not optional_catalog
    ):

        return {
            "selectedIds":
                [],

            "selectedBy":
                "not_required",

            "retried":
                False,

            "fallbackUsed":
                False,

            "issues":
                [],

            "firstOutput":
                None,

            "retryOutput":
                None,
        }

    # --------------------------------------------------------
    # 후보 수가 선택 수와 같거나 작으면
    # 굳이 LLM 호출하지 않고 모두 선택
    # --------------------------------------------------------

    if len(
        optional_catalog
    ) <= selection_count:

        ids = [
            fact["id"]
            for fact in optional_catalog
        ]

        return {
            "selectedIds":
                ids,

            "selectedBy":
                "deterministic_all_candidates",

            "retried":
                False,

            "fallbackUsed":
                False,

            "issues":
                [],

            "firstOutput":
                None,

            "retryOutput":
                None,
        }

    system_prompt = (
        build_system_prompt(
            selection_count
        )
    )

    user_prompt = (
        build_user_prompt(
            optional_catalog,
            selection_count,
        )
    )

    first_output = None
    retry_output = None

    # ========================================================
    # 1차 LLM 호출
    # ========================================================

    try:

        first_output = (
            call_local_llm(
                system_prompt,
                user_prompt,
            )
        )

        parsed = (
            parse_llm_json(
                first_output
            )
        )

        issues = (
            validate_optional_selection(
                parsed,
                optional_catalog,
                selection_count,
            )
        )

        # ----------------------------------------------------
        # 바로 성공
        # ----------------------------------------------------

        if not issues:

            return {
                "selectedIds":
                    parsed[
                        "selectedFactIds"
                    ],

                "selectedBy":
                    "local_llm",

                "retried":
                    False,

                "fallbackUsed":
                    False,

                "issues":
                    [],

                "firstOutput":
                    first_output,

                "retryOutput":
                    None,
            }

        # ====================================================
        # LLM 응답은 왔지만 Guard FAIL
        # → Selection Retry 1회
        # ====================================================

        try:

            retry_output = (
                retry_optional_selection(
                    optional_catalog,
                    selection_count,
                    first_output,
                    issues,
                )
            )

            retry_parsed = (
                parse_llm_json(
                    retry_output
                )
            )

            retry_issues = (
                validate_optional_selection(
                    retry_parsed,
                    optional_catalog,
                    selection_count,
                )
            )

            if not retry_issues:

                return {
                    "selectedIds":
                        retry_parsed[
                            "selectedFactIds"
                        ],

                    "selectedBy":
                        "local_llm_retry",

                    "retried":
                        True,

                    "fallbackUsed":
                        False,

                    "issues":
                        [],

                    "firstOutput":
                        first_output,

                    "retryOutput":
                        retry_output,
                }

            # Retry 결과도 Guard 실패
            fallback_ids = (
                deterministic_optional_selection(
                    optional_catalog,
                    selection_count,
                )
            )

            return {
                "selectedIds":
                    fallback_ids,

                "selectedBy":
                    "deterministic_fallback",

                "retried":
                    True,

                "fallbackUsed":
                    True,

                "issues":
                    retry_issues,

                "firstOutput":
                    first_output,

                "retryOutput":
                    retry_output,
            }

        except Exception as retry_error:

            fallback_ids = (
                deterministic_optional_selection(
                    optional_catalog,
                    selection_count,
                )
            )

            return {
                "selectedIds":
                    fallback_ids,

                "selectedBy":
                    "deterministic_fallback",

                "retried":
                    True,

                "fallbackUsed":
                    True,

                "issues": [
                    (
                        "LLM_SELECTION_RETRY_ERROR:"
                        + type(
                            retry_error
                        ).__name__
                        + ":"
                        + str(
                            retry_error
                        )
                    )
                ],

                "firstOutput":
                    first_output,

                "retryOutput":
                    retry_output,
            }

    # ========================================================
    # Timeout 전용 처리
    # ========================================================

    except requests.exceptions.Timeout as timeout_error:

        # 첫 요청이 timeout이면
        # 동일 요청을 딱 한 번 다시 시도
        try:

            retry_output = (
                call_local_llm(
                    system_prompt,
                    user_prompt,
                )
            )

            retry_parsed = (
                parse_llm_json(
                    retry_output
                )
            )

            retry_issues = (
                validate_optional_selection(
                    retry_parsed,
                    optional_catalog,
                    selection_count,
                )
            )

            # Timeout Retry 성공
            if not retry_issues:

                return {
                    "selectedIds":
                        retry_parsed[
                            "selectedFactIds"
                        ],

                    "selectedBy":
                        "local_llm_timeout_retry",

                    "retried":
                        True,

                    "fallbackUsed":
                        False,

                    "issues":
                        [],

                    "firstOutput":
                        None,

                    "retryOutput":
                        retry_output,
                }

            # Timeout 후 재호출은 성공했지만
            # 선택 결과가 Guard FAIL
            fallback_ids = (
                deterministic_optional_selection(
                    optional_catalog,
                    selection_count,
                )
            )

            return {
                "selectedIds":
                    fallback_ids,

                "selectedBy":
                    "deterministic_fallback",

                "retried":
                    True,

                "fallbackUsed":
                    True,

                "issues":
                    (
                        [
                            "TIMEOUT_RETRY_SELECTION_FAILED"
                        ]
                        + retry_issues
                    ),

                "firstOutput":
                    None,

                "retryOutput":
                    retry_output,
            }

        except Exception as retry_error:

            # Timeout Retry까지 실패
            fallback_ids = (
                deterministic_optional_selection(
                    optional_catalog,
                    selection_count,
                )
            )

            return {
                "selectedIds":
                    fallback_ids,

                "selectedBy":
                    "deterministic_fallback",

                "retried":
                    True,

                "fallbackUsed":
                    True,

                "issues": [
                    (
                        "LOCAL_LLM_TIMEOUT:"
                        + type(
                            timeout_error
                        ).__name__
                        + ":"
                        + str(
                            timeout_error
                        )
                    ),
                    (
                        "LOCAL_LLM_TIMEOUT_RETRY_FAILED:"
                        + type(
                            retry_error
                        ).__name__
                        + ":"
                        + str(
                            retry_error
                        )
                    ),
                ],

                "firstOutput":
                    None,

                "retryOutput":
                    retry_output,
            }

    # ========================================================
    # 기타 LLM / Network 오류
    # ========================================================

    except Exception as e:

        fallback_ids = (
            deterministic_optional_selection(
                optional_catalog,
                selection_count,
            )
        )

        return {
            "selectedIds":
                fallback_ids,

            "selectedBy":
                "deterministic_fallback",

            "retried":
                False,

            "fallbackUsed":
                True,

            "issues": [
                (
                    "LOCAL_LLM_ERROR:"
                    + type(e).__name__
                    + ":"
                    + str(e)
                )
            ],

            "firstOutput":
                first_output,

            "retryOutput":
                retry_output,
        }


# ============================================================
# Presentation Order
# ============================================================

PRESENTATION_ORDER = {
    # 인식 결과에 문제가 있을 가능성이 있다면
    # 화면낭독기 사용자가 가장 먼저 들어야 한다.
    "review_warning": 0,

    "pitch_range": 10,
    "melodic_contour": 20,
    "time_signature": 30,
    "active_measures": 40,
    "notes_per_active_measure": 50,
    "dominant_duration": 60,
    "repeated_rhythm": 70,
    "tempo": 80,
    "note_rest_count": 90,
}


# ============================================================
# Evidence Pointer Resolution
# ============================================================

def resolve_claims(
    selected_ids,
    catalog,
):
    """
    선택된 Fact ID를
    실제 사용자용 Claim과
    Evidence Pointer로 변환한다.

    최종 문장은 LLM이 생성하지 않는다.
    """

    fact_map = {
        fact["id"]: fact
        for fact in catalog
    }

    selected_facts = []

    for fact_id in selected_ids:

        fact = (
            fact_map.get(
                fact_id
            )
        )

        if fact is not None:
            selected_facts.append(
                fact
            )

    # 사용자에게 읽히는 순서 정렬
    selected_facts = sorted(
        selected_facts,
        key=lambda fact:
            PRESENTATION_ORDER.get(
                fact["type"],
                500,
            ),
    )

    claims = []

    for fact in selected_facts:

        evidence = {
            "factId":
                fact["id"],

            "source":
                fact["source"],

            "path":
                fact["path"],

            "value":
                fact["value"],
        }

        if "part" in fact:

            evidence["part"] = (
                fact["part"]
            )

        claim = {
            "text":
                fact[
                    "accessibleText"
                ],

            "type":
                fact[
                    "type"
                ],

            "verified":
                True,

            "evidence":
                evidence,
        }

        claims.append(
            claim
        )

    return claims


# ============================================================
# Final Grounding Validation
# ============================================================

def validate_final_claims(
    claims,
    catalog,
):
    """
    최종 Claim이 실제 Fact와
    정확하게 연결돼 있는지 검증.

    확인:
    - Fact ID
    - Evidence path
    - Evidence value
    - 사용자 문장

    모두 원본 Catalog와 동일해야 한다.
    """

    issues = []

    fact_map = {
        fact["id"]: fact
        for fact in catalog
    }

    for claim in claims:

        evidence = (
            claim.get(
                "evidence",
                {},
            )
            or {}
        )

        fact_id = (
            evidence.get(
                "factId"
            )
        )

        if fact_id not in fact_map:

            issues.append(
                f"UNKNOWN_EVIDENCE_FACT:"
                f"{fact_id}"
            )

            continue

        original_fact = (
            fact_map[
                fact_id
            ]
        )

        # ----------------------------------------------------
        # Path
        # ----------------------------------------------------

        if (
            evidence.get(
                "path"
            )
            != original_fact.get(
                "path"
            )
        ):

            issues.append(
                f"EVIDENCE_PATH_MISMATCH:"
                f"{fact_id}"
            )

        # ----------------------------------------------------
        # Value
        # ----------------------------------------------------

        if (
            evidence.get(
                "value"
            )
            != original_fact.get(
                "value"
            )
        ):

            issues.append(
                f"EVIDENCE_VALUE_MISMATCH:"
                f"{fact_id}"
            )

        # ----------------------------------------------------
        # Text
        # ----------------------------------------------------

        if (
            claim.get(
                "text"
            )
            != original_fact.get(
                "accessibleText"
            )
        ):

            issues.append(
                f"CLAIM_TEXT_MISMATCH:"
                f"{fact_id}"
            )

    return list(
        dict.fromkeys(
            issues
        )
    )


# ============================================================
# Main Summarizer
# ============================================================

def summarize_music(
    structure,
    features,
):
    """
    MIDI-PHOR-inspired Grounded Summary.

    전체 흐름:

    MusicStructure / Features
              ↓
    Atomic Fact Catalog
              ↓
    Mandatory Fact
              ↓
    Qwen Optional Fact Selection
              ↓
    Hallucination / Selection Guard
              ↓
    Evidence Pointer
              ↓
    Final Grounding Validation
              ↓
    Accessible Summary
    """

    # ========================================================
    # 1. Fact Catalog
    # ========================================================

    catalog = (
        build_fact_catalog(
            structure,
            features,
        )
    )

    if not catalog:

        return {
            "text":
                None,

            "claims":
                [],

            "source":
                "midi_phor_inspired_grounded_summary",

            "model":
                LOCAL_LLM_MODEL,

            "selection": {
                "mandatoryFactIds":
                    [],

                "optionalFactIds":
                    [],

                "selectedFactIds":
                    [],

                "optionalSelectedBy":
                    "none",
            },

            "validation": {
                "passed":
                    False,

                "issues": [
                    "NO_FACTS_AVAILABLE"
                ],

                "retried":
                    False,

                "fallbackUsed":
                    False,
            },

            "debug": {
                "llmFirstOutput":
                    None,

                "llmRetryOutput":
                    None,
            },

            "factCatalog":
                [],
        }

    # ========================================================
    # 2. Mandatory Facts
    # ========================================================

    mandatory_ids = (
        get_mandatory_fact_ids(
            catalog
        )
    )

    # 최대 4개 제한
    mandatory_ids = (
        mandatory_ids[
            :MAX_SUMMARY_FACTS
        ]
    )

    # ========================================================
    # 3. Optional Candidates
    # ========================================================

    optional_catalog = (
        get_optional_catalog(
            catalog,
            mandatory_ids,
        )
    )

    remaining_slots = max(
        0,
        MAX_SUMMARY_FACTS
        - len(mandatory_ids),
    )

    optional_count = min(
        remaining_slots,
        len(optional_catalog),
    )

    # ========================================================
    # 4. Optional LLM Selection
    # ========================================================

    optional_result = (
        select_optional_fact_ids(
            optional_catalog,
            optional_count,
        )
    )

    optional_ids = (
        optional_result.get(
            "selectedIds",
            [],
        )
        or []
    )

    # ========================================================
    # 5. Final Selected IDs
    # ========================================================

    selected_ids = []

    for fact_id in (
        mandatory_ids
        + optional_ids
    ):

        if fact_id not in selected_ids:

            selected_ids.append(
                fact_id
            )

    # ========================================================
    # 6. Evidence Pointer
    # ========================================================

    claims = (
        resolve_claims(
            selected_ids,
            catalog,
        )
    )

    # ========================================================
    # 7. Final Grounding Guard
    # ========================================================

    grounding_issues = (
        validate_final_claims(
            claims,
            catalog,
        )
    )

    # ========================================================
    # 8. Summary Text
    # ========================================================

    summary_text = " ".join(
        claim["text"]
        for claim in claims
    )

    optional_issues = (
        optional_result.get(
            "issues",
            [],
        )
        or []
    )

    validation_issues = (
        optional_issues
        + grounding_issues
    )

    # --------------------------------------------------------
    # 중요:
    #
    # LLM이 timeout 나서 fallback을 사용했더라도
    # 최종 Evidence 연결이 정상이라면
    # Grounding 자체는 PASS로 본다.
    # --------------------------------------------------------

    passed = (
        len(
            grounding_issues
        )
        == 0
    )

    return {
        "text":
            summary_text,

        "claims":
            claims,

        "source":
            "midi_phor_inspired_grounded_summary",

        "model":
            LOCAL_LLM_MODEL,

        "selection": {
            "mandatoryFactIds":
                mandatory_ids,

            "optionalFactIds":
                optional_ids,

            "selectedFactIds":
                selected_ids,

            "optionalSelectedBy":
                optional_result.get(
                    "selectedBy"
                ),
        },

        "validation": {
            "passed":
                passed,

            "issues":
                validation_issues,

            "retried":
                optional_result.get(
                    "retried",
                    False,
                ),

            "fallbackUsed":
                optional_result.get(
                    "fallbackUsed",
                    False,
                ),
        },

        "debug": {
            "llmFirstOutput":
                optional_result.get(
                    "firstOutput"
                ),

            "llmRetryOutput":
                optional_result.get(
                    "retryOutput"
                ),
        },

        "factCatalog":
            catalog,
    }


# ============================================================
# Standalone Test
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "MIDI-PHOR-inspired "
        "Grounded Music Summarizer"
    )

    print(
        "=" * 70
    )

    confidence_path = (
        CONFIDENCE_DIR
        / "M01_original.json"
    )

    feature_path = (
        FEATURE_DIR
        / "M01_original.json"
    )

    if not confidence_path.exists():

        raise FileNotFoundError(
            "Confidence JSON 없음: "
            f"{confidence_path}"
        )

    if not feature_path.exists():

        raise FileNotFoundError(
            "Feature JSON 없음: "
            f"{feature_path}"
        )

    structure = (
        load_json(
            confidence_path
        )
    )

    features = (
        load_json(
            feature_path
        )
    )

    try:

        summary = (
            summarize_music(
                structure,
                features,
            )
        )

        output_path = (
            SUMMARY_DIR
            / "M01_original.json"
        )

        save_json(
            summary,
            output_path,
        )

        # ====================================================
        # Summary
        # ====================================================

        print()
        print(
            "[Summary]"
        )
        print()

        print(
            summary.get(
                "text"
            )
        )

        # ====================================================
        # Claims
        # ====================================================

        print()
        print(
            "[Claims]"
        )

        for index, claim in enumerate(
            summary.get(
                "claims",
                [],
            ),
            start=1,
        ):

            print()

            print(
                f"{index}. "
                f"{claim.get('text')}"
            )

            evidence = (
                claim.get(
                    "evidence",
                    {},
                )
                or {}
            )

            print(
                "   Evidence:",
                evidence.get(
                    "factId"
                ),
                "→",
                evidence.get(
                    "path"
                ),
                "=",
                evidence.get(
                    "value"
                ),
            )

            print(
                "   Verified:",
                claim.get(
                    "verified"
                ),
            )

        # ====================================================
        # Selection
        # ====================================================

        selection = (
            summary.get(
                "selection",
                {},
            )
            or {}
        )

        print()
        print(
            "[Selection]"
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

        # ====================================================
        # Validation
        # ====================================================

        validation = (
            summary.get(
                "validation",
                {},
            )
            or {}
        )

        print()
        print(
            "Model:",
            summary.get(
                "model"
            ),
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

        if validation.get(
            "issues"
        ):

            print(
                "Issues:",
                validation.get(
                    "issues"
                ),
            )

        # ====================================================
        # Debug
        # ====================================================

        debug = (
            summary.get(
                "debug",
                {},
            )
            or {}
        )

        if debug.get(
            "llmFirstOutput"
        ):

            print()
            print(
                "[LLM 1차 선택]"
            )

            print(
                debug.get(
                    "llmFirstOutput"
                )
            )

        if debug.get(
            "llmRetryOutput"
        ):

            print()
            print(
                "[LLM Retry 선택]"
            )

            print(
                debug.get(
                    "llmRetryOutput"
                )
            )

        print()
        print(
            "출력:",
            output_path,
        )

        print()
        print(
            "✅ Grounded Summary 완료"
        )

    except Exception as e:

        print()
        print(
            "❌ Grounded Summary 오류"
        )

        print(
            type(e).__name__,
            ":",
            e,
        )


if __name__ == "__main__":
    main()