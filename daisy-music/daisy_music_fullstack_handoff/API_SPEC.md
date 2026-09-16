# OCR-DAISY 악보 인식 API 명세서

**버전:** 0.1.0
**목적:** 풀스택에서 악보 이미지를 업로드하고 접근성 음악 분석 결과를 받을 수 있도록 하는 API 계약

---

# 1. API 요약

| Method | Endpoint | 설명 |
|---|---|---|
| `GET` | `/api/music/health` | Audiveris / Ollama 상태 확인 |
| `POST` | `/api/music/recognize` | 악보 이미지 → MusicContent |

풀스택에서는 위 HTTP API만 사용하면 됩니다.

`music_pipeline.py`, `musicxml_parser.py` 등 내부 모듈은 외부 API가 아닙니다.

---

# 2. GET `/api/music/health`

## 목적

악보 인식 서비스의 필수 구성요소가 정상인지 확인합니다.

## 정상 응답 예시

```json
{
  "status": "healthy",
  "audiveris": {
    "available": true,
    "command": "/path/to/Audiveris"
  },
  "ollama": {
    "available": true,
    "baseUrl": "http://127.0.0.1:11434",
    "fallbackAvailable": true
  }
}
```

## status 의미

### `healthy`

```text
Audiveris 사용 가능
+
Ollama 연결 가능
```

### `degraded`

```text
Audiveris 사용 가능
+
Ollama 연결 실패
+
Deterministic fallback 사용 가능
```

이 상태에서도 악보 분석은 성공할 수 있습니다.

### `unhealthy`

```text
Audiveris 사용 불가
```

이미지 → OMR 변환 자체가 불가능하므로 정상 분석이 어렵습니다.

---

# 3. POST `/api/music/recognize`

## 목적

악보 이미지 한 장에 대해 전체 악보 분석 파이프라인을 실행합니다.

```text
Image
↓
Audiveris
↓
MXL + OMR
↓
Music Pipeline
↓
MusicContent
```

## Request

```text
Content-Type: multipart/form-data
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `image_file` | File | O | 악보 이미지 |

현재 지원 확장자:

```text
.jpg
.jpeg
.png
```

현재 기본 업로드 크기 제한:

```text
50 MiB
```

이미지 픽셀 수가 너무 큰 경우 `audiveris_runner.py`가 내부적으로 resize합니다.

---

# 4. 호출 예시

## curl

```bash
curl -X POST \
  http://127.0.0.1:8000/api/music/recognize \
  -F "image_file=@M01.png"
```

## JavaScript

```javascript
const formData = new FormData();
formData.append("image_file", file);

const response = await fetch(
  "http://127.0.0.1:8000/api/music/recognize",
  {
    method: "POST",
    body: formData,
  }
);

const result = await response.json();
```

브라우저 `FormData`를 사용할 때 `Content-Type`을 직접 설정하지 않는 것이 좋습니다. 브라우저가 multipart boundary를 자동으로 추가해야 합니다.

---

# 5. 성공 응답 구조

```json
{
  "success": true,
  "requestId": "a1b2c3...",
  "upload": {
    "filename": "score.png",
    "sizeBytes": 123456
  },
  "musicContent": {},
  "outputPath": "/internal/path/music_content.json",
  "runDir": "/internal/path/run-directory"
}
```

`outputPath`, `runDir`은 현재 개발/디버깅용입니다.
운영 프론트에서 장기적으로 사용할 공개 필드로 보지 않는 것을 권장합니다.

---

# 6. MusicContent 전체 구조

```json
{
  "type": "music",
  "status": "DONE",

  "musicXml": "<score-partwise ...>",
  "metadata": {},

  "spokenText": "...",
  "summary": {},
  "measures": [],

  "features": {},
  "confidence": {},
  "review": {},
  "mapping": {},

  "brailleMusic": null,

  "outputs": {
    "daisy": null,
    "hwp": null
  },

  "playback": null,

  "artifacts": {},
  "recognition": {}
}
```

---

# 7. 필드별 의미

## `type`

현재 값:

```text
music
```

향후 전체 IR에서 콘텐츠 종류를 구분하기 위한 값입니다.

---

## `status`

정상 완료 시:

```text
DONE
```

`DONE`은 **파이프라인이 끝까지 실행되었다는 뜻**이지, 악보 인식 정확도가 100%라는 뜻이 아닙니다.

인식 품질은 별도로:

```text
review
confidence
```

를 확인해야 합니다.

---

## `musicXml`

Audiveris가 생성한 `.mxl` 안의 실제 MusicXML 문자열입니다.

용도:

```text
구조 근거 보존
점자악보 후속 변환
playback/MIDI 후속 변환
IR 저장
디버깅
```

운영에서는 응답 크기가 커질 수 있으므로 나중에는 `artifactId` 방식으로 분리할 수 있습니다.

---

## `spokenText`

스크린리더에서 읽기 위한 **상세 사실 기반 설명**입니다.

주로 규칙/템플릿으로 생성됩니다.

추천 UI:

```text
[상세 설명 보기]
```

---

## `summary`

짧은 음악 구조 요약입니다.

대표 하위 필드:

```text
text
claims
source/model
selection
validation
debug
factCatalog
```

일반 프론트에서는 보통:

```text
summary.text
```

만 먼저 사용하면 됩니다.

검수/개발 UI는:

```text
summary.validation
summary.claims
```

을 추가로 사용할 수 있습니다.

---

# 8. Summary Validation

예시:

```json
{
  "validation": {
    "passed": true,
    "retried": false,
    "fallbackUsed": false
  }
}
```

## `passed=true`

뜻:

> 요약에 사용된 문장이 파이프라인이 만든 Fact Catalog에 근거하고 있다.

뜻하지 않는 것:

> Audiveris가 모든 음표를 정확하게 인식했다.

이 둘은 반드시 구분해야 합니다.

## `fallbackUsed=false`

Ollama/Local LLM이 Optional Fact ID 선택을 정상 수행했습니다.

## `fallbackUsed=true`

LLM 연결 실패 또는 잘못된 선택으로 deterministic fallback을 사용했습니다.

이 경우에도:

```text
status = DONE
validation.passed = true
```

가 될 수 있습니다.

---

# 9. `confidence`

예시:

```json
{
  "average": 0.806,
  "minimum": 0.78,
  "measureCount": 30
}
```

중요:

```text
confidence ≠ Ground Truth Accuracy
```

따라서 UI에서:

```text
정확도 80.6%
```

라고 표시하지 않는 것이 좋습니다.

대신:

```text
인식 신뢰도 평균: 0.806
```

처럼 표시합니다.

---

# 10. `review`

예시:

```json
{
  "needsReview": true,
  "level": "HIGH",
  "reasons": [
    "EMPTY_MEASURE_IN_MUSICXML"
  ],
  "threshold": 0.67
}
```

## Level

```text
LOW
MEDIUM
HIGH
```

### LOW

일반 표시.

### MEDIUM

가벼운 검수 필요 메시지 표시 권장.

### HIGH

사용자/검수자에게 명확히 알리는 것을 권장합니다.

추천 문장:

> 악보 인식 결과에는 확인이 필요한 부분이 있습니다.

---

# 11. `features`

구조화된 음악 특징입니다.

예:

```text
pitchRange
melodicContour
rhythm-related statistics
part-level features
```

향후 음악 구조 시각화, 검색, 요약 등에 재사용 가능합니다.

---

# 12. `mapping`

OMR / MusicXML / JSON 사이의 내부 일관성을 확인하기 위한 개발/검수용 정보입니다.

예:

```text
omrHeadCount
musicXmlPitchNoteCount
jsonNoteheadEquivalentCount
noteCountMatch
omrRestCount
musicXmlRestCount
jsonRestCount
restCountMatch
```

일반 사용자 UI에는 그대로 노출할 필요가 없습니다.

---

# 13. 향후 예약 필드

## `brailleMusic`

현재:

```json
null
```

향후:

```text
MusicXML / MusicStructure
↓
점자악보 변환
↓
brailleMusic
```

## `outputs.daisy`

현재:

```json
null
```

DAISY는 악보 하나만 따로 변환하기보다 전체 문서의 읽기 순서에 악보 설명을 넣는 방식으로 연결할 예정입니다.

## `outputs.hwp`

현재:

```json
null
```

향후 HWP serializer 결과 또는 artifact reference를 넣을 수 있습니다.

## `playback`

현재:

```json
null
```

MusicContent IR 확정 이후 MIDI/playback 기능을 연결할 예정입니다.

---

# 14. `artifacts`

개발/내부 파일 경로 정보입니다.

예:

```json
{
  "sourceImage": "/.../input.png",
  "musicXmlPath": "/.../input.mxl",
  "omrProjectPath": "/.../input.omr",
  "pipelineOutputPath": "/.../pipeline_output/input.json"
}
```

주의:

서버 로컬 경로는 공개 URL이 아닙니다.
운영에서는 아래 중 하나로 바꾸는 것을 권장합니다.

```text
1. 일반 응답에서 제거
2. 관리자 모드에서만 노출
3. artifactId로 대체
4. 별도 download endpoint 제공
```

---

# 15. `recognition`

Audiveris 실행과 이미지 전처리의 디버깅 정보입니다.

예:

```json
{
  "preprocess": {
    "resized": true,
    "originalWidth": 11256,
    "originalHeight": 15372,
    "originalPixels": 173027232,
    "preparedWidth": 2928,
    "preparedHeight": 4000,
    "preparedPixels": 11712000
  }
}
```

운영 일반 사용자보다는 개발/검수에서 유용합니다.

---

# 16. 오류 응답

공통 형태:

```json
{
  "success": false,
  "requestId": "...",
  "error": {
    "code": "...",
    "message": "..."
  }
}
```

## `400 INVALID_FILE_TYPE`

지원하지 않는 파일 형식.

## `413 FILE_TOO_LARGE`

업로드 바이트 크기 제한 초과.

## `422 MUSIC_RECOGNITION_FAILED`

Audiveris 또는 Music Pipeline이 악보를 정상적으로 처리하지 못함.

## `504 MUSIC_RECOGNITION_TIMEOUT`

Audiveris 처리 시간이 설정된 timeout을 초과함.

## `500 UPLOAD_SAVE_FAILED`

업로드 파일 저장 실패.

## `500 INTERNAL_SERVER_ERROR`

예상하지 못한 서버 내부 오류.

---

# 17. 프론트 권장 처리

성공하면 우선 아래만 사용해도 1차 UI가 가능합니다.

```text
musicContent.summary.text
musicContent.spokenText
musicContent.review.needsReview
musicContent.review.level
musicContent.review.reasons
```

추천 화면 예시:

```text
악보 분석 결과

[검수 필요 여부]
Review: HIGH
악보 인식 결과에는 확인이 필요한 부분이 있습니다.

[요약]
summary.text

[상세 설명]
spokenText
```

개발/검수 화면에서만:

```text
confidence
mapping
summary.validation
summary.claims
features
```

을 추가로 표시하면 됩니다.
