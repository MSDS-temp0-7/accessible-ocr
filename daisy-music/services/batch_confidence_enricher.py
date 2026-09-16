from pathlib import Path

from confidence_enricher import enrich_confidence


BASE_DIR = Path(__file__).resolve().parent.parent

JSON_DIR = BASE_DIR / "parsed_output"
OMR_DIR = BASE_DIR / "audiveris_output"
OUTPUT_DIR = BASE_DIR / "confidence_output"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


json_files = sorted(
    JSON_DIR.glob("*.json")
)


print("=" * 70)
print("Confidence Batch Enricher")
print("=" * 70)

print(f"JSON 파일: {len(json_files)}개")
print()


success = 0
failed = 0


for json_path in json_files:

    name = json_path.stem

    omr_path = (
        OMR_DIR
        / f"{name}.omr"
    )

    output_path = (
        OUTPUT_DIR
        / f"{name}.json"
    )

    print(f"[처리] {name}")

    if not omr_path.exists():

        print("  → OMR 파일 없음")

        failed += 1
        continue

    try:

        result = enrich_confidence(
            json_path,
            omr_path,
            output_path,
        )

        confidence = result.get(
            "confidence"
        )

        print(
            f"  → 완료 "
            f"confidence={confidence}"
        )

        success += 1

    except Exception as e:

        print(
            f"  → 실패: {e}"
        )

        failed += 1


print()
print("=" * 70)
print("Confidence Batch 완료")
print("=" * 70)

print(f"전체 : {len(json_files)}")
print(f"성공 : {success}")
print(f"실패 : {failed}")
print(f"출력 : {OUTPUT_DIR}")