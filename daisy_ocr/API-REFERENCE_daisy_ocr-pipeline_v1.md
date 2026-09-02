# `daisy_ocr.pipeline` API 레퍼런스

내부 로직을 몰라도 이 문서만으로 통합할 수 있도록 함수·모듈 호출법만
정리했다. "왜 이렇게 만들었는지", "내부에서 어떻게 계산하는지"가 궁금하면
[`docs/PIPELINE_Page-Text-Extraction_v1.md`](PIPELINE_Page-Text-Extraction_v1.md)를 보면 된다 — 이 문서는 그 반대로,
설명 없이 시그니처와 예제만 빠르게 찾기 위한 것이다.

```python
from daisy_ocr.pipeline import prepare_page, merge_page, TranscribedRegion
```

---

## 설치·준비

```bash
poetry install   # 또는 .venv/Scripts/python.exe -m pip install -e .
```

`.env` 파일에 아래 값이 있어야 한다:

```env
CLOVA_OCR_SECRET=...       # 항상 필요
CLOVA_OCR_INVOKE_URL=...   # 항상 필요, https://xxxx.apigw.ntruss.com/... 형태
OPENAI_API_KEY=...         # transcribe_regions() / process_page() 쓸 때만 필요
```

호출 전 애플리케이션 시작 시 한 번:

```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 함수 목록

| 함수 | 비동기 | 언제 쓰나 |
|---|---|---|
| [`prepare_page()`](#prepare_page) | ✅ `async` | 페이지 분할 + 본문 텍스트화. 거의 항상 첫 호출. |
| [`merge_page()`](#merge_page) | ❌ 일반 함수 | 결과 병합. `prepare_page()` 다음에 호출. |
| [`transcribe_regions()`](#transcribe_regions-참고-구현) | ✅ `async` | 표/그래프/수식을 OpenAI로 설명(참고 구현). 다른 모델로 대체 가능. |
| [`process_page()`](#process_page-올인원-편의-함수) | ✅ `async` | 위 셋을 한 번에. 빠른 테스트·데모용. |

---

## `prepare_page()`

```python
async def prepare_page(
    image: PIL.Image.Image,
    *,
    layout_model: str = "doclaynet",
    conf: float | None = None,
    imgsz: int | None = None,
) -> PreparedPage
```

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `image` | `PIL.Image.Image` | 필수 | `.convert("RGB")` 적용된 이미지 |
| `layout_model` | `str` | `"doclaynet"` | `daisy_ocr.layout.detect.MODELS` 키 중 하나 |
| `conf` | `float \| None` | `None` | `None`이면 모델별 등록 기본값(현재 `0.3`) |
| `imgsz` | `int \| None` | `None` | `None`이면 모델별 등록 기본값(`960`) |

**반환: `PreparedPage`**

```python
@dataclass
class PreparedPage:
    ocr_blocks: list[TextBlock]
    regions: list[LayoutRegion]
    non_text_regions: list[LayoutRegion]
    layout_model: str
    conf: float
    imgsz: int
    ocr_elapsed_ms: float
    detect_elapsed_ms: float
```

**예외**: `RuntimeError` — 로컬 설정에 실제 `CLOVA_OCR_SECRET`/`CLOVA_OCR_INVOKE_URL` 없음.

```python
prepared = await prepare_page(image)
prepared.non_text_regions  # 다음 단계(transcribe)에 넘길 것
prepared.ocr_blocks        # merge_page()에 그대로 넘길 것
```

---

## `merge_page()`

```python
def merge_page(
    ocr_blocks: list[TextBlock],
    non_text_regions: list[LayoutRegion],
    transcribed: list[TranscribedRegion],
) -> list[PageElement]
```

`await` 불필요. `transcribed=[]`면 표/그래프/수식 설명 없이 OCR 결과만
순서대로 반환.

| 파라미터 | 값 |
|---|---|
| `ocr_blocks` | `prepared.ocr_blocks` 그대로 |
| `non_text_regions` | `prepared.non_text_regions` 그대로 |
| `transcribed` | `TranscribedRegion` 리스트 — 아래 참고 |

**반환: `list[PageElement]`** — 읽기 순서로 정렬된 최종 결과.

```python
@dataclass(frozen=True)
class PageElement:
    kind: str                     # "ocr" | "ai"
    type: str                     # text | table | formula | graph | music | unknown
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float | None      # ocr만
    label: str | None             # ai만
    error: str | None             # ai 실패 시만
```

```python
elements = merge_page(prepared.ocr_blocks, prepared.non_text_regions, transcribed)
for el in elements:
    print(el.kind, el.type, el.text)
```

---

## `TranscribedRegion` — 표/그래프/수식 설명 결과의 입력 형태

`merge_page()`의 `transcribed` 인자에 넣을 항목 하나. 어떤 모델로
만들었든 이 형태만 맞추면 된다.

```python
@dataclass(frozen=True)
class TranscribedRegion:
    type: str          # "table" | "formula" | "graph" | "music" | "unknown"
    label: str          # 자유 문자열(원래 레이아웃 라벨을 넣는 게 보통)
    bbox: tuple[float, float, float, float]  # non_text_regions의 해당 항목과 동일 좌표
    confidence: float
    text: str | None    # 실패 시 None
    error: str | None = None
```

```python
transcribed = [
    TranscribedRegion(
        type="table", label=r.label, bbox=r.bbox, confidence=r.confidence,
        text=내_모델_호출(image, r.bbox), error=None,
    )
    for r in prepared.non_text_regions
]
```

---

## `transcribe_regions()` [참고 구현]

```python
async def transcribe_regions(
    image: PIL.Image.Image,
    regions: list[LayoutRegion],
    layout_model: str = "doclaynet",
    *,
    openai_model: str = "gpt-5-mini",
    max_regions: int = 40,
) -> list[TranscribedRegion]
```

OpenAI 비전 모델로 `regions`(보통 `prepared.non_text_regions`)를 크롭해
설명을 생성한다. `OPENAI_API_KEY` 필요. `max_regions`개까지만 처리(비용
보호). 영역 하나가 실패해도 예외를 던지지 않고 그 항목의 `error`에 담아
나머지는 계속 처리한다.

```python
transcribed = await transcribe_regions(image, prepared.non_text_regions)
```

---

## `process_page()` [올인원 편의 함수]

```python
async def process_page(
    image: PIL.Image.Image,
    *,
    layout_model: str = "doclaynet",
    conf: float | None = None,
    imgsz: int | None = None,
    openai_model: str = "gpt-5-mini",
    max_transcribe_regions: int = 40,
    transcribe_non_text: bool = True,
) -> PageResult
```

`prepare_page → transcribe_regions(OpenAI) → merge_page`를 이어붙인
함수. `transcribe_non_text=False`면 OpenAI를 아예 안 부른다.

**반환: `PageResult`**

```python
@dataclass
class PageResult:
    elements: list[PageElement]
    regions: list[LayoutRegion]
    ocr_blocks: list[TextBlock]
    transcribed: list[TranscribedRegion]
    ocr_elapsed_ms: float
    detect_elapsed_ms: float
    transcribe_elapsed_ms: float
    model: str
    conf: float
    imgsz: int
```

```python
result = await process_page(image)
for el in result.elements:
    print(el.text)
```

---

## 참고 dataclass — 다른 모듈에서 옴

```python
# daisy_ocr.layout.detect
@dataclass
class LayoutRegion:
    label: str
    bbox: list[float]      # [x1, y1, x2, y2]
    confidence: float

MODELS: dict[str, ModelSpec]   # 등록된 레이아웃 모델 목록
DEFAULT_MODEL = "doclaynet"
to_our_type(label: str, model: str) -> str  # 원본 라벨 → 5종 유형(text/table/formula/graph/music)

# daisy_ocr.ocr.clova_engine
@dataclass
class TextBlock:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]
```

---

## 전체 예시

```python
import asyncio
from dotenv import load_dotenv
from PIL import Image
from daisy_ocr.pipeline import prepare_page, merge_page, TranscribedRegion

load_dotenv()

async def extract(image_path: str) -> list:
    image = Image.open(image_path).convert("RGB")
    prepared = await prepare_page(image)

    transcribed = [
        TranscribedRegion(
            type="table", label=r.label, bbox=r.bbox, confidence=r.confidence,
            text="...",  # 실제로는 다른 팀 모델 호출 결과
            error=None,
        )
        for r in prepared.non_text_regions
    ]

    return merge_page(prepared.ocr_blocks, prepared.non_text_regions, transcribed)

elements = asyncio.run(extract("page.jpg"))
```

빠르게 결과만 보고 싶으면(OpenAI 참고 구현 그대로):

```python
from daisy_ocr.pipeline import process_page
result = await process_page(image)
```
