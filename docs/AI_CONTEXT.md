# AI 작업 컨텍스트: Accessible OCR

## 설계 권한과 목표

- 최우선 설계 자료: `Windows_네이티브_접근형_OCR_화면설계서_v0.1.docx`
- 보조 초기 시안: `접근형 OCR 앱_WF-01~04.png`
- 제품: OCR 결과를 접근 가능한 구조로 만들고 검수·내보내기하는 Windows 네이티브 앱
- 플랫폼/UI: Windows 10/11, WPF, .NET 8, XAML, MVVM
- 현재 단계: WPF → 로컬 FastAPI → CLOVA OCR + DocLayout-YOLO → 결과 ZIP의 실제 실행 경로 구현
- 인증 단계: 로그인 화면과 HTTP 인증 클라이언트, 회원가입 입력 화면, 메모리 세션, 역할별 UI 권한 골격 구현. 회원가입은 저장하지 않으며 실제 인증 서버와 사용자 DB는 미구현.
- OCR I/O 기준: 루트의 `IO-SPEC_OCR-Layout-Formula_v0.2.md`

Word 화면설계서와 기존 API 메모가 충돌하면, 화면·MVP 범위·접근성은 Word 설계서를 우선하고 API 메모는 구현 전 정리 대상으로 취급한다.

## 제품 경계

- MVP 입력: PDF, 이미지, DOCX, HWP
- MVP 출력: 구조화 DOCX, 접근 가능한 HTML, 검수 보고서
- 후속/연동 출력: DAISY, HWP 직접 생성, 음성 파일, 점자악보
- WPF 프로세스는 모델을 직접 실행하지 않는다. 현재 `localhost:8000`의 Python 보조 프로세스가 모델을 실행하며, 운영 배치 방식은 미정이다.
- 일반 텍스트는 CLOVA OCR이 실제 처리한다. DocLayout-YOLO는 특수 객체 위치를 실제 검출하며 표·수식·그래프·악보의 전용 내용 변환은 모델팀 결과 연결 대기다.
- CLOVA/모델 API의 실제 키는 EXE나 Git 추적 파일에 넣지 않는다. 서버 로컬 설정 위치는 `config/integration-api.env`이며 공유용 표본은 `.example` 파일이다.
- 결과 계약: DAISY3 DTBook `book.xml` + 검수 사이드카 `review.json` + `pages/page-XXXX.jpg` 검수용 페이지 이미지.
- AI 결과: 확정값이 아닌 제안. 원문, AI 제안, 사용자 수정, 검수 상태를 분리해 보인다.
- 초기 상태에는 샘플 문서나 임의 객체 수를 만들지 않는다. 검수·내보내기 요약은 실제 `book.xml`/`review.json` 결과를 읽은 뒤에만 생성한다.
- 검수 화면에 임의 수식·표 내용을 하드코딩하지 않는다. 특수 모델 미연결 상태는 실제 검출 영역에 명시적인 안내와 `needs_review`로 표현한다.
- ViewModel의 private setter/read-only 속성을 `ProgressBar.Value` 등에 연결할 때 `Mode=OneWay`를 명시한다.
- 처리되지 않은 UI 예외는 `App.xaml.cs`가 안내하고 `%LOCALAPPDATA%\AccessibleOcr\logs\app-errors.log`에 기록한다.
- `AnalysisViewModel`은 앱 셸이 공유하는 단일 작업 상태다. 화면 이동만으로
  `Reset()`하거나 새 ViewModel을 만들지 않는다. 실행 중에는 파일 재선택과 중복
  시작을 막고, 셸의 `진행 중 작업` 버튼으로 언제든 같은 분석 화면에 복귀시킨다.
- 현재 작업 유지 범위는 동일 앱 실행 안이다. 프로세스 재시작 후 복구를
  메모리 상태로 흉내 내지 말고 SQLite/서버 저장 설계와 함께 구현한다.

## 현재 로컬 API 코드

- 패키지/실행점: 루트 `pyproject.toml`, `daisy-ocr-api`
- API: `daisy_ocr/server.py`
- CLOVA: `daisy_ocr/ocr/clova_engine.py`
- 레이아웃·병합: `daisy_ocr/layout/`, `daisy_ocr/pipeline.py`
- 결과 직렬화: `daisy_ocr/output/package.py`
- 실행 스크립트: `scripts/start-local-ocr.ps1`
- 시연 절차: `docs/LOCAL_OCR_DEMO.md`

서버 Job과 검수 PATCH는 현재 메모리 저장이며 재시작 시 사라진다. DB와 인증
서버는 없다. CLOVA 키가 없는 환경에서도 API 기동과 health 확인은 가능하지만
PDF Job은 실패 상태가 되어야 하며 가짜 결과로 성공시키지 않는다.

## 화면 흐름

```text
WF-01 Home
  -> WF-02 Import settings
  -> WF-03 Analysis progress
  -> WF-04 Review workspace
      -> WF-05 Table/chart detail
      -> WF-06 Math detail
      -> WF-07 Music detail
  -> WF-08 Review summary/export
```

- 분석이 끝나도 자동으로 WF-04로 이동하지 않는다.
- 분석 중 다른 화면을 열어도 polling을 취소하지 않으며, 셸에서 진행 상태와
  복귀 동작을 항상 제공한다.
- 특수 객체의 기본 읽기는 개요다. Enter로 상세에 들어가고 Esc로 개요에 돌아온다.
- 미확인 항목이 있어도 내보내기는 가능하며 결과·검수 보고서에 상태를 남긴다.

## 코드 경계

- `Views`: XAML과 최소한의 UI 코드비하인드
- `ViewModels`: 화면 상태, 명령, 유효성, 라이브 상태 문구
- `Models`: UI 공유 모델과 열거형
- `Services`: Windows 파일 선택, HTTP OCR Job, 결과 패키지 파서, 검수 저장 API
- `Infrastructure`: MVVM 공통 코드

View는 Service를 직접 호출하지 않는다. URL, DTO, 인증 토큰, 파일 시스템 경로는 ViewModel에 하드코딩하지 않는다.

로그인 역할은 `READER`, `INSPECTOR`, `VOLUNTEER`를 사용한다. 클라이언트의 버튼 비활성화는 편의 기능일 뿐 보안 경계가 아니며, 실제 통합 서버가 모든 요청에서 권한을 검사해야 한다. Debug의 개발 미리보기는 실제 인증으로 취급하지 않는다.

회원가입 화면에서는 `READER`와 `VOLUNTEER`만 신청할 수 있다. `INSPECTOR`는 관리자 부여 대상으로 유지한다. 회원가입 API 명세는 아직 없으므로 임의 경로를 하드코딩하지 말고 `docs/AUTHENTICATION_INTEGRATION.md`의 미확정 항목을 먼저 결정한다.

## 상태와 데이터 규칙

```text
DocumentStatus:
Uploaded -> Processing -> AiDraft -> InReview -> Completed -> Exporting -> ReadyForDownload
                                         \-> ReviewNeeded
                                         \-> Failed

ReviewStatus:
Pending | Reviewed | NeedsReview

BlockType:
Text | Table | Graph | Math | Music | Image
```

- 파이프라인의 `review.json`은 0-based `page_index`와 픽셀 `bbox: [x, y, w, h]`를 제공한다. 화면이 페이지 width/height로 정규화한다.
- 각 `pages[]` 항목의 선택적 `image_ref`는 ZIP 안의 검수용 페이지 JPEG를 가리킨다. WPF는 패키지를 닫기 전에 이미지 bytes를 읽고 `BitmapImage`를 `OnLoad`로 생성·Freeze한다.
- WF-04는 선택 페이지의 객체만 `PageBlocks`에 표시한다. 페이지 목록, 객체 목록, 중앙 오버레이, 오른쪽 검사 패널의 선택 상태를 동기화한다.
- 기존 결과 패키지처럼 `image_ref`가 없을 때 임의 이미지를 만들지 말고, 재분석이 필요하다는 빈 상태를 표시한다.
- WF-02 페이지 범위 UI는 `UseAllPages`, `StartPage`, `EndPage`를 사용한다.
  전체 페이지 선택 시 숫자 입력을 비활성화하고, 유효하지 않은 범위에서는 분석
  명령을 비활성화한다. 명시한 범위를 서버가 임의로 전체 페이지로 대체하면 안 된다.
- 블록 수정 API에는 `revision`을 포함한다.
- UI 문자열은 한국어로 시작하고, 리소스 분리는 후속 작업으로 남긴다.

## 접근성 구현 규칙

- 모든 주요 기능은 키보드만으로 가능해야 한다.
- Tab/Shift+Tab, Enter, Esc, Alt+1~3, Ctrl+F, F6의 설계 의도를 유지한다.
- `AutomationProperties.Name`과 `AutomationProperties.HelpText`는 보이는 라벨과 같은 용어를 사용한다.
- Tree/TreeItem은 문서 개요, Grid/GridItem은 표, Tab/TabItem은 보기 전환에 우선 사용한다.
- 라이브 알림은 진행률, 발견 객체, 오류에 사용하되 반복 이벤트는 합친다.
- 상태는 색상뿐 아니라 텍스트와 UI Automation 상태로 전달한다.
- 오버레이에만 정보를 두지 말고, 접근 가능한 목록·트리·편집기를 함께 제공한다.
- 완료 전 200% 텍스트 확대, 고대비, 포커스 사각형, Narrator 흐름을 확인한다.

## 변경 작업 규칙

1. 먼저 `docs/DEVELOPMENT_DIRECTION.md`와 이 파일을 읽는다.
2. `git status --short`로 기존 변경을 확인하고 덮어쓰지 않는다.
3. 설계 변경은 문서와 코드 모델을 같은 변경 단위에 포함한다.
4. `appsettings.json`의 API 경로는 I/O 정의서에 없는 추정값일 수 있다. 모델팀의 실제 OpenAPI가 오면 `HttpDocumentService` 계약을 우선 수정한다.
5. 실제 비밀 키가 필요한 경우 `config/integration-api.env.example`을 복사한 로컬 파일만 수정한다.
6. 외부 의존성 추가 전 이유·라이선스·대체 가능성을 확인한다.
7. `dotnet build AccessibleOcr.sln` 성공을 최소 검증으로 한다.
8. Python 변경은 `uv build`, 결과 패키지 테스트, 로컬 API `/health`를 함께 확인한다.
9. 한글 경로 호환 때문에 `uv sync --no-editable`을 유지한다. 편집형 `.pth` 설치로 되돌리지 않는다.
