from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent.parent

OMR_FILE = (
    BASE_DIR
    / "audiveris_output"
    / "M01_original.omr"
)


TARGET_TAGS = {
    "head",
    "stem",
    "head-chord",
    "rest",
    "rest-chord",
    "time-pair",
    "clef",
}


def clean_tag(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def inspect_links(omr_path):

    with zipfile.ZipFile(
        omr_path,
        "r"
    ) as archive:

        xml_bytes = archive.read(
            "sheet#1/sheet#1.xml"
        )

    root = ET.fromstring(
        xml_bytes
    )

    counters = {
        tag: 0
        for tag in TARGET_TAGS
    }

    print("=" * 80)
    print("Audiveris Inter 구조 확인")
    print("=" * 80)

    for element in root.iter():

        tag = clean_tag(
            element.tag
        )

        if tag not in TARGET_TAGS:
            continue

        if counters[tag] >= 10:
            continue

        counters[tag] += 1

        print()
        print(
            f"[{tag} #{counters[tag]}]"
        )

        print(
            "attributes:",
            element.attrib
        )

        # 자식 태그도 확인
        for child in element:

            print(
                "  child:",
                clean_tag(child.tag),
                child.attrib
            )


if __name__ == "__main__":

    inspect_links(
        OMR_FILE
    )