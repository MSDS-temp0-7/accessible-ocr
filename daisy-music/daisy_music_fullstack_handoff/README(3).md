# OCR-DAISY 악보 파트 — 풀스택 연동 README

> 이 문서는 현재 `daisy-music` 프로젝트의 **실제 폴더 구조**, **Python 파일별 역할**, **데이터 흐름**, **설치/실행 방법**, **풀스택팀이 설정해야 할 값**, **운영 시 주의사항**을 한 번에 이해할 수 있도록 정리한 문서입니다.

---

# 1. 프로젝트 목적

이 프로젝트의 악보 파트는 악보 이미지를 단순히 자연어로 설명하는 것이 아니라 다음 순서로 처리합니다.

```text
악보 이미지(JPG / JPEG / PNG)
        ↓
Audiveris OMR
        ↓
MusicXML(.mxl) + Audiveris 프로젝트(.omr)
        ↓
MusicXML 구조화
        ↓
Confidence / Review
        ↓
음악 특징 분석
        ↓
스크린리더용 상세 설명(spokenText)
        ↓
Grounded LLM Summary
        ↓
MusicContent JSON
```

핵심 원칙은 다음과 같습니다.

```text
이미지를 LLM이 직접 보고 음악 사실을 생성
X

OMR → MusicXML → 구조 데이터 → 검증된 사실
→ LLM은 제한된 사실을 선택/요약
O
```

즉, LLM이 자유롭게 악보 내용을 추측하지 않도록 하고 실제 OMR/MusicXML 근거를 기반으로 접근성 정보를 생성합니다.

---

# 2. 현재 구현된 기능

현재 아래 기능까지 구현되어 있습니다.

```text
악보 이미지 입력
→ 큰 이미지 자동 Resize
→ Audiveris CLI 자동 실행
→ .mxl 생성
→ .omr 생성
→ MusicXML Parser
→ Confidence / Review
→ Music Feature Analysis
→ Rule 기반 spokenText
→ Grounded LLM Summary
→ LLM 실패 시 deterministic fallback
→ MusicContent JSON
```

현재 최종 출력에서 사용할 수 있는 주요 값은 다음과 같습니다.

- `musicXml`
- `spokenText`
- `summary`
- `confidence`
- `review`
- `features`
- `mapping`
- `.mxl` 결과 경로
- `.omr` 결과 경로

향후 확장을 위해 아래 필드는 미리 예약되어 있습니다.

```json
{
  "brailleMusic": null,
  "outputs": {
    "daisy": null,
    "hwp": null
  },
  "playback": null
}
```

현재 `null`인 것은 오류가 아니라 아직 구현 전이라는 의미입니다.

---

# 3. 전체 호출 구조

풀스택에서는 내부 Python 파일을 각각 직접 호출할 필요가 없습니다.

최종적으로 아래 API만 호출하는 구조를 목표로 합니다.

```text
POST /api/music/recognize
```

전체 내부 흐름은 다음과 같습니다.

```text
Frontend
   ↓
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
                  ↓
            Grounded Summary
                  ↓
             MusicContent
                  ↓
             FastAPI Response
```

---

# 4. 현재 실제 프로젝트 폴더 구조

현재 로컬 프로젝트의 최상위 폴더는 다음과 같습니다.

```text
daisy-music/
├── .git/
├── .venv/
├── api/
├── audiveris_auto_test/
├── audiveris_input/
├── audiveris_output/
├── audiveris_runs/
├── confidence_output/
├── evaluation/
├── feature_output/
├── ground_truth/
├── music_recognition_runs/
├── parsed_output/
├── pipeline_output/
├── services/
├── spoken_output/
├── summary_output/
└── variants/
```

현재 로컬에는 없지만 API를 실제 실행하면 아래 폴더가 생성될 수 있습니다.

```text
api_uploads/
music_api_runs/
```

---

# 5. 폴더별 상세 설명

## 5.1 `.git/`

Git 저장소 내부 관리 폴더입니다.

```text
용도:
- commit 기록
- branch 정보
- remote 정보
```

직접 수정하지 않습니다.

분류:

```text
개발 관리용
Git 필수
운영 데이터 아님
```

---

## 5.2 `.venv/`

현재 Python 가상환경입니다.

예:

```text
Python
music21
Pillow
FastAPI
urllib3
기타 dependency
```

풀스택 서버에서 이 폴더 자체를 복사하는 것은 권장하지 않습니다.

서버에서는 새로 생성합니다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

분류:

```text
개발 환경
Git 저장 X
서버에서 재생성
```

---

## 5.3 `api/`

풀스택이 접근하는 HTTP API 영역입니다.

현재 핵심 파일:

```text
api/
├── __init__.py
└── music_api.py
```

### `music_api.py`

역할:

```text
Frontend 요청 받기
↓
파일 검사
↓
requestId 생성
↓
업로드 파일 저장
↓
recognize_music() 호출
↓
HTTP JSON 응답 반환
```

풀스택팀이 수정할 가능성이 높은 부분:

```text
CORS
API 인증
업로드 크기 제한
DB 연결
사용자 ID 연결
응답 포맷
파일 다운로드 endpoint
서버 저장 경로
```

음악 분석 계산은 이 파일에서 하지 않는 것이 좋습니다.

---

## 5.4 `services/`

악보 분석 핵심 로직이 들어 있는 폴더입니다.

```text
services/
├── audiveris_runner.py
├── music_recognizer.py
├── music_pipeline.py
├── musicxml_parser.py
├── confidence_enricher.py
├── music_feature_analyzer.py
├── music_describer.py
└── local_llm_summarizer.py
```

각 파일은 아래에서 별도로 설명합니다.

---

## 5.5 `audiveris_auto_test/`

Audiveris CLI 자동 실행 기능을 처음 확인하기 위해 만든 **수동 테스트 폴더**입니다.

예:

```text
audiveris_auto_test/
├── M01_4000.mxl
├── M01_4000.omr
├── M01_4000-xxxx.log
└── 과거 실패 테스트 결과
```

이 폴더는 다음 기능을 확인하기 위해 사용했습니다.

```text
-batch
-transcribe
-export
-save
```

현재는 `audiveris_runner.py`가 자동화되어 있으므로 운영에 필요하지 않습니다.

분류:

```text
과거 개발 테스트용
운영 필수 X
Git 저장 X
삭제 가능
```

---

## 5.6 `audiveris_input/`

Audiveris의 약 20M pixel 제한을 확인하기 전에 수동으로 이미지를 줄여 테스트할 때 사용한 폴더입니다.

예:

```text
M01.png
11256 x 15372
↓
수동 resize
↓
M01_4000.png
```

현재는 `audiveris_runner.py`가 자동으로 Resize하기 때문에 운영에는 필요 없습니다.

분류:

```text
과거 전처리 테스트용
운영 필수 X
Git 저장 X
삭제 가능
```

---

## 5.7 `audiveris_output/`

초기 개발 및 OMR 평가 과정에서 Audiveris GUI/수동 실행으로 생성한 결과를 보관한 폴더입니다.

주요 파일:

```text
*.mxl
*.omr
```

용도:

```text
OMR 평가
Parser 개발
Confidence 개발
Ground Truth 비교
기존 샘플 재실행
```

현재 API 운영 시 직접 사용하는 폴더는 아닙니다.

분류:

```text
개발/평가용
운영 필수 X
평가 재현용으로는 보존 권장
```

---

## 5.8 `audiveris_runs/`

`services/audiveris_runner.py`를 **단독 CLI로 실행할 때** 만들어지는 결과 폴더입니다.

예:

```bash
python services/audiveris_runner.py M01.png
```

실행 후 예:

```text
audiveris_runs/
└── M01_20260907T123918_88d8606f/
    ├── _input/
    │   └── M01.png
    ├── M01.mxl
    ├── M01.omr
    ├── runner_stdout.log
    └── runner_stderr.log
```

`_input/`에는 Audiveris에 실제로 전달된 이미지가 들어갑니다. 원본 이미지가 너무 크면 자동 Resize된 이미지가 저장됩니다.

분류:

```text
개발/디버깅용
운영 API에서 직접 접근할 필요 X
Git 저장 X
```

---

## 5.9 `parsed_output/`

`musicxml_parser.py`가 생성하는 **MusicXML 구조화 중간 결과**입니다.

흐름:

```text
.mxl
↓
musicxml_parser.py
↓
parsed_output/<name>.json
```

포함되는 데이터 예:

```text
metadata
parts
measures
notes
rests
chords
pitch
duration
tie
slur
articulation
dynamic
```

이 데이터가 이후 confidence, feature, spokenText, summary의 기본 입력이 됩니다.

분류:

```text
내부 중간 결과
프론트 직접 접근 X
Git 저장 X
```

---

## 5.10 `confidence_output/`

OMR 결과와 구조 JSON을 비교하여 Confidence / Review 정보를 붙인 중간 결과입니다.

흐름:

```text
parsed JSON
+
.omr
+
.mxl
↓
confidence_enricher.py
↓
confidence_output/
```

주요 데이터:

```text
average confidence
minimum confidence
measureCount
mapping
review.level
review.needsReview
review.reasons
```

주의:

```text
Confidence 0.80
≠
실제 정확도 80%
```

실제 정확도는 `ground_truth/`와 `evaluation/`을 통해 별도로 측정합니다.

분류:

```text
내부 중간 결과
검수 판단 근거
Git 저장 X
```

---

## 5.11 `feature_output/`

`music_feature_analyzer.py`가 계산한 음악 구조 특징을 저장합니다.

예:

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

대표 특징:

```text
음역
최저음
최고음
음역 semitone
상승 진행
하강 진행
반복음
평균 음정
최대 음정
리듬 밀도
활성 마디
```

분류:

```text
내부 분석 결과
필요 시 관리자/검수 UI에서 활용 가능
Git 저장 X
```

---

## 5.12 `spoken_output/`

`music_describer.py`가 생성한 **스크린리더용 상세 접근성 설명**을 저장합니다.

예:

```text
1마디에서는 ...
2마디에서는 ...
3마디에서는 ...
```

이 출력은 LLM 자유 생성이 아니라 Rule/Template 기반입니다.

목적:

```text
자연스러운 감상문 생성
X

악보 내용을 정확하게 읽을 수 있게 설명
O
```

즉 `summary`보다 더 상세한 접근성 정보입니다.

분류:

```text
핵심 접근성 출력의 중간 저장
프론트에서는 최종 MusicContent.spokenText 사용
Git 저장 X
```

---

## 5.13 `summary_output/`

`local_llm_summarizer.py`가 생성한 **Grounded Summary 결과**를 저장하는 폴더입니다.

흐름:

```text
Music Structure
+
Feature
+
Review
↓
Fact Catalog
↓
Ollama / qwen3:8b
↓
Fact ID 선택
↓
Validation
↓
summary_output/
```

포함될 수 있는 주요 데이터:

```text
summary.text
claims
Fact ID
mandatory facts
optional facts
evidence
validation
retried
fallbackUsed
selectedBy
```

예:

```text
Validation: PASS
Optional Selected By: local_llm
Retry: False
Fallback: False
```

LLM이 꺼져 있으면:

```text
Ollama 실패
↓
deterministic fallback
↓
Validation PASS
```

중요:

```text
summary.validation.passed = true
```

는 **OMR이 100% 정확하다는 의미가 아닙니다.**

의미는:

```text
생성된 자연어 요약이
현재 추출된 구조 데이터에 근거하고 있는가?
```

입니다.

분류:

```text
내부 요약 결과
프론트에서는 MusicContent.summary 사용
Git 저장 X
```

---

## 5.14 `pipeline_output/`

`music_pipeline.py`의 전체 분석 결과입니다.

내부 순서:

```text
1. MusicXML Parser
2. Confidence / Review
3. Feature Analysis
4. SpokenText
5. Grounded Summary
```

위 결과를 하나로 묶어 저장합니다.

예:

```json
{
  "status": "DONE",
  "confidence": {},
  "review": {},
  "features": {},
  "spokenText": "...",
  "summary": {},
  "mapping": {},
  "warnings": []
}
```

`pipeline_output/`은 Core Pipeline 내부 결과이고, `music_content.json`은 풀스택/IR에 넘기기 위한 최종 포장 결과입니다.

분류:

```text
Core 내부 최종 결과
디버깅/검수용
Git 저장 X
```

---

## 5.15 `music_recognition_runs/`

`services/music_recognizer.py`를 CLI로 직접 실행할 때 생성되는 **End-to-End 실행 결과**입니다.

예:

```bash
python services/music_recognizer.py M01.png
```

결과 예:

```text
music_recognition_runs/
└── M01_20260908T131915_4353712f/
    ├── _input/
    ├── M01.mxl
    ├── M01.omr
    ├── runner_stdout.log
    ├── runner_stderr.log
    └── music_content.json
```

차이:

```text
audiveris_runs/
→ Audiveris만 단독 테스트

music_recognition_runs/
→ Audiveris + 전체 Music Pipeline 테스트
```

분류:

```text
CLI End-to-End 개발 테스트
운영 필수 X
Git 저장 X
```

---

## 5.16 `api_uploads/` — API 실행 시 생성 예정

현재 로컬 폴더 목록에는 없습니다.

FastAPI를 실행하고 실제 업로드 요청을 받으면 사용합니다.

예:

```text
api_uploads/
└── <requestId>/
    └── input.png
```

역할:

```text
사용자가 업로드한 원본 파일 저장
```

분류:

```text
운영 런타임
Git 저장 X
```

---

## 5.17 `music_api_runs/` — API 실행 시 생성 예정

현재 로컬 폴더 목록에는 없습니다.

`POST /api/music/recognize` 요청을 처리할 때 요청별 분석 결과를 저장합니다.

차이:

```text
music_recognition_runs/
→ 개발자가 CLI 직접 실행

music_api_runs/
→ 풀스택 / Frontend가 HTTP API 호출
```

분류:

```text
운영 런타임
Git 저장 X
```

---

## 5.18 `ground_truth/`

OMR 정확도 평가용 정답 데이터를 저장합니다.

예:

```text
사람이 검수한 MusicXML
직접 생성한 원본 MusicXML
```

OMR 출력과 비교해 실제 정확도를 계산합니다.

예:

```text
Pitch Precision / Recall / F1
Rest
Duration
Accidental
Time Signature
Key Signature
Chord
Tie
Slur
Dynamics
Repeat
Tempo
```

분류:

```text
평가 정답
운영 API 필수 X
평가 재현을 위해 보존 권장
```

---

## 5.19 `evaluation/`

Ground Truth를 기반으로 평가한 결과를 저장합니다.

목적:

```text
OMR 실제 정확도 측정
조건별 성능 비교
confidence와 실제 accuracy 비교
```

주의:

```text
confidence
≠
ground-truth accuracy
```

분류:

```text
연구/평가용
운영 API 필수 X
```

---

## 5.20 `variants/`

기존 M01~M05 악보의 변형 입력을 저장합니다.

대표 조건:

```text
original
small
tilt
lowq
```

목적:

```text
크기 변화
기울기
저화질
등의 조건에서 OMR 성능 변화 측정
```

분류:

```text
Robustness 평가용
운영 필수 X
```

---

# 6. Python 파일별 역할

## 6.1 `api/music_api.py`

풀스택이 호출하는 HTTP API 진입점입니다.

대표 endpoint:

```text
GET  /api/music/health
POST /api/music/recognize
```

입력:

```text
multipart/form-data
image_file=<JPG/JPEG/PNG>
```

하는 일:

```text
파일 확장자 확인
↓
파일 크기 제한 확인
↓
requestId 생성
↓
업로드 저장
↓
recognize_music() 호출
↓
HTTP JSON 응답
```

---

## 6.2 `services/music_recognizer.py`

서비스 관점에서 가장 중요한 조율 파일입니다.

대표 함수:

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

---

## 6.3 `services/audiveris_runner.py`

악보 이미지를 Audiveris에 넣어 `.mxl`, `.omr`을 생성합니다.

입력:

```text
JPG
JPEG
PNG
```

출력:

```text
.mxl
.omr
```

내부 흐름:

```text
이미지 검사
↓
Pillow로 이미지 크기 확인
↓
너무 크면 자동 Resize
↓
Audiveris CLI
↓
.mxl / .omr 생성 여부 확인
↓
로그 저장
```

환경 의존 설정:

```text
AUDIVERIS_CMD
```

---

## 6.4 `services/music_pipeline.py`

Core 음악 분석 파이프라인을 순서대로 실행합니다.

입력:

```text
mxl_path
omr_path
```

내부 순서:

```text
[1/5] MusicXML Parser
[2/5] Confidence / Review
[3/5] Feature Analysis
[4/5] SpokenText
[5/5] Grounded LLM Summary
```

---

## 6.5 `services/musicxml_parser.py`

MusicXML을 Python/JSON 구조로 바꿉니다.

주요 추출 정보:

```text
part
measure
note
rest
chord
pitch
duration
tie
slur
articulation
dynamic
metadata
```

---

## 6.6 `services/confidence_enricher.py`

Audiveris OMR 정보와 MusicXML/JSON을 비교하여 신뢰도 및 검수 필요 여부를 계산합니다.

Review 단계:

```text
LOW
MEDIUM
HIGH
```

`HIGH`는 사람이 확인할 필요가 높은 상태를 의미합니다.

---

## 6.7 `services/music_feature_analyzer.py`

음악적 구조 특징을 계산합니다.

예:

```text
Pitch Range
Melodic Contour
Ascending / Descending
Repeated Note
Rhythm Density
Active Measures
```

---

## 6.8 `services/music_describer.py`

Rule/Template 기반 상세 접근성 텍스트를 생성합니다.

출력:

```text
spokenText
```

LLM이 꺼져 있어도 생성되어야 하는 핵심 접근성 기능입니다.

---

## 6.9 `services/local_llm_summarizer.py`

Ollama의 Local LLM을 이용해 악보 구조를 짧게 요약합니다.

현재 사용 모델:

```text
qwen3:8b
```

핵심 정책:

```text
LLM 자유 생성
X

이미 생성된 Fact ID 선택
O
```

LLM 장애 시 deterministic fallback으로 전체 파이프라인은 계속 동작합니다.

---

# 7. 주요 데이터 파일 종류

## `.mxl`

Compressed MusicXML입니다.

용도:

```text
음표/쉼표/박자/조성 등 구조 근거
점자악보 변환 입력 후보
MIDI/playback 입력 후보
오류 분석
```

## `.omr`

Audiveris 프로젝트 파일입니다.

용도:

```text
Audiveris 인식 근거
confidence 추출
오류 디버깅
향후 검수
```

가능하면 `.mxl`과 함께 보존하는 것을 권장합니다.

## `music_content.json`

풀스택 연동에서 가장 중요한 최종 결과입니다.

대표 구조:

```json
{
  "type": "music",
  "status": "DONE",
  "musicXml": "...",
  "spokenText": "...",
  "summary": {},
  "features": {},
  "confidence": {},
  "review": {},
  "mapping": {},
  "brailleMusic": null,
  "outputs": {
    "daisy": null,
    "hwp": null
  },
  "playback": null
}
```

---

# 8. 요청 1건의 실제 파일 흐름

```text
1. Frontend
score.png 선택

2. POST /api/music/recognize
image_file=score.png

3. music_api.py
requestId 생성

4. api_uploads/
api_uploads/<requestId>/input.png

5. music_recognizer.py
recognize_music(input.png)

6. audiveris_runner.py
이미지 크기 검사
↓
필요 시 Resize
↓
Audiveris 실행

7. Audiveris 출력
input.mxl
input.omr

8. music_pipeline.py

input.mxl
↓
parsed_output/

.omr + parsed JSON
↓
confidence_output/

parsed JSON
↓
feature_output/

parsed JSON
↓
spoken_output/

structure + features + review
↓
summary_output/

전체 결합
↓
pipeline_output/

9. music_recognizer.py
MusicContent 생성

10. music_content.json 저장

11. FastAPI Response

12. Frontend / IR
```

---

# 9. 풀스택에서 우선 사용할 필드

일반 사용자 화면:

```text
musicContent.summary.text
musicContent.spokenText
musicContent.review.level
musicContent.review.needsReview
musicContent.review.reasons
```

검수/관리자 화면:

```text
musicContent.confidence
musicContent.mapping
musicContent.features
musicContent.summary.validation
musicContent.summary.claims
```

---

# 10. 설치 환경

권장:

```text
Python 3.11
Audiveris 5.10.2
Ollama 또는 기존 Local LLM 서버
qwen3:8b
```

Python 설치:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

# 11. Audiveris 설정

개발 Mac 예:

```text
/Applications/Audiveris.app/Contents/MacOS/Audiveris
```

서버에서는 실제 설치 경로를 확인해 설정합니다.

```bash
export AUDIVERIS_CMD=/실제/서버/Audiveris/경로
```

확인:

```bash
$AUDIVERIS_CMD -version
```

---

# 12. Ollama 설정

기존 Ollama 서버를 사용한다면 새로 설치할 필요 없습니다.

예:

```bash
export OLLAMA_BASE_URL=http://서버IP:11434
```

필요 모델:

```text
qwen3:8b
```

LLM이 꺼져 있어도 deterministic fallback으로 API가 성공할 수 있도록 설계되어 있습니다.

---

# 13. 주요 환경변수

```env
AUDIVERIS_CMD=/path/to/Audiveris
AUDIVERIS_TIMEOUT=600

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b

MUSIC_UPLOAD_ROOT=./api_uploads
MUSIC_RECOGNITION_ROOT=./music_api_runs

MAX_MUSIC_UPLOAD_BYTES=52428800

CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

풀스택팀에서 반드시 확인해야 할 값:

```text
AUDIVERIS_CMD
OLLAMA_BASE_URL
OLLAMA_MODEL
CORS_ORIGINS
API PORT
업로드 저장 위치
분석 결과 저장 위치
업로드 최대 크기
파일 보관 기간
```

---

# 14. API 실행

```bash
pip install fastapi uvicorn python-multipart
```

실행:

```bash
uvicorn api.music_api:app \
  --host 0.0.0.0 \
  --port 8000
```

개발 Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 15. API

## Health

```http
GET /api/music/health
```

## Recognize

```http
POST /api/music/recognize
Content-Type: multipart/form-data
```

입력:

```text
image_file=<악보 이미지>
```

---

# 16. 현재 구현되지 않은 기능

## 점자악보

현재:

```json
"brailleMusic": null
```

향후 예상:

```text
MusicXML / MusicStructure
↓
Braille Music Converter
↓
brailleMusic
```

## DAISY

현재:

```json
"outputs": {
  "daisy": null
}
```

DAISY는 전체 문서 읽기 순서와 함께 연결할 예정입니다.

## HWP

현재:

```json
"outputs": {
  "hwp": null
}
```

전체 OCR 문서 IR/serializer 단계에서 연결할 예정입니다.

## Playback

현재:

```json
"playback": null
```

MusicContent IR 구조 확정 후 MIDI 등의 재생 기능을 추가할 예정입니다.

---

# 17. 운영 전에 풀스택팀이 결정해야 할 것

```text
[ ] 실제 서버 OS
[ ] Audiveris 설치 경로
[ ] 기존 Ollama 서버 주소
[ ] qwen3:8b 사용 가능 여부
[ ] Frontend 실제 Origin
[ ] API host / port
[ ] 업로드 파일 저장 위치
[ ] 분석 artifact 저장 위치
[ ] 파일 삭제/보관 기간
[ ] DB에 저장할 필드
[ ] .mxl / .omr 보관 방식
[ ] 로컬 filesystem path를 외부 응답에서 제거할지
[ ] API 인증 방식
[ ] 요청이 길어질 경우 async job 방식으로 전환할지
```

---

# 18. 권장 DB 저장 항목

```text
requestId
userId
documentId
source image reference
MusicContent JSON
review.level
review.needsReview
검수 완료 여부
.mxl artifact reference
.omr artifact reference
createdAt
updatedAt
```

---

# 19. 파일 보관 정책

요청 1건마다 아래 파일이 생성될 수 있습니다.

```text
원본 이미지
Resize 이미지
.mxl
.omr
Audiveris log
parsed JSON
confidence JSON
feature JSON
spokenText
summary JSON
pipeline JSON
music_content.json
```

예:

```text
성공 요청
→ 7~30일 보관 후 삭제

실패 요청
→ 디버깅을 위해 조금 더 오래 보관

Ground Truth / Evaluation
→ 영구 보관
```

---

# 20. 보안/운영 주의사항

- Ollama 포트를 브라우저에 직접 공개하지 않습니다.
- Frontend는 Music API만 호출합니다.
- 파일 확장자와 크기를 검사합니다.
- 서버 로컬 파일 경로를 일반 사용자에게 그대로 노출하지 않는 것을 권장합니다.
- 실제 프론트 주소만 CORS에 허용합니다.
- Audiveris 결과 파일은 서버 내부 통제된 디렉터리에 저장합니다.

---

# 21. 현재 검증 완료 상태

로컬에서 아래 End-to-End 흐름까지 확인했습니다.

```text
대형 원본 PNG
↓
자동 Resize
↓
Audiveris CLI
↓
MusicXML + OMR
↓
Parser
↓
Confidence / Review
↓
Feature Analysis
↓
SpokenText
↓
Grounded LLM
↓
MusicContent JSON
```

Ollama ON:

```text
Optional Selected By: local_llm
Fallback: False
Validation: PASS
```

Ollama OFF:

```text
Optional Selected By: deterministic_fallback
Fallback: True
Validation: PASS
```

---

# 22. 풀스택 1차 연동 완료 기준

```text
[ ] GET /api/music/health 응답
[ ] Audiveris available = true
[ ] 악보 JPG/PNG 업로드 성공
[ ] success = true
[ ] status = DONE
[ ] .mxl 생성
[ ] .omr 생성
[ ] spokenText 존재
[ ] summary.text 존재
[ ] confidence 존재
[ ] review 존재
[ ] summary.validation.passed = true
[ ] Ollama ON → fallbackUsed = false
[ ] Ollama OFF → fallback으로 요청 성공
```

---

# 23. 폴더를 한눈에 구분하면

```text
[코드]
api/
services/

[개발 환경]
.venv/
.git/

[Core 중간 결과]
parsed_output/
confidence_output/
feature_output/
spoken_output/
summary_output/
pipeline_output/

[Audiveris 개발/디버깅]
audiveris_input/
audiveris_auto_test/
audiveris_output/
audiveris_runs/

[End-to-End CLI 테스트]
music_recognition_runs/

[API 운영 시 생성]
api_uploads/
music_api_runs/

[평가]
ground_truth/
evaluation/
variants/
```

풀스택 1차 연동에서 핵심적으로 봐야 할 것은 다음입니다.

```text
api/
services/
requirements.txt
.env 설정
Audiveris
Ollama
```

반대로 아래는 서비스 실행에 필수적이지 않은 개발/평가 데이터입니다.

```text
audiveris_auto_test/
audiveris_input/
audiveris_output/
variants/
ground_truth/
evaluation/
```
