from pathlib import Path
from collections import Counter
import zipfile
import xml.etree.ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent.parent

OMR_FILE = (
    BASE_DIR
    / "audiveris_output"
    / "M01_original.omr"
)


def clean_tag(tag):
    """
    XML namespace 제거
    """
    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def inspect_omr(omr_path):

    print("=" * 70)
    print("Audiveris OMR Confidence Inspector")
    print("=" * 70)

    print("파일:", omr_path)
    print()

    if not omr_path.exists():

        print("❌ OMR 파일을 찾을 수 없습니다.")
        return

    # ---------------------------------------------------------
    # .omr 파일은 ZIP 구조
    # ---------------------------------------------------------

    with zipfile.ZipFile(
        omr_path,
        "r"
    ) as archive:

        files = archive.namelist()

        print("[OMR 내부 파일]")

        for file_name in files:
            print(" -", file_name)

        print()

        # -----------------------------------------------------
        # sheet XML 찾기
        # -----------------------------------------------------

        sheet_xml_files = [
            name
            for name in files
            if (
                name.startswith("sheet#")
                and name.endswith(".xml")
            )
        ]

        if not sheet_xml_files:

            print("❌ sheet XML을 찾지 못했습니다.")
            return

        print(
            "발견된 sheet XML:",
            sheet_xml_files
        )

        print()

        total_grade_count = 0

        tag_counter = Counter()

        # -----------------------------------------------------
        # sheet XML 검사
        # -----------------------------------------------------

        for sheet_file in sheet_xml_files:

            print("=" * 70)
            print("분석:", sheet_file)
            print("=" * 70)

            xml_bytes = archive.read(
                sheet_file
            )

            root = ET.fromstring(
                xml_bytes
            )

            grade_items = []

            for element in root.iter():

                # attribute 이름 중
                # grade가 들어가는 값 모두 탐색
                grade_attributes = {}

                for key, value in element.attrib.items():

                    if "grade" in key.lower():

                        grade_attributes[key] = value

                if grade_attributes:

                    tag_name = clean_tag(
                        element.tag
                    )

                    grade_items.append({
                        "tag": tag_name,
                        "attributes":
                            grade_attributes
                    })

                    tag_counter[tag_name] += 1

            print(
                f"grade 관련 요소 수: "
                f"{len(grade_items)}"
            )

            total_grade_count += len(
                grade_items
            )

            print()

            # -------------------------------------------------
            # 처음 30개 출력
            # -------------------------------------------------

            print(
                "[grade 샘플 - 최대 30개]"
            )

            for item in grade_items[:30]:

                print(
                    f"{item['tag']} "
                    f"{item['attributes']}"
                )

            print()

            # -------------------------------------------------
            # 만약 XML attribute 검색에서 안 잡히면
            # raw XML에서도 grade 검색
            # -------------------------------------------------

            if not grade_items:

                xml_text = xml_bytes.decode(
                    "utf-8",
                    errors="ignore"
                )

                lines = xml_text.splitlines()

                grade_lines = [
                    line.strip()
                    for line in lines
                    if "grade" in line.lower()
                ]

                print(
                    "[Raw XML grade 검색]"
                )

                for line in grade_lines[:30]:

                    print(line)

                print()

    # ---------------------------------------------------------
    # 결과 요약
    # ---------------------------------------------------------

    print("=" * 70)
    print("요약")
    print("=" * 70)

    print(
        "전체 grade 관련 요소:",
        total_grade_count
    )

    print()

    print(
        "태그별 개수:"
    )

    for tag, count in (
        tag_counter.most_common()
    ):

        print(
            f"{tag}: {count}"
        )


if __name__ == "__main__":

    inspect_omr(
        OMR_FILE
    )