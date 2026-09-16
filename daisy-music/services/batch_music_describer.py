from pathlib import Path

from music_describer import MusicDescriber


# ============================================================
# 경로 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "parsed_output"
OUTPUT_DIR = BASE_DIR / "spoken_output"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# JSON 파일 검색
# ============================================================

json_files = sorted(
    INPUT_DIR.glob("*.json")
)


print("=" * 60)
print("Music SpokenText Batch Generator")
print("=" * 60)

print(f"발견된 JSON: {len(json_files)}개")
print()


# ============================================================
# 통계
# ============================================================

success = 0
failed = 0

failed_files = []


# ============================================================
# 일괄 변환
# ============================================================

for json_path in json_files:

    output_path = (
        OUTPUT_DIR
        / f"{json_path.stem}.txt"
    )

    print(
        f"[처리] {json_path.name}"
    )

    try:

        describer = MusicDescriber(
            json_path
        )

        describer.save_text(
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

        failed_files.append({
            "file": json_path.name,
            "error": str(e),
        })


# ============================================================
# 결과 출력
# ============================================================

print()
print("=" * 60)
print("SpokenText Batch 생성 완료")
print("=" * 60)

print(
    f"전체 JSON : {len(json_files)}"
)

print(
    f"성공      : {success}"
)

print(
    f"실패      : {failed}"
)

print(
    f"출력 폴더 : {OUTPUT_DIR}"
)


# ============================================================
# 실패 파일 출력
# ============================================================

if failed_files:

    print()
    print("=" * 60)
    print("실패 파일")
    print("=" * 60)

    for item in failed_files:

        print(
            f"{item['file']} "
            f"→ {item['error']}"
        )