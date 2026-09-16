from pathlib import Path

import json
import sys
import zipfile
import xml.etree.ElementTree as ET

from music21 import (
    bar,
    chord,
    converter,
    dynamics,
    key,
    meter,
    note,
    spanner,
    stream,
    tempo,
)


# =============================================================
# MusicXML Parser
# =============================================================


class MusicXMLParser:

    def __init__(self, musicxml_path):

        self.musicxml_path = Path(
            musicxml_path
        ).resolve()

        if not self.musicxml_path.exists():
            raise FileNotFoundError(
                f"MusicXML 파일을 찾을 수 없습니다: "
                f"{self.musicxml_path}"
            )

        # -----------------------------------------------------
        # 중요
        #
        # music21이 빈 마디에 자동으로 Rest를 만드는 경우가 있다.
        # 그래서 music21 parse 전에 원본 MusicXML의
        # 마디별 note/rest 존재 여부를 따로 저장한다.
        # -----------------------------------------------------

        self.source_measure_info = (
            self._load_source_measure_info()
        )

        self.score = converter.parse(
            str(
                self.musicxml_path
            )
        )

    # =========================================================
    # XML Utility
    # =========================================================

    @staticmethod
    def _clean_xml_tag(tag):

        if "}" in tag:
            return tag.split(
                "}",
                1,
            )[1]

        return tag

    # =========================================================
    # 원본 MusicXML 읽기
    # =========================================================

    def _load_source_xml_root(self):

        suffix = (
            self.musicxml_path
            .suffix
            .lower()
        )

        # -----------------------------------------------------
        # .mxl
        # -----------------------------------------------------

        if suffix == ".mxl":

            with zipfile.ZipFile(
                self.musicxml_path,
                "r",
            ) as archive:

                xml_files = [
                    name
                    for name
                    in archive.namelist()
                    if (
                        name.lower().endswith(
                            ".xml"
                        )
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

                xml_bytes = archive.read(
                    xml_files[0]
                )

                return ET.fromstring(
                    xml_bytes
                )

        # -----------------------------------------------------
        # .xml / .musicxml
        # -----------------------------------------------------

        return ET.parse(
            self.musicxml_path
        ).getroot()

    # =========================================================
    # 원본 Measure 정보
    # =========================================================

    def _load_source_measure_info(self):

        """
        music21 변환 전의 MusicXML에서
        각 파트 / 마디의 실제 note/rest 개수를 저장한다.

        목적:
        music21이 빈 마디에 자동 생성하는 whole rest를
        실제 악보 기호로 잘못 처리하지 않기 위함.
        """

        root = (
            self._load_source_xml_root()
        )

        result = {}

        parts = [
            element
            for element
            in root.iter()
            if self._clean_xml_tag(
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
                    self._clean_xml_tag(
                        measure.tag
                    )
                    != "measure"
                ):
                    continue

                measure_number = str(
                    measure.attrib.get(
                        "number"
                    )
                )

                note_count = 0
                rest_count = 0

                for element in measure:

                    if (
                        self._clean_xml_tag(
                            element.tag
                        )
                        != "note"
                    ):
                        continue

                    child_tags = {
                        self._clean_xml_tag(
                            child.tag
                        )
                        for child
                        in element
                    }

                    if "rest" in child_tags:

                        rest_count += 1

                    elif (
                        "pitch" in child_tags
                        or "unpitched"
                        in child_tags
                    ):

                        note_count += 1

                result[
                    (
                        part_index,
                        measure_number,
                    )
                ] = {
                    "partId":
                        part_id,

                    "noteCount":
                        note_count,

                    "restCount":
                        rest_count,

                    "empty":
                        (
                            note_count == 0
                            and rest_count == 0
                        ),
                }

        return result

    # =========================================================
    # 원본에서 빈 마디인지 확인
    # =========================================================

    def _is_source_measure_empty(
        self,
        part_index,
        measure_number,
    ):

        info = (
            self.source_measure_info.get(
                (
                    part_index,
                    str(
                        measure_number
                    ),
                )
            )
        )

        if info is None:
            return False

        return bool(
            info.get(
                "empty",
                False,
            )
        )

    # =========================================================
    # Voice
    # =========================================================

    @staticmethod
    def _extract_voice(element):

        voice = (
            element.getContextByClass(
                stream.Voice
            )
        )

        if voice is None:
            return 1

        voice_id = getattr(
            voice,
            "id",
            None,
        )

        if voice_id is None:
            return 1

        return voice_id

    # =========================================================
    # Pitch
    # =========================================================

    @staticmethod
    def _pitch_to_dict(pitch):

        return {
            "step":
                pitch.step,

            "alter":
                (
                    int(
                        pitch.accidental.alter
                    )
                    if pitch.accidental
                    is not None
                    else 0
                ),

            "octave":
                pitch.octave,

            "name":
                pitch.nameWithOctave,

            "midi":
                pitch.midi,
        }

    # =========================================================
    # Tie
    # =========================================================

    @staticmethod
    def _extract_tie(element):

        tie = getattr(
            element,
            "tie",
            None,
        )

        if tie is None:
            return None

        return tie.type

    # =========================================================
    # Slur
    # =========================================================

    @staticmethod
    def _extract_slur(element):

        result = []

        try:

            sites = (
                element.getSpannerSites()
            )

        except Exception:

            return result

        for site in sites:

            if not isinstance(
                site,
                spanner.Slur,
            ):
                continue

            spanned = list(
                site.getSpannedElements()
            )

            if not spanned:
                continue

            if element is spanned[0]:

                slur_type = "start"

            elif element is spanned[-1]:

                slur_type = "stop"

            else:

                slur_type = "continue"

            result.append({
                "type":
                    slur_type,
            })

        return result

    # =========================================================
    # Articulation
    # =========================================================

    @staticmethod
    def _extract_articulations(element):

        articulations = getattr(
            element,
            "articulations",
            [],
        )

        result = []

        for articulation in articulations:

            name = (
                articulation
                .__class__
                .__name__
            )

            result.append(
                name.lower()
            )

        return result

    # =========================================================
    # Dynamic
    # =========================================================

    @staticmethod
    def _extract_dynamic(element):

        try:

            dynamic = (
                element.getContextByClass(
                    dynamics.Dynamic
                )
            )

        except Exception:

            return None

        if dynamic is None:
            return None

        return getattr(
            dynamic,
            "value",
            None,
        )

    # =========================================================
    # Note
    # =========================================================

    def _parse_note(
        self,
        element,
        measure,
    ):

        return {
            "type":
                "note",

            "offset":
                round(
                    float(
                        element.getOffsetInHierarchy(
                            measure
                        )
                    ),
                    3,
                ),

            "voice":
                self._extract_voice(
                    element
                ),

            "pitch":
                self._pitch_to_dict(
                    element.pitch
                ),

            "duration": {
                "quarterLength":
                    float(
                        element
                        .duration
                        .quarterLength
                    ),

                "type":
                    element.duration.type,

                "dots":
                    element.duration.dots,
            },

            "rest":
                False,

            "chord":
                False,

            "tie":
                self._extract_tie(
                    element
                ),

            "slur":
                self._extract_slur(
                    element
                ),

            "articulations":
                self._extract_articulations(
                    element
                ),

            "dynamic":
                self._extract_dynamic(
                    element
                ),
        }

    # =========================================================
    # Rest
    # =========================================================

    def _parse_rest(
        self,
        element,
        measure,
    ):

        return {
            "type":
                "rest",

            "offset":
                round(
                    float(
                        element.getOffsetInHierarchy(
                            measure
                        )
                    ),
                    3,
                ),

            "voice":
                self._extract_voice(
                    element
                ),

            "pitch":
                None,

            "duration": {
                "quarterLength":
                    float(
                        element
                        .duration
                        .quarterLength
                    ),

                "type":
                    element.duration.type,

                "dots":
                    element.duration.dots,
            },

            "rest":
                True,

            "chord":
                False,

            "tie":
                None,

            "slur":
                [],

            "articulations":
                [],

            "dynamic":
                None,
        }

    # =========================================================
    # Chord
    # =========================================================

    def _parse_chord(
        self,
        element,
        measure,
    ):

        pitches = [
            self._pitch_to_dict(
                pitch
            )
            for pitch
            in element.pitches
        ]

        return {
            "type":
                "chord",

            "offset":
                round(
                    float(
                        element.getOffsetInHierarchy(
                            measure
                        )
                    ),
                    3,
                ),

            "voice":
                self._extract_voice(
                    element
                ),

            "pitch":
                None,

            "pitches":
                pitches,

            "duration": {
                "quarterLength":
                    float(
                        element
                        .duration
                        .quarterLength
                    ),

                "type":
                    element.duration.type,

                "dots":
                    element.duration.dots,
            },

            "rest":
                False,

            "chord":
                True,

            "tie":
                None,

            "slur":
                self._extract_slur(
                    element
                ),

            "articulations":
                self._extract_articulations(
                    element
                ),

            "dynamic":
                self._extract_dynamic(
                    element
                ),
        }

    # =========================================================
    # Barline
    # =========================================================

    @staticmethod
    def _barline_type(
        barline_object
    ):

        if barline_object is None:
            return None

        return getattr(
            barline_object,
            "type",
            None,
        )

    @staticmethod
    def _repeat_direction(
        left_barline,
        right_barline,
    ):

        if isinstance(
            left_barline,
            bar.Repeat,
        ):

            direction = getattr(
                left_barline,
                "direction",
                None,
            )

            if direction:
                return direction

        if isinstance(
            right_barline,
            bar.Repeat,
        ):

            direction = getattr(
                right_barline,
                "direction",
                None,
            )

            if direction:
                return direction

        return None

    # =========================================================
    # Measure
    # =========================================================

    def _parse_measure(
        self,
        measure,
        part_index,
    ):

        events = []

        # -----------------------------------------------------
        # 원본 MusicXML 자체가 빈 마디인지 확인
        # -----------------------------------------------------

        source_empty = (
            self._is_source_measure_empty(
                part_index,
                measure.number,
            )
        )

        for element in measure.recurse():

            # -------------------------------------------------
            # Note
            # -------------------------------------------------

            if isinstance(
                element,
                note.Note,
            ):

                events.append(
                    self._parse_note(
                        element,
                        measure,
                    )
                )

            # -------------------------------------------------
            # Rest
            # -------------------------------------------------

            elif isinstance(
                element,
                note.Rest,
            ):

                # =============================================
                # 핵심 수정
                #
                # 원본 MusicXML에서 완전히 빈 마디인데
                # music21이 whole rest를 자동 생성한 경우
                # JSON에는 포함시키지 않는다.
                # =============================================

                if source_empty:
                    continue

                events.append(
                    self._parse_rest(
                        element,
                        measure,
                    )
                )

            # -------------------------------------------------
            # Chord
            # -------------------------------------------------

            elif isinstance(
                element,
                chord.Chord,
            ):

                events.append(
                    self._parse_chord(
                        element,
                        measure,
                    )
                )

        # -----------------------------------------------------
        # offset 기준 정렬
        # -----------------------------------------------------

        events.sort(
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
            )
        )

        # -----------------------------------------------------
        # Time Signature
        # -----------------------------------------------------

        time_signature = None

        try:

            ts = (
                measure.getTimeSignatures()
            )

            if ts:
                time_signature = (
                    ts[0].ratioString
                )

        except Exception:

            pass

        # -----------------------------------------------------
        # Key Signature
        # -----------------------------------------------------

        key_signature = None

        try:

            keys = (
                measure.recurse()
                .getElementsByClass(
                    key.KeySignature
                )
            )

            if keys:

                key_signature = (
                    keys[0].sharps
                )

        except Exception:

            pass

        # -----------------------------------------------------
        # Barline
        # -----------------------------------------------------

        left_barline = (
            measure.leftBarline
        )

        right_barline = (
            measure.rightBarline
        )

        repeat = (
            self._repeat_direction(
                left_barline,
                right_barline,
            )
        )

        return {
            "number":
                measure.number,

            "timeSignature":
                time_signature,

            "keySignature":
                key_signature,

            "barline": {
                "left":
                    self._barline_type(
                        left_barline
                    ),

                "right":
                    self._barline_type(
                        right_barline
                    ),

                "repeat":
                    repeat,
            },

            # 원본 MusicXML 자체가 빈 마디였는지
            # 후속 검수에서도 확인 가능
            "sourceEmpty":
                source_empty,

            "events":
                events,
        }

    # =========================================================
    # Metadata
    # =========================================================

    def _extract_metadata(self):

        title = None
        composer = None

        if self.score.metadata:

            title = (
                self.score
                .metadata
                .title
            )

            composer = (
                self.score
                .metadata
                .composer
            )

        if not title:

            title = (
                self.musicxml_path
                .stem
            )

        # -----------------------------------------------------
        # Key Signature
        # -----------------------------------------------------

        key_signature = None

        try:

            key_signatures = (
                self.score.recurse()
                .getElementsByClass(
                    key.KeySignature
                )
            )

            if key_signatures:

                key_signature = (
                    key_signatures[0]
                    .sharps
                )

        except Exception:

            pass

        # -----------------------------------------------------
        # Time Signature
        # -----------------------------------------------------

        time_signature = None

        try:

            time_signatures = (
                self.score.recurse()
                .getElementsByClass(
                    meter.TimeSignature
                )
            )

            if time_signatures:

                time_signature = (
                    time_signatures[0]
                    .ratioString
                )

        except Exception:

            pass

        # -----------------------------------------------------
        # Tempo
        # -----------------------------------------------------

        tempo_value = None

        try:

            tempos = (
                self.score.recurse()
                .getElementsByClass(
                    tempo.MetronomeMark
                )
            )

            for tempo_object in tempos:

                number = getattr(
                    tempo_object,
                    "number",
                    None,
                )

                if number is not None:

                    tempo_value = (
                        float(
                            number
                        )
                    )

                    break

        except Exception:

            pass

        return {
            "title":
                title,

            "composer":
                composer,

            "keySignature":
                key_signature,

            "timeSignature":
                time_signature,

            "tempo":
                tempo_value,
        }

    # =========================================================
    # Parse
    # =========================================================

    def parse(self):

        parts_result = []

        parts = list(
            self.score.parts
        )

        # Part 없는 단일 stream 대응
        if not parts:
            parts = [
                self.score
            ]

        for part_index, part in enumerate(
            parts
        ):

            part_name = (
                getattr(
                    part,
                    "partName",
                    None,
                )
                or getattr(
                    part,
                    "id",
                    None,
                )
                or f"Part {part_index + 1}"
            )

            part_id = (
                getattr(
                    part,
                    "id",
                    None,
                )
                or part_name
            )

            measures_result = []

            measures = (
                part.getElementsByClass(
                    stream.Measure
                )
            )

            for measure in measures:

                measures_result.append(
                    self._parse_measure(
                        measure,
                        part_index,
                    )
                )

            parts_result.append({
                "id":
                    str(
                        part_id
                    ),

                "name":
                    str(
                        part_name
                    ),

                "measures":
                    measures_result,
            })

        return {
            "source": {
                "fileName":
                    self.musicxml_path.name,

                "format":
                    "MusicXML",
            },

            "metadata":
                self._extract_metadata(),

            "parts":
                parts_result,
        }

    # =========================================================
    # Save JSON
    # =========================================================

    def save_json(
        self,
        output_path,
    ):

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = self.parse()

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


# =============================================================
# 직접 실행
# =============================================================

if __name__ == "__main__":

    BASE_DIR = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    # ---------------------------------------------------------
    # pipeline 호출
    #
    # python services/musicxml_parser.py input.mxl output.json
    # ---------------------------------------------------------

    if len(sys.argv) == 3:

        input_file = Path(
            sys.argv[1]
        ).resolve()

        output_file = Path(
            sys.argv[2]
        ).resolve()

    # ---------------------------------------------------------
    # 단독 테스트
    # ---------------------------------------------------------

    elif len(sys.argv) == 1:

        input_file = (
            BASE_DIR
            / "audiveris_output"
            / "M01_original.mxl"
        )

        output_file = (
            BASE_DIR
            / "parsed_output"
            / "M01_original.json"
        )

    else:

        print(
            "사용법:"
        )

        print(
            "python services/musicxml_parser.py "
            "<input.mxl> <output.json>"
        )

        sys.exit(1)

    if not input_file.exists():

        raise FileNotFoundError(
            f"MusicXML 파일 없음: "
            f"{input_file}"
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "=" * 60
    )

    print(
        "MusicXML Parser"
    )

    print(
        "=" * 60
    )

    print(
        "입력:",
        input_file,
    )

    parser = MusicXMLParser(
        input_file
    )

    result = parser.save_json(
        output_file
    )

    print(
        "출력:",
        output_file,
    )

    print()

    print(
        "Metadata:"
    )

    print(
        json.dumps(
            result[
                "metadata"
            ],
            ensure_ascii=False,
            indent=2,
        )
    )

    print()

    print(
        "Part 개수:",
        len(
            result[
                "parts"
            ]
        ),
    )

    measure_count = sum(
        len(
            part[
                "measures"
            ]
        )
        for part
        in result[
            "parts"
        ]
    )

    print(
        "Measure 개수:",
        measure_count,
    )

    event_count = sum(
        len(
            measure[
                "events"
            ]
        )
        for part
        in result[
            "parts"
        ]
        for measure
        in part[
            "measures"
        ]
    )

    print(
        "Event 개수:",
        event_count,
    )

    empty_measures = [
        {
            "part":
                part[
                    "name"
                ],

            "measure":
                measure[
                    "number"
                ],
        }
        for part
        in result[
            "parts"
        ]
        for measure
        in part[
            "measures"
        ]
        if measure.get(
            "sourceEmpty"
        )
    ]

    print(
        "원본 MusicXML 빈 마디:",
        empty_measures,
    )

    print()

    print(
        "✅ MusicXML → JSON 변환 완료"
    )