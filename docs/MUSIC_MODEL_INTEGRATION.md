# 악보 인식 모델 연결

최종 갱신: 2026-09-16

## 현재 연결 상태

`daisy-music`의 Audiveris 기반 인식기를 `daisy_ocr.server`의 PDF Job 안에서
직접 호출한다. 별도의 두 번째 HTTP 서버를 실행할 필요는 없다.

```text
PDF 페이지
  -> CLOVA OCR + DocLayout-YOLO
  -> 악보 문맥 페이지의 가장 큰 Picture 영역을 music으로 승격
  -> 영역 PNG crop
  -> daisy-music/services/music_recognizer.py
  -> Audiveris .mxl/.omr
  -> MusicXML 분석 + 신뢰도 + 검수 사유 + spokenText
  -> TranscribedRegion(type=music)
  -> book.xml/review.json -> WPF 악보 상세 화면
```

`ocr_test_sample.pdf`의 3페이지에는 `악보`, `Sheet Music` 문맥과 큰 악보
그림이 있어 위 경로로 들어간다. 현재 DocLayNet 가중치에는 music 클래스가
없으므로, 일반 문서에서 악보를 자동 검출하는 전용 모델을 대신하는 임시 승격
규칙이다. 문맥이 없는 일반 그림은 악보로 보내지 않는다.

## 최초 준비

Python 의존성은 루트 `pyproject.toml`에 포함되어 있으며
`scripts/start-local-ocr.ps1`이 `music21`과 `requests`까지 설치한다.

악보 이미지 자체의 OMR 실행에는 다음 외부 프로그램이 추가로 필요하다.

- Java 런타임
- Audiveris
- 선택 사항: Ollama와 `qwen3:8b`; 없으면 모델팀 코드의 규칙 기반 요약 사용

`config/integration-api.env`에 설치된 Audiveris 실행 파일 경로를 적는다.

```text
MUSIC_RECOGNITION_ENABLED=true
MUSIC_MODEL_ROOT=daisy-music
AUDIVERIS_CMD=C:\Program Files\Audiveris\bin\Audiveris.bat
AUDIVERIS_TIMEOUT=600
```

실제 설치 경로가 다르면 `AUDIVERIS_CMD`만 수정한다. 이 값은 API 키는
아니지만 PC마다 다르므로 실제 로컬 설정 파일에만 둔다.

## 상태 확인

로컬 API 실행 후 `GET http://localhost:8000/health`의 `music` 값을 확인한다.

- `available: true`: Audiveris 실행 경로 확인 완료
- `available: false`: `message`에 모델 폴더 또는 Audiveris 설정 오류 표시

Audiveris가 없거나 특정 악보 인식이 실패해도 PDF Job 전체를 실패시키지 않는다.
해당 영역을 `music` 및 `needs_review`로 남기고 악보 상세 화면에 원인과 재설정
안내를 표시한다.

## 2026-09-16 진행 상태

| 단계 | 상태 | 확인 내용 |
| --- | --- | --- |
| 테스트 PDF 입력 | 완료 | `ocr_test_sample.pdf` 3페이지 처리 확인 |
| 악보 페이지 판별 | 완료 | `악보`, `Sheet Music` 문맥 확인 |
| 악보 영역 검출 | 완료 | 가장 큰 Picture 영역이 `music`으로 승격됨 |
| 모델 호출 어댑터 | 완료 | 잘라낸 PNG가 `daisy-music/services/music_recognizer.py`로 전달됨 |
| Python 악보 파서 | 완료 | `music21`을 루트 의존성에 추가하고 기존 `.mxl` 샘플 파싱 성공 |
| MusicXML 후처리 | 확인 | 제공 샘플에서 4/4박자, 12마디, 이벤트 40개 확인 |
| 앱 결과 표시 | 완료 | Music 블록, 좌표, 신뢰도, 결과 또는 실행 오류를 악보 상세 화면에 표시 |
| 부분 실패 처리 | 완료 | 악보 모델 실패 시에도 PDF Job과 앱이 종료되지 않고 `NeedsReview` 유지 |
| 신규 악보 Audiveris 실행 | 대기 | 현재 개발 PC에 Java와 Audiveris가 없음 |
| 점자악보·DAISY 출력 | 미구현 | `brailleMusic`, DAISY 출력은 모델 응답에서도 아직 `null` |

검증 결과는 Python 자동 테스트 9건 통과, WPF Debug 빌드 경고 0개·오류
0개다. 로컬 OCR API와 Windows 앱의 동시 실행도 확인했다.

## 현재 화면에 표시되는 오류의 의미

다음 메시지는 PDF나 악보 영역 검출 실패가 아니다.

```text
악보 영역을 찾았지만 악보 인식기를 실행하지 못했습니다.
Audiveris와 AUDIVERIS_CMD 설정을 확인한 뒤 다시 분석하세요.
```

처리는 서로 다른 두 단계다.

```text
1. DocLayout-YOLO: 페이지에서 악보가 있는 위치를 찾음        -> 성공
2. Audiveris OMR: 음표·마디를 해석하여 MusicXML을 생성함     -> 실행 환경 없음
```

따라서 원본 화면에 악보 박스가 정확히 그려져도 인식 결과에는 위 오류가 나올
수 있다. 앱의 `NeedsReview` 상태는 이 부분 실패를 사용자에게 숨기지 않기 위한
정상 동작이다. 가짜 음표나 기존 샘플 결과로 성공을 꾸미지 않는다.

## 오류·조치 기록

### `Audiveris 실행 파일을 찾을 수 없습니다`

- 발생 위치: 악보 상세 화면 및 `/health`의 `music.message`
- 원인: Java/Audiveris가 설치되지 않았거나 `AUDIVERIS_CMD`가 실제 실행 파일을
  가리키지 않음
- 현재 개발 PC 상태: Java 명령과 Audiveris 실행 파일 모두 확인되지 않음
- 영향: 일반 OCR·레이아웃·검수 패키지는 정상이며 악보 내용 변환만 실패
- 처리: Music 블록에 오류를 기록하고 `NeedsReview`로 유지
- 해결: Java와 Audiveris 설치 후 `AUDIVERIS_CMD` 설정, 로컬 API 재시작,
  `/health`에서 `music.available: true` 확인

### `music.available: false`

- 의미: 악보 연결 코드는 활성화됐지만 실행 가능한 Audiveris를 찾지 못함
- 확인 위치: `GET http://localhost:8000/health`
- 모델 폴더가 없을 때도 같은 값이 나오므로 `message`와 `model_root`를 함께 확인

### `ModuleNotFoundError: No module named 'daisy_ocr'`

- 발생 시점: 개발 테스트 도구가 한글 경로의 편집형 `.pth`를 만든 뒤 로컬 API를
  `-SkipSync`로 시작했을 때
- 원인: 한글 프로젝트 경로와 편집형 Python 설치 방식의 호환 문제
- 조치 완료: 편집 링크를 제거하고 일반 wheel 방식으로 다시 설치함
- 복구 명령:

```powershell
uv sync --no-dev --no-editable --reinstall-package daisy-ocr
```

- 예방: 평소에는 `scripts/start-local-ocr.ps1`을 사용한다. 이 스크립트가
  `--no-editable` 일반 wheel 설치를 적용한다.

### `music21` 모듈 없음

- 최초 상태: 모델팀 폴더의 `requirements.txt`에는 있었지만 루트 OCR 환경에는
  포함되지 않아 같은 프로세스에서 사용할 수 없었음
- 조치 완료: 루트 `pyproject.toml`과 `uv.lock`에 `music21`, `requests` 추가
- 확인: 제공된 `OCR_Test01_screen_normal.mxl` 파싱 성공

### 로컬 LLM/Ollama 미실행

- 영향: Audiveris·MusicXML 핵심 처리 실패로 보지 않음
- 처리: 모델팀 코드가 규칙 기반 deterministic summary로 대체 가능
- 필수 여부: 현재 시연의 필수 설치 대상은 Java와 Audiveris이며 Ollama는 선택

## 재시도 확인 순서

1. Java와 Audiveris를 설치한다.
2. `config/integration-api.env`의 `AUDIVERIS_CMD`를 실제 파일 경로로 바꾼다.
3. 기존 로컬 API 프로세스를 종료하고 `scripts/start-local-ocr.ps1`로 다시 시작한다.
4. `/health`의 `music.available`이 `true`인지 확인한다.
5. Windows 앱에서 `ocr_test_sample.pdf` 전체 또는 3페이지만 다시 분석한다.
6. 악보 상세 화면에서 오류 문구 대신 악보 요약과 `[악보 시작]` 마디별 읽기가
   표시되는지 확인한다.

## 결과와 제한

- 앱 표시: 요약, 마디별 스크린리더용 읽기, 검수 사유, 평균 신뢰도
- 모델 내부 산출물: MusicXML 문자열, `.mxl`, `.omr`, 분석 JSON
- 아직 미구현: MusicXML 파일 다운로드, 점자악보 변환, 최종 DAISY 패키지 삽입
- 악보 모델의 `needsReview`가 참이면 검수 상태를 완료로 자동 확정하지 않는다.
- Audiveris 입력·실행 파일은 OCR Job 임시 폴더에 두고, 모델팀 파이프라인이
  만드는 `*_output` 작업 폴더도 `.gitignore`로 제외한다.

현재 개발 PC 확인 결과 Python 연결과 `music21` 설치는 완료되었지만 Java와
Audiveris는 설치되어 있지 않다. 따라서 실제 신규 악보 OMR 시연 전에는 위 두
프로그램을 설치하고 `AUDIVERIS_CMD`를 채워야 한다.
