from pathlib import Path
import json


# ============================================================
# 음 이름 변환
# ============================================================

NOTE_NAMES = {
    "C": "도",
    "D": "레",
    "E": "미",
    "F": "파",
    "G": "솔",
    "A": "라",
    "B": "시",
}


ACCIDENTAL_NAMES = {
    -2: "더블 플랫",
    -1: "플랫",
    0: "",
    1: "샤프",
    2: "더블 샤프",
}


DURATION_NAMES = {
    "whole": "온음표",
    "half": "2분음표",
    "quarter": "4분음표",
    "eighth": "8분음표",
    "16th": "16분음표",
    "32nd": "32분음표",
    "64th": "64분음표",
}


REST_NAMES = {
    "whole": "온쉼표",
    "half": "2분쉼표",
    "quarter": "4분쉼표",
    "eighth": "8분쉼표",
    "16th": "16분쉼표",
    "32nd": "32분쉼표",
    "64th": "64분쉼표",
}


class MusicDescriber:

    def __init__(self, json_path):
        self.json_path = Path(json_path)

        if not self.json_path.exists():
            raise FileNotFoundError(
                f"JSON 파일을 찾을 수 없습니다: {self.json_path}"
            )

        with open(
            self.json_path,
            "r",
            encoding="utf-8",
        ) as file:
            self.data = json.load(file)

    # ========================================================
    # 박자 읽기
    # ========================================================

    def _describe_time_signature(self, time_signature):

        if not time_signature:
            return None

        try:
            numerator, denominator = time_signature.split("/")

            return (
                f"{denominator}분의 {numerator}박자"
            )

        except ValueError:
            return time_signature

    # ========================================================
    # 음높이 읽기
    # ========================================================

    def _describe_pitch(self, pitch):

        if not pitch:
            return ""

        step = pitch.get("step")
        octave = pitch.get("octave")
        alter = pitch.get("alter", 0)

        note_name = NOTE_NAMES.get(
            step,
            step
        )

        accidental = ACCIDENTAL_NAMES.get(
            alter,
            ""
        )

        if accidental:
            return (
                f"{note_name} {accidental} {octave}"
            )

        return (
            f"{note_name} {octave}"
        )

    # ========================================================
    # 음표 길이 읽기
    # ========================================================

    def _describe_note_duration(self, duration):

        if not duration:
            return "길이 미상"

        duration_type = duration.get("type")

        name = DURATION_NAMES.get(
            duration_type
        )

        if name:
            return name

        quarter_length = duration.get(
            "quarterLength"
        )

        return (
            f"길이 {quarter_length}"
        )

    # ========================================================
    # 쉼표 길이 읽기
    # ========================================================

    def _describe_rest_duration(self, duration):

        if not duration:
            return "쉼표"

        duration_type = duration.get("type")

        name = REST_NAMES.get(
            duration_type
        )

        if name:
            return name

        quarter_length = duration.get(
            "quarterLength"
        )

        return (
            f"길이 {quarter_length}의 쉼표"
        )

    # ========================================================
    # Note 설명
    # ========================================================

    def _describe_note(self, event):

        pitch_text = self._describe_pitch(
            event.get("pitch")
        )

        duration_text = self._describe_note_duration(
            event.get("duration")
        )

        return (
            f"{pitch_text} {duration_text}"
        )

    # ========================================================
    # Rest 설명
    # ========================================================

    def _describe_rest(self, event):

        return self._describe_rest_duration(
            event.get("duration")
        )

    # ========================================================
    # Chord 설명
    # ========================================================

    def _describe_chord(self, event):

        pitches = event.get(
            "pitches",
            []
        )

        pitch_texts = [
            self._describe_pitch(pitch)
            for pitch in pitches
        ]

        duration_text = self._describe_note_duration(
            event.get("duration")
        )

        if pitch_texts:

            joined = ", ".join(
                pitch_texts
            )

            return (
                f"{joined} 화음 {duration_text}"
            )

        return (
            f"화음 {duration_text}"
        )

    # ========================================================
    # Event 설명
    # ========================================================

    def _describe_event(self, event):

        event_type = event.get(
            "type"
        )

        if event_type == "note":
            return self._describe_note(event)

        if event_type == "rest":
            return self._describe_rest(event)

        if event_type == "chord":
            return self._describe_chord(event)

        return None

    # ========================================================
    # 마디 설명
    # ========================================================

    def _describe_measure(self, measure):

        measure_number = measure.get(
            "number"
        )

        events = measure.get(
            "events",
            []
        )

        event_texts = []

        for event in events:

            text = self._describe_event(
                event
            )

            if text:
                event_texts.append(
                    text
                )

        if not event_texts:

            return (
                f"{measure_number}마디에는 "
                f"인식된 음악 요소가 없습니다."
            )

        joined = ", ".join(
            event_texts
        )

        return (
            f"{measure_number}마디: "
            f"{joined}."
        )

    # ========================================================
    # Part 설명
    # ========================================================

    def _describe_part(self, part):

        lines = []

        part_name = part.get(
            "name"
        )

        if part_name:
            lines.append(
                f"{part_name} 파트입니다."
            )

        measures = part.get(
            "measures",
            []
        )

        for measure in measures:

            lines.append(
                self._describe_measure(
                    measure
                )
            )

        return lines

    # ========================================================
    # 전체 악보 설명
    # ========================================================

    def describe(self):

        lines = []

        metadata = self.data.get(
            "metadata",
            {}
        )

        # ----------------------------------------------------
        # 악보 시작
        # ----------------------------------------------------

        lines.append(
            "[악보 시작]"
        )

        # ----------------------------------------------------
        # 제목
        # ----------------------------------------------------

        title = metadata.get(
            "title"
        )

        if title:
            lines.append(
                f"악보 제목은 {title}입니다."
            )

        # ----------------------------------------------------
        # 박자
        # ----------------------------------------------------

        time_signature = (
            metadata.get(
                "timeSignature"
            )
        )

        time_text = (
            self._describe_time_signature(
                time_signature
            )
        )

        if time_text:
            lines.append(
                f"박자는 {time_text}입니다."
            )

        # ----------------------------------------------------
        # Tempo
        # ----------------------------------------------------

        tempo = metadata.get(
            "tempo"
        )

        if tempo is not None:
            lines.append(
                f"빠르기는 분당 {tempo:g}입니다."
            )

        # ----------------------------------------------------
        # Part
        # ----------------------------------------------------

        parts = self.data.get(
            "parts",
            []
        )

        for part in parts:

            lines.extend(
                self._describe_part(
                    part
                )
            )

        # ----------------------------------------------------
        # 악보 끝
        # ----------------------------------------------------

        lines.append(
            "[악보 끝]"
        )

        return "\n".join(
            lines
        )

    # ========================================================
    # 텍스트 저장
    # ========================================================

    def save_text(
        self,
        output_path
    ):

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        text = self.describe()

        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as file:

            file.write(text)

        return text


# ============================================================
# 직접 실행 테스트
# ============================================================

if __name__ == "__main__":

    BASE_DIR = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    input_file = (
        BASE_DIR
        / "parsed_output"
        / "M01_original.json"
    )

    output_dir = (
        BASE_DIR
        / "spoken_output"
    )

    output_file = (
        output_dir
        / "M01_original.txt"
    )

    describer = MusicDescriber(
        input_file
    )

    text = describer.save_text(
        output_file
    )

    print("=" * 60)
    print("Music Describer")
    print("=" * 60)
    print()

    print(text)

    print()
    print("=" * 60)

    print(
        "출력:",
        output_file
    )

    print(
        "✅ JSON → spokenText 변환 완료"
    )