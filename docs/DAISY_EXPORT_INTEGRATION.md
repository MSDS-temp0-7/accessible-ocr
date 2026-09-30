# DAISY3 내보내기

최종 갱신: 2026-09-29

## 현재 구현

WF-08 `검수 완료 / 내보내기` 화면의 `DAISY3 (.zip)` 버튼은 검수 화면에
실제로 로드된 `OcrDocumentResult`를 외부 서버나 API 키 없이 로컬에서
ANSI/NISO Z39.86-2005 계열의 텍스트형 `textNCX` 패키지로 생성한다.
저장한 ZIP과 같은 폴더에는 사용자용 `*-검수보고서.html`도 함께 생성한다.

ZIP 내부 구조:

```text
문서명-DAISY3.zip
  package.opf       패키지 메타데이터, manifest, SMIL spine
  book.xml          DTBook 2005-3 본문과 페이지·객체 ID
  navigation.ncx    페이지 내비게이션
  book.smil         NCX에서 DTBook 본문으로 이어지는 텍스트 참조
문서명-DAISY3-검수보고서.html
```

현재 오디오가 없으므로 패키지 유형은 `textNCX`이고 SMIL에는 `<audio>`가 아닌
DTBook `<text>` 참조만 들어간다. 페이지와 객체는 페이지 번호, 세로 좌표,
가로 좌표 순으로 기록한다. 사용자가 검수 화면에서 수정한 `ReviewBlock.Content`가
본문이 되며, 미확인·검수 필요 항목에는 해당 상태를 읽을 수 있는 접두사를 붙인다.

표·도표·수식·악보·이미지는 현재 각 객체의 검수된 접근성 설명 텍스트로
DTBook에 기록한다. 표 셀 구조, MathML, MusicXML과 원본 이미지를 네이티브
DAISY 리소스로 포함하는 단계는 아직 아니다.

## 앱 내부 기본 검사

파일을 최종 경로로 옮기기 전에 다음을 검사한다.

1. OPF, DTBook, NCX, SMIL 네 파일 존재
2. 각 XML 루트 요소와 네임스페이스
3. OPF manifest가 가리키는 파일과 `id="ncx"` 항목
4. XML 안의 중복 ID
5. NCX → SMIL → DTBook fragment 참조 대상

검사가 실패하면 완성 파일로 교체하지 않고 화면에 오류를 표시한다. 이 검사는
깨진 내부 링크와 누락 파일을 막는 기본 무결성 검사다. 공식 DTD 전체 검증이나
선정한 DAISY 검증기의 표준 적합성 판정과 동일하지 않다.

## HTML 검수 보고서

보고서는 키보드와 스크린리더로 읽을 수 있는 표준 HTML이며 다음을 포함한다.

- 문서 제목과 생성 시각
- 전체 객체 수와 미확인/검수 필요 수
- DAISY 기본 구조 검사 통과 항목
- 객체별 페이지, 유형, 현재 내용, 검수 상태, 신뢰도

사용자 수정 전후 이력, 모델·파이프라인 버전, 상세 오류 목록은 현재
`OcrDocumentResult`에 충분한 이력 데이터가 없어 후속 보강 대상이다.

## 남은 완료 조건

- 선정한 외부 DAISY3/DTD 검증기로 생성물 검증 및 실패 항목 수정
- 실제 DAISY 플레이어 여러 종류에서 페이지 이동·읽기 순서 호환성 시험
- Narrator·NVDA와 키보드만으로 저장 대화상자까지 종단 간 접근성 시험
- 표 셀, MathML, MusicXML, 이미지·대체텍스트의 네이티브 구조 보존
- 필요 시 TTS 오디오와 SMIL 시간 동기화 추가

내부 검사 통과만으로 “완전한 표준 적합성 검증 완료”라고 기록하지 않는다.

## 코드 위치

- 내보내기 계약: `src/AccessibleOcr.Desktop/Services/IDocumentExporter.cs`
- DAISY 패키지·보고서 생성과 기본 검사:
  `src/AccessibleOcr.Desktop/Services/Daisy3Exporter.cs`
- 서비스 진입점: `src/AccessibleOcr.Desktop/Services/DocumentExporter.cs`
- 화면 명령·상태: `src/AccessibleOcr.Desktop/ViewModels/ExportViewModel.cs`
- 화면: `src/AccessibleOcr.Desktop/Views/ExportView.xaml`

## 검증 기록

2026-09-29 개발 PC에서 한글 본문과 수식 설명, 검수 필요 상태가 들어 있는
샘플을 생성해 다음을 확인했다.

- Debug·Release 빌드 경고 0개, 오류 0개
- 기존 OCR·악보 Python 회귀 테스트 20개 통과
- ZIP에 필수 네 파일 존재
- OPF가 기본 OEB package 네임스페이스를 사용하고 NCX manifest ID를 포함
- 앱 내부 필수 파일·루트·manifest·NCX→SMIL→DTBook 참조 검사 통과
- UTF-8 한글 본문과 별도 HTML 검수 보고서 생성

샘플은 `artifacts/daisy-smoke-test/`에 있다. 전용 외부 검증기 결과는 아직
기록하지 않았으므로 이 기록은 기본 구조·내부 참조 스모크 테스트다.
