# AI 작업 컨텍스트: Accessible OCR

## 설계 권한과 목표

- 최우선 설계 자료: `Windows_네이티브_접근형_OCR_화면설계서_v0.1.docx`
- 보조 초기 시안: `접근형 OCR 앱_WF-01~04.png`
- 제품: OCR 결과를 접근 가능한 구조로 만들고 검수·내보내기하는 Windows 네이티브 앱
- 플랫폼/UI: Windows 10/11, WPF, .NET 8, XAML, MVVM
- 현재 단계: 실제 PDF 선택과 HTTP OCR Job 연동을 구현한 통합 단계
- OCR I/O 기준: 루트의 `IO-SPEC_OCR-Layout-Formula_v0.2.md`

Word 화면설계서와 기존 API 메모가 충돌하면, 화면·MVP 범위·접근성은 Word 설계서를 우선하고 API 메모는 구현 전 정리 대상으로 취급한다.

## 제품 경계

- MVP 입력: PDF, 이미지, DOCX, HWP
- MVP 출력: 구조화 DOCX, 접근 가능한 HTML, 검수 보고서
- 후속/연동 출력: DAISY, HWP 직접 생성, 음성 파일, 점자악보
- 앱은 모델을 직접 실행하지 않는다. 로컬 개발에서는 `localhost` OCR API를, 운영에서는 서버 API를 사용한다.
- 결과 계약: DAISY3 DTBook `book.xml` + 검수 사이드카 `review.json`.
- AI 결과: 확정값이 아닌 제안. 원문, AI 제안, 사용자 수정, 검수 상태를 분리해 보인다.
- 초기 상태에는 샘플 문서나 임의 객체 수를 만들지 않는다. 검수·내보내기 요약은 실제 `book.xml`/`review.json` 결과를 읽은 뒤에만 생성한다.

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
- 특수 객체의 기본 읽기는 개요다. Enter로 상세에 들어가고 Esc로 개요에 돌아온다.
- 미확인 항목이 있어도 내보내기는 가능하며 결과·검수 보고서에 상태를 남긴다.

## 코드 경계

- `Views`: XAML과 최소한의 UI 코드비하인드
- `ViewModels`: 화면 상태, 명령, 유효성, 라이브 상태 문구
- `Models`: UI 공유 모델과 열거형
- `Services`: Windows 파일 선택, HTTP OCR Job, 결과 패키지 파서, 검수 저장 API
- `Infrastructure`: MVVM 공통 코드

View는 Service를 직접 호출하지 않는다. URL, DTO, 인증 토큰, 파일 시스템 경로는 ViewModel에 하드코딩하지 않는다.

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
5. 외부 의존성 추가 전 이유·라이선스·대체 가능성을 확인한다.
6. `dotnet build AccessibleOcr.sln` 성공을 최소 검증으로 한다.
