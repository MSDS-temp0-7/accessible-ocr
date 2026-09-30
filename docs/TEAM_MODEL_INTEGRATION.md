# 팀 도표·악보 모델 적용 (2026-09-18)

> 2026-09-28 보완: 로컬 Audiveris를 5.11.0으로 연결하고 음악 요약을
> Ollama `qwen3:14b`로 검증했다. 악보 영역은 15% 확장한 뒤
> `No system found`에서 페이지 폭·35% 세로 여백으로 자동 재시도한다.
> 실제 악보 실추론은 성공했지만 `ocr_test_sample.pdf`의 단순 그림은 확장
> 후에도 Audiveris system으로 인식되지 않으므로 시연에는 실제 악보 PDF를
> 사용한다. 현재 Python 회귀 테스트는 20개 통과한다.

## 적용 결과

- 도표: 바탕화면 `ai_engine`의 F3 코드를 저장소에 복사하고 Qwen2.5-VL-7B-Instruct를 4비트로 실행한다. 원본 폴더와 전달받은 `.venv`는 수정하지 않았다.
- 악보: 바탕화면 `daisy-music/services`와 기존 저장소를 비교했다. 줄바꿈을 제외하면 기존 Windows 경로 탐색 보완 이외의 핵심 로직은 같았다. 기존 Windows 호환 코드를 유지하고 Audiveris 5.10.2 실행 파일을 연결했다.
- 본문: 기존 CLOVA OCR을 유지한다. 실제 키는 변경하지 않았다.
- 모델 서버의 결과는 여전히 WPF 검수용 `book.xml`, `review.json`, 페이지
  이미지 ZIP이다. 별도의 WPF WF-08 내보내기가 이 검수 결과를 textNCX
  DAISY3 ZIP과 HTML 검수 보고서로 변환한다.

## 실행

이미 구성된 이 PC에서는 기존 API 창에서 진행 중인 작업이 끝난 뒤 Ctrl+C로 종료하고, 저장소 루트에서 다시 실행한다.

```powershell
.\scripts\start-local-ocr.ps1
```

기본 스크립트의 동기화가 변경한 Python 패키지를 다시 설치하므로 이번 첫 재시작에는 `-SkipSync`를 사용하지 않는다. API를 재시작하면 이전 작업·검수 메모리는 사라지므로 필요한 결과를 먼저 확인한다. 앱에서는 PDF를 새로 분석해야 새 모델 결과가 나온다.

처음 시험할 때는 `ocr_test_sample.pdf`의 1페이지(도표), 3페이지(악보)를 각각 분석한다. 수식 전용 변환은 이번 작업의 범위가 아니다.

새 PC에서 도표 환경을 만들 때:

```powershell
.\scripts\setup-chart.ps1
```

이 PC에서 검증한 도표 환경은 RTX 4060 8GB, PyTorch 2.6.0+cu124, Transformers 4.57.1, bitsandbytes 0.49.2다. 재현용 목록은 `ai_engine/requirements-tested.txt`다. CUDA PyTorch의 다운로드 원본은 setup 스크립트에 명시했다.

## 로컬 설정

`config/integration-api.env`:

```dotenv
CHART_RECOGNITION_ENABLED=true
CHART_MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct
CHART_TIMEOUT=900
CHART_MAX_PIXELS=401408
MUSIC_RECOGNITION_ENABLED=true
MUSIC_MODEL_ROOT=daisy-music
MUSIC_SUMMARY_MODE=rules
AUDIVERIS_CMD=이_PC에_준비된_Audiveris.exe_절대경로
```

실제 `AUDIVERIS_CMD`는 이미 로컬 파일에 설정했다. 공식 Windows Console MSI를 `.tools/audiveris`에 추출해 사용한다. Java 25 런타임이 포함되어 있어 기존 Java 17을 바꿀 필요는 없다. `.tools`, `.venv-chart`, `.model-cache`와 실제 `.env`는 Git에서 제외된다.

## 처리 경로

1. CLOVA가 페이지 글자를 읽고 DocLayout-YOLO가 영역을 찾는다.
2. 표/그림 영역을 잘라 F3 ChartAnalyzer에 전달한다. 이미 잘린 영역이므로 팀 코드의 두 번째 YOLO 검출은 생략한다.
3. 별도 `.venv-chart` 프로세스가 Qwen 모델을 최초 한 번 로드하고 이후 영역에서 재사용한다. 기존 CPU 레이아웃 코드의 `CUDA_VISIBLE_DEVICES=-1`이 GPU 프로세스로 전파되지 않도록 분리했다.
4. 제목·축·범례·수치·설명을 WPF가 읽는 TranscribedRegion으로 변환한다. 이 분석은 표의 셀 구조 복원 기능을 대신하지 않는다.
5. 악보 문맥이 있는 페이지의 가장 큰 Picture 영역은 사방 15% 확장해 Music에 전달한다. `No system found`이면 페이지 전체 폭과 더 큰 세로 여백으로 한 번 재시도한다. Audiveris가 새 MusicXML/OMR을 만들면 팀 파이프라인이 마디별 읽기·요약을 생성한다.
6. 한 특수 영역이 실패하면 해당 영역에 오류와 검수 필요 상태를 표시하고 나머지 문서 처리는 계속한다. 도표 실패 시 해당 영역에서 CLOVA가 읽은 글자도 보존한다.

## Ollama는 선택 사항

기본 예시는 `MUSIC_SUMMARY_MODE=auto`이며 Ollama를 먼저 사용하고 실패하면 같은 규칙 방식으로 자동 전환한다. 음표·쉼표·마디 인식은 Audiveris/MusicXML이 담당하고, Ollama는 검증된 음악 사실 중 요약에 넣을 항목만 고른다.

Ollama를 사용하지 않을 PC는 `MUSIC_SUMMARY_MODE=rules`로 바꿀 수 있다. 이 경우 `deterministic_rules`가 표시된다. `auto`에서 접속이나 추론이 실패하면 `deterministic_fallback`으로 표시되며 전체 악보 처리는 계속된다.

로컬 기본 시연 설정은 설치된 `qwen3:14b`를 `LOCAL_LLM_MODEL=qwen3:14b`로 지정한다. 기존 `qwen3:8b`도 같은 역할로 사용할 수 있다. 14B는 더 큰 텍스트 모델이지만 이미지 입력은 처리하지 않으므로 도표용 `Qwen2.5-VL-7B-Instruct`를 대체하지 않는다. 기본 주소는 `http://127.0.0.1:11434`다. `LOCAL_LLM_THINK=false`로 JSON 외 사고 출력을 막고 `LOCAL_LLM_KEEP_ALIVE=0`으로 요청 후 모델을 내려 두 GPU 모델의 메모리 경쟁을 줄인다.

## 확인한 문제와 수정

- 팀 ChartAnalyzer의 `from config`를 패키지 상대 import로 수정했다.
- 이미 검출한 영역의 중복 크롭을 제거했다. 문서 모델 로드 실패 시 일반 사물 YOLO로 조용히 대체하는 동작도 제거했다.
- 응답 필드 파싱 정규식을 수정하고 설명에 추가된 숫자가 점수를 낮추도록 보수적으로 검수했다. 이 점수는 실제 정확도를 보장하는 확률이 아니다.
- CPU 레이아웃 엔진이 GPU를 숨기는 환경변수 충돌을 재현하고 수정했다.
- Windows Python/Java 출력의 인코딩을 지정했다. 음악 파서 호출에 제한 시간을 두었다.
- API 종료 시 도표 하위 프로세스도 종료하도록 처리했다.

## 검증 기록

| 검증 | 결과 |
| --- | --- |
| 합성 막대 그래프 실추론 | 10/20/30 수치와 한국어 설명 생성 성공. 초기 모델 로드 포함 약 1분 |
| 1페이지 PDF 실 API | CLOVA → 레이아웃 → 팀 도표 → 결과 ZIP 성공. 약 63초, 도표 결과 needs_review 유지 |
| 악보 신규 이미지 실추론 | 사용자의 일반 PowerShell에서 약 20초, MusicXML 생성, 음표 8개·쉼표 28개, 평균 모델 신뢰도 0.807 |
| 악보 상세 | 한국어 요약, `[악보 시작]` 마디별 읽기 확인 |
| 기존 MusicXML/OMR 후처리 | 별도 샘플 통과. 이 검증은 신규 이미지 인식과 구분하며 빈 마디 경고를 유지 |
| Python 회귀 테스트 | 17개 통과: 영역 전달/실패 격리/패키지/파싱/GPU 격리/규칙 모드 무네트워크 |
| WPF Debug 빌드 | 경고 0, 오류 0. 자동 실행 환경의 SDK 표시명 조회 제한 때문에 TargetPlatformMoniker를 명시하고 별도 출력 폴더로 빌드 |

테스트 자료와 상세 로그는 `artifacts/team-model-tests` 및 `artifacts/chart-worker.log`에 있다. 자동 실행 환경에서는 Java 파일 접근이 거부되어 악보 신규 인식은 사용자가 같은 스크립트를 일반 PowerShell에서 실행했고, 생성된 `music-report.json`의 성공·MusicXML·내용을 확인했다.

수동 재검증:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\test-team-models.py --mode chart
.\.venv\Scripts\python.exe -X utf8 scripts\test-team-models.py --mode music
```

## 남은 제한

- 악보 위치는 전용 검출 모델이 아닌 문맥 기반 임시 규칙이다. 악보라는 문구가 없는 악보는 놓칠 수 있다.
- 일반 그림도 Picture로 분류되므로 도표 프롬프트에 전달될 수 있다. 그림/그래프 분류 개선이 필요하다.
- 표 내용의 텍스트 설명은 생성하지만 셀·병합·행열 구조의 완전한 복원은 구현하지 않았다.
- 모델이 PASS를 반환해도 사람의 검수를 대신하지 않으며 WPF에서는 특수 영역을 needs_review로 유지한다.
- 검수 내용 영구 저장은 후속 개발이다. textNCX DAISY 패키징과 HTML 검수
  보고서는 WPF에 구현됐으며, 외부 표준 검증기·DAISY 플레이어 호환성 검증은 남아 있다.
