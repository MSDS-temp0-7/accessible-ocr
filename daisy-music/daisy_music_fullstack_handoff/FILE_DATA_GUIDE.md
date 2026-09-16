# OCR-DAISY 악보 파트 — Python 파일 및 데이터 파일 상세 설명

이 문서는 풀스택/백엔드 개발자가 프로젝트를 처음 받았을 때 **어떤 Python 파일이 무엇을 하고, 어떤 데이터가 어디서 만들어지며, 무엇을 수정해도 되는지** 빠르게 이해하기 위한 문서입니다.

---

# 1. 전체 호출 관계

```text
api/music_api.py
   ↓
services/music_recognizer.py
   ├─ services/audiveris_runner.py
   │      ↓
   │   Audiveris CLI
   │      ↓
   │   .mxl + .omr
   │
   └─ services/music_pipeline.py
          ├─ musicxml_parser.py
          ├─ confidence_enricher.py
          ├─ music_feature_analyzer.py
          ├─ music_describer.py
          └─ local_llm_summarizer.py
                 ↓
             Ollama

최종
↓
MusicContent JSON
```

---

# 2. Python 파일 상세

| 파일 | 한 줄 설명 | 입력 | 출력 | 풀스택이 직접 수정? |
|---|---|---|---|---|
| `api/music_api.py` | HTTP API 진입점 | 업로드 이미지 | HTTP JSON | 환경/응답 포맷은 가능 |
| `music_recognizer.py` | 전체 이미지 분석 조율 | image path | MusicContent | 새 최종 필드 연결 시 수정 |
| `audiveris_runner.py` | 이미지→OMR 자동화 | JPG/PNG | `.mxl`, `.omr` | 보통 수정 X |
| `music_pipeline.py` | 분석 5단계 조율 | `.mxl`, `.omr` | pipeline result | 분석 단계 변경 시 수정 |
| `musicxml_parser.py` | MusicXML 구조화 | `.mxl` | 구조 JSON | 음악 파싱 담당만 수정 권장 |
| `confidence_enricher.py` | 신뢰도/검수 판단 | JSON + `.omr` + `.mxl` | confidence/review | 기준 변경 시 신중히 수정 |
| `music_feature_analyzer.py` | 음악 특징 계산 | 구조 JSON | feature JSON | 새 특징 추가 시 수정 |
| `music_describer.py` | 상세 접근성 설명 | 구조 JSON | spokenText | 문장 정책 변경 시 수정 |
| `local_llm_summarizer.py` | 근거 기반 요약 | 구조+feature+review | summary | 모델/프롬프트 변경 시 수정 |

---

## 2.1 `api/music_api.py`

### 이 파일이 필요한 이유

브라우저/프론트는 Python 함수를 직접 호출할 수 없기 때문에 HTTP API가 필요합니다.

### 대표 흐름

```text
POST /api/music/recognize
↓
UploadFile 받기
↓
requestId 생성
↓
api_uploads에 저장
↓
recognize_music()
↓
MusicContent 반환
```

### 여기에서 수정할 가능성이 높은 것

```text
CORS
파일 업로드 크기
API 인증
응답에서 내부 path 제거
artifact download endpoint
로그인 사용자 정보 연결
DB 저장
```

### 여기에서 하지 않는 것이 좋은 것

```text
음표 count 계산
confidence 산식
선율 방향 계산
LLM Fact validation
```

이런 로직은 `services/` 안에서 관리하는 편이 좋습니다.

---

## 2.2 `music_recognizer.py`

### 역할

서비스 관점에서 가장 중요한 Python 함수 중 하나입니다.

```python
recognize_music(image_path)
```

한 번 호출하면:

```text
Audiveris 실행
+
Music Pipeline 실행
+
MusicContent 생성
```

까지 처리합니다.

### 향후 추가할 곳

점자악보 모듈이 추가된다면 예:

```text
pipeline_result
↓
braille converter
↓
brailleMusic
↓
build_music_content()
```

DAISY/HWP는 전체 문서 IR 단계에서 만들 가능성이 높으므로 여기서는 결과 reference만 넣는 방향이 좋습니다.

---

## 2.3 `audiveris_runner.py`

### 입력

```text
score.jpg
score.jpeg
score.png
```

### 출력

```text
score.mxl
score.omr
```

### 내부적으로 하는 일

```text
파일 검사
↓
Pillow로 이미지 크기 확인
↓
너무 크면 resize
↓
subprocess.run(Audiveris ...)
↓
stdout/stderr 저장
↓
return code 검사
↓
결과 파일 존재 검사
```

### 환경 의존 값

```text
AUDIVERIS_CMD
```

Mac에서 개발할 때와 Linux 서버에서 실행할 때 경로가 달라질 수 있으므로 코드에 서버 경로를 하드코딩하지 않고 환경변수를 사용합니다.

---

## 2.4 `music_pipeline.py`

### 입력

```text
mxl_path
omr_path
```

### 출력

대략:

```json
{
  "status": "DONE",
  "confidence": {},
  "review": {},
  "features": {},
  "spokenText": "...",
  "summary": {},
  "mapping": {}
}
```

### 내부 5단계

```text
MusicXML Parser
↓
Confidence / Review
↓
Feature Analysis
↓
SpokenText
↓
Grounded Summary
```

이 파일은 중앙 조율 역할을 하므로 개별 계산 로직을 너무 많이 넣지 않는 것이 좋습니다.

---

## 2.5 `musicxml_parser.py`

### 구조 JSON 예시 개념

```json
{
  "metadata": {},
  "parts": [
    {
      "name": "Voice",
      "measures": [
        {
          "number": 1,
          "events": [
            {
              "type": "note",
              "pitch": "C4",
              "duration": 1.0
            }
          ]
        }
      ]
    }
  ]
}
```

실제 필드는 더 많을 수 있습니다.

### 특별 주의

`music21`이 자동으로 만든 rest를 실제 OMR 결과로 오해하지 않도록 raw MusicXML과 비교하는 보정이 들어가 있습니다.

---

## 2.6 `confidence_enricher.py`

### 왜 필요한가

Audiveris가 결과를 냈다고 해서 모든 음표가 정확한 것은 아닙니다.

그래서:

```text
평균 confidence
최소 confidence
마디별/요소별 상태
OMR↔MusicXML↔JSON count
빈 마디
```

등을 보고 review level을 만듭니다.

### 주의

`average=0.80`을 `정확도 80%`라고 해석하면 안 됩니다.

Ground Truth 정확도는 `evaluation/`의 별도 평가 결과입니다.

---

## 2.7 `music_feature_analyzer.py`

### 만들어내는 데이터 예

```json
{
  "pitchRange": {
    "minimumPitch": "C4",
    "maximumPitch": "C5",
    "rangeSemitones": 12
  },
  "melodicContour": {
    "ascendingCount": 7,
    "descendingCount": 0,
    "repeatedCount": 0,
    "dominantDirection": "ASCENDING"
  }
}
```

이 데이터를 LLM이 근거로 사용할 수 있습니다.

---

## 2.8 `music_describer.py`

### 출력 예

```text
1마디에서는 ...
2마디에서는 ...
```

목표는 예쁜 문장보다 **정확하게 읽을 수 있는 문장**입니다.

LLM이 없어도 생성되어야 하는 핵심 접근성 출력입니다.

---

## 2.9 `local_llm_summarizer.py`

### 현재 모델

```text
qwen3:8b
```

### Ollama 연결

```text
OLLAMA_BASE_URL
```

### 핵심 안전장치

```text
LLM 자유 생성
X

Fact ID 선택
O
```

LLM이 실패하면 deterministic fallback을 사용합니다.

---

# 3. 데이터 파일 상세

| 파일/폴더 | 분류 | 설명 | 운영 필수? |
|---|---|---|---:|
| `M01.png~M05.png` | 테스트 입력 | 초기 샘플 악보 | X |
| `variants/` | 평가 입력 | original/small/tilt/lowq | X |
| `audiveris_output/` | 평가/개발 | 기존 수동 OMR 결과 | X |
| `ground_truth/` | 평가 정답 | 사람이 검수한/원본 MusicXML | X |
| `evaluation/` | 평가 결과 | 정확도 CSV/JSON | X |
| `api_uploads/` | 런타임 | 사용자 업로드 원본 | O |
| `music_api_runs/` | 런타임 | API 요청별 분석 결과 | O |
| `music_recognition_runs/` | 개발/CLI | CLI 직접 실행 결과 | X |
| `parsed_output/` | 중간 결과 | parser JSON | 내부 필요 |
| `confidence_output/` | 중간 결과 | confidence 반영 JSON | 내부 필요 |
| `pipeline_output/` | 내부 결과 | pipeline final JSON | 내부 필요 |
| `.mxl` | OMR 결과 | compressed MusicXML | O |
| `.omr` | OMR 근거 | Audiveris 프로젝트 | O 권장 |
| `music_content.json` | 최종 결과 | 풀스택 연동용 결과 | O |

---

# 4. 어떤 데이터가 최종 사용자에게 가는가

### 프론트에서 우선 사용하는 데이터

```text
summary.text
spokenText
review
```

### 검수/관리자 화면에서 추가 사용 가능

```text
confidence
mapping
features
summary.validation
summary.claims
```

### 일반 사용자에게 직접 노출하지 않아도 되는 데이터

```text
서버 로컬 path
runner stdout/stderr
raw mapping 전체
Audiveris command path
```

---

# 5. 어떤 데이터는 DB에 저장해야 하는가

현재 코드가 DB까지 강제하지는 않습니다.
풀스택에서 결정해야 합니다.

저장 후보:

```text
requestId
사용자/문서 ID
원본 파일 reference
MusicContent JSON
review 상태
검수 완료 여부
.mxl artifact ID
.omr artifact ID
생성 시간
수정 시간
```

파일 자체는 DB blob보다 object storage/파일 저장소에 두고 DB에는 reference만 저장하는 방식도 가능합니다.

---

# 6. 삭제/보관 정책이 필요한 파일

요청 1건마다 여러 파일이 생성됩니다.

```text
원본 이미지
전처리 이미지
.mxl
.omr
Audiveris log
pipeline JSON
music_content.json
```

따라서 운영 전에 보관 정책이 반드시 필요합니다.

예시:

```text
원본 업로드: 24시간
runner log: 7일
실패 작업: 7일
검수 완료된 MusicContent: 장기 보관
.mxl/.omr: 검수 근거로 보존 여부 결정
```

정확한 기간은 서비스 정책에 맞게 결정합니다.
