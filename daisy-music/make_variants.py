from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "variants"

OUTPUT_DIR.mkdir(exist_ok=True)

# Audiveris 입력용 기준
MAX_SIDE = 4000

SMALL_SCALE = 0.6
TILT_ANGLE = 5
LOWQ_SCALE = 0.5


def resize_for_audiveris(img):
    """
    원본 비율을 유지하면서
    긴 변을 최대 4000px로 제한
    """

    width, height = img.size

    longest = max(width, height)

    if longest <= MAX_SIDE:
        return img.copy()

    scale = MAX_SIDE / longest

    new_width = int(width * scale)
    new_height = int(height * scale)

    return img.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )


def make_small(img):
    """
    동일한 페이지 크기에서
    악보 자체만 60%로 줄임
    """

    width, height = img.size

    new_width = int(width * SMALL_SCALE)
    new_height = int(height * SMALL_SCALE)

    small = img.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )

    canvas = Image.new(
        "RGB",
        (width, height),
        "white"
    )

    x = (width - new_width) // 2
    y = (height - new_height) // 2

    canvas.paste(small, (x, y))

    return canvas


def make_tilt(img):

    return img.rotate(
        TILT_ANGLE,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor="white"
    )


def make_low_quality(img):

    width, height = img.size

    low_width = int(width * LOWQ_SCALE)
    low_height = int(height * LOWQ_SCALE)

    # 품질 저하
    low = img.resize(
        (low_width, low_height),
        Image.Resampling.BILINEAR
    )

    # 다시 원래 크기로 확대
    low = low.resize(
        (width, height),
        Image.Resampling.BILINEAR
    )

    return low


for i in range(1, 6):

    name = f"M{i:02d}"

    source_path = BASE_DIR / f"{name}.png"

    if not source_path.exists():
        print(f"[없음] {source_path}")
        continue

    original = Image.open(source_path).convert("RGB")

    print(
        f"{name} 원본 크기:",
        original.size
    )

    # --------------------------------
    # Audiveris용 표준 원본 생성
    # --------------------------------

    base = resize_for_audiveris(original)

    print(
        f"{name} 변환 크기:",
        base.size
    )

    # original
    base.save(
        OUTPUT_DIR / f"{name}_original.png"
    )

    # small
    small = make_small(base)

    small.save(
        OUTPUT_DIR / f"{name}_small.png"
    )

    # tilt
    tilt = make_tilt(base)

    tilt.save(
        OUTPUT_DIR / f"{name}_tilt.png"
    )

    # low quality
    lowq = make_low_quality(base)

    lowq.save(
        OUTPUT_DIR / f"{name}_lowq.png"
    )

    print(f"[완료] {name}")


print("\n20개 평가 이미지 생성 완료")