# Word·한글 내보내기

최종 갱신: 2026-09-29

## 현재 지원 범위

WF-08 `검수 완료 / 내보내기` 화면은 실제 OCR 결과가 로드된 경우에만
다음 파일을 저장한다.

| 형식 | 구현 방식 | 외부 API | PC 설치 조건 |
| --- | --- | --- | --- |
| Word `.docx` | WPF 앱이 OOXML ZIP 패키지를 직접 생성 | 없음 | 없음. Word 미설치 PC에서도 생성 가능 |
| 한글 `.hwpx` | 설치된 한/글 COM 자동화로 HWPX 저장 | 없음 | 한컴오피스 한/글 2010 이상 |

구형 바이너리 `.hwp`는 현재 생성하지 않는다. `.hwpx`는 OWPML 기반의
한글 표준 문서이며 단순히 파일 확장자를 바꾼 것이 아니다.

## 사용자 흐름

1. PDF 분석을 완료하고 검수 작업공간에서 내용을 수정·확인한다.
2. `검수·내보내기` 화면으로 이동한다.
3. `Word (.docx)` 또는 `한글 (.hwpx)` 버튼을 누른다.
4. Windows 저장 대화상자에서 위치와 파일명을 선택한다.
5. 완료 메시지에 실제 저장 경로가 표시되는지 확인한다.

미확인 항목이 있어도 저장은 가능하다. `Pending` 또는 `NeedsReview`
블록은 내보낸 파일에 검수 상태 문단을 함께 기록한다.

## 데이터 변환 규칙

- 입력은 화면에 로드된 `OcrDocumentResult`다.
- 블록은 페이지 번호, 세로 좌표, 가로 좌표 순으로 정렬한다.
- 문서 제목과 페이지 제목을 먼저 기록한다.
- 일반 텍스트는 사용자가 수정한 `ReviewBlock.Content`를 기록한다.
- 표·도표·수식·악보·이미지는 유형 이름과 인식 내용을 함께 기록한다.
- 검수 완료가 아닌 블록은 `검수 필요` 또는 `미확인` 상태를 기록한다.
- OCR 서버, CLOVA, Ollama가 종료된 뒤에도 이미 앱에 로드된 결과는 저장할 수 있다.

## 현재 제한

- 표는 셀 구조가 아니라 하나의 인식 문단으로 저장된다.
- 수식은 Word 수식/MathML 객체가 아니라 인식된 텍스트로 저장된다.
- 악보 MusicXML, 원본 페이지 이미지와 검출 박스는 문서에 삽입하지 않는다.
- HWPX에는 한/글 자동화가 필요하므로 배포 PC 설치 조건을 설치 프로그램과
  운영 가이드에 명시해야 한다.
- 텍스트형 DAISY3 ZIP과 HTML 검수 보고서는 별도 버튼으로 구현됐다.
  패키지 구성과 검증 범위는 `docs/DAISY_EXPORT_INTEGRATION.md`를 따른다.
- DOCX/HWPX와 DAISY3 모두 현재 표 셀, MathML, MusicXML과 원본 이미지를
  네이티브 구조로 보존하지 않고 검수된 접근성 설명 텍스트로 기록한다.

## 코드 위치

- 인터페이스: `src/AccessibleOcr.Desktop/Services/IDocumentExporter.cs`
- 구현: `src/AccessibleOcr.Desktop/Services/DocumentExporter.cs`
- 저장 대화상자: `src/AccessibleOcr.Desktop/Services/WindowsFilePicker.cs`
- 화면 상태·명령: `src/AccessibleOcr.Desktop/ViewModels/ExportViewModel.cs`
- 화면: `src/AccessibleOcr.Desktop/Views/ExportView.xaml`

## 검증 기록

2026-09-29 개발 PC에서 한글 본문과 악보 블록이 들어 있는 테스트 결과를
`.docx`와 `.hwpx`로 생성했다.

- DOCX: Microsoft Word에서 열기 성공, 한글 본문 검색 성공
- HWPX: 한컴오피스 한/글 2024에서 열기 성공, 한글 본문 추출 성공
- WPF Debug 빌드: 경고 0개, 오류 0개
