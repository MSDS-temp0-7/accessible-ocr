from pathlib import Path
from musicxml_parser import MusicXMLParser


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "audiveris_output"
OUTPUT_DIR = BASE_DIR / "parsed_output"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


mxl_files = sorted(
    INPUT_DIR.glob("*.mxl")
)


print("=" * 60)
print("MusicXML Batch Parser")
print("=" * 60)

print(f"발견된 MXL: {len(mxl_files)}개")
print()


success = 0
failed = 0


for mxl_path in mxl_files:

    output_path = (
        OUTPUT_DIR /
        f"{mxl_path.stem}.json"
    )

    print(
        f"[처리] {mxl_path.name}"
    )

    try:

        parser = MusicXMLParser(
            mxl_path
        )

        parser.save_json(
            output_path
        )

        print(
            f"  → 완료: {output_path.name}"
        )

        success += 1

    except Exception as e:

        print(
            f"  → 실패: {e}"
        )

        failed += 1


print()
print("=" * 60)
print("Batch Parsing 완료")
print("=" * 60)

print(
    f"성공: {success}"
)

print(
    f"실패: {failed}"
)

print(
    f"출력 폴더: {OUTPUT_DIR}"
)