# OCR 파이프라인 연동 계약

최종 갱신: 2026-09-02

## 현재 실행 구조

WPF 앱은 Python 모델을 프로세스 안에 직접 로드하지 않는다. 사용자가 고른
PDF를 같은 PC에서 실행 중인 `daisy_ocr.server`에 업로드하고 비동기 Job을
조회한다. 로컬 서버가 모델 코드를 실행하고 WPF 계약에 맞는 ZIP을 만든다.

```text
PDF 선택
  -> POST /api/v1/jobs (multipart: file, options)
  <- { job_id, document_id, status: queued, progress, message }
  -> GET /api/v1/jobs/{job_id}
  <- { status: queued | processing | done | failed, progress, message, error? }
  -> GET /api/v1/jobs/{job_id}/result
  <- application/zip
  -> ZIP: book.xml + review.json
```

검수 수정 요청:

```text
PATCH /api/v1/documents/{document_id}/elements/{element_id}/review
{
  "corrected_content": "...",
  "review_status": "reviewed | needsreview | pending",
  "revision": null
}
```

현재 PATCH는 데모를 위해 서버 메모리에만 저장한다.

## 서버 내부 처리

1. PDF를 시스템 임시 폴더에 저장한다.
2. 선택 페이지를 200 DPI 이미지로 렌더링한다.
3. CLOVA General OCR로 페이지 전체 글자·좌표·신뢰도를 읽는다.
4. DocLayout-YOLO DocLayNet 모델로 표·수식·그림 영역을 찾는다.
5. 중복 레이아웃 박스를 정리하고 가져오기 옵션에 따라 유형을 선택한다.
6. OCR 조각과 비텍스트 영역을 중복 없이 읽기 순서로 합친다.
7. DTBook과 검수 사이드카를 ZIP으로 만든다.

CLOVA 호출은 페이지당 한 번이다. 자동 재시도나 숨은 사전 호출은 없다.
레이아웃 모델 가중치는 Hugging Face 캐시에 한 번 다운로드된 뒤 재사용된다.

## 결과 패키지

| 파일 | 현재 책임 | WPF 사용처 |
| --- | --- | --- |
| `book.xml` | 요소 ID와 읽기 순서, OCR/특수 영역 텍스트 | 검수 편집 내용 |
| `review.json` | 페이지 크기, DPI, 페이지 이미지 참조, 유형, 픽셀 좌표, 신뢰도, 검수 상태 | 목록·상태·좌표·오버레이 표시 |
| `pages/page-XXXX.jpg` | 실제 OCR 입력에 사용한 페이지 미리보기 | 중앙 원본 페이지 검수 화면 |

- DTBook `id`와 `review.json.elements`의 키는 같다.
- `page_index`는 0부터 시작한다.
- `bbox`는 `[x, y, width, height]` 픽셀이다.
- `confidence`는 `0.0~1.0`이다.
- `review_status`는 `pending`, `reviewed`, `needs_review` 중 하나다.
- 일반 OCR이 0.8 미만이면 `needs_review`다.
- 전용 변환이 아직 없는 특수 영역은 신뢰도와 무관하게 `needs_review`다.

## WPF 요청 옵션

`options` multipart 필드는 JSON 문자열이며 현재 속성 이름은 .NET 모델과
동일한 PascalCase다.

```json
{
  "PageRange": "전체 페이지",
  "Language": "한국어",
  "DetectBody": true,
  "DetectTables": true,
  "DetectCharts": true,
  "DetectMath": true,
  "DetectMusic": true,
  "DetectImages": true,
  "ProcessingPolicy": "조직 정책에 따라 처리"
}
```

WPF 화면은 `전체 페이지` 또는 시작·끝 숫자로 만든 `1-3` 형식을 전송한다.
서버 계약은 기존 호환을 위해 `1`, `1-3`, `1-3,5`도 해석한다. 숫자가 없거나
역순이거나 실제 PDF 페이지 수를 벗어나면 전체 페이지로 대체하지 않고 Job을
실패 처리한다.

## 비밀 설정

- 공유 표본: `config/integration-api.env.example`
- 실제 로컬 값: `config/integration-api.env` (`.gitignore` 적용)
- 필요한 실제 값: `CLOVA_OCR_INVOKE_URL`, `CLOVA_OCR_SECRET`
- WPF의 `OcrApi.BaseUrl`은 CLOVA 주소가 아니라 로컬 API 주소다.
- 기본 로컬 주소: `http://localhost:8000`

## 모델팀 결과 연결 지점

모델팀은 표·수식·그래프·악보 영역별 결과를 다음 의미로 전달하면 된다.

```text
TranscribedRegion:
  type        table | formula | graph | music | unknown
  label       레이아웃 모델 원본 라벨
  bbox        [x1, y1, x2, y2]
  confidence  검출 신뢰도
  text        접근 가능한 전사·설명 결과
  error       부분 실패 메시지 또는 null
```

`review.json`의 각 `pages[]` 항목에는 이미지가 포함된 경우
`"image_ref": "pages/page-0001.jpg"`가 추가된다. 좌표는 이 이미지의
`width`, `height` 픽셀 좌표계와 같으므로 화면에서는 동일 비율로 축소한 뒤
박스를 겹쳐 그린다. `image_ref`는 하위 호환을 위해 선택값이다.

`daisy_ocr.pipeline.merge_page()`는 전사 엔진에 의존하지 않으므로 모델팀
결과를 이 구조로 바꾸는 어댑터만 추가하면 된다. 현재 서버의 안내 문구 생성은
그 어댑터가 들어갈 임시 폴백이며 임의 수식이나 표 데이터를 만들지 않는다.

## 운영 전 결정할 항목

1. 로컬 API를 EXE 설치에 포함하고 자동 기동할지, 중앙 서버로 옮길지
2. 사용자 인증·권한과 Job 소유권
3. DB 및 원본/결과 파일 보존 기간
4. 모델팀 전용 결과의 오류·버전·revision 규격
5. 원본 페이지 이미지와 영역 크롭 전달 방식
6. CLOVA 과금 제한, 타임아웃, 취소와 재시도 정책
