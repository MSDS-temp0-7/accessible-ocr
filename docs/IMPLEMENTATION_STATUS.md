# 구현 진행 현황

최종 갱신: 2026-09-02

## 현재 단계

PDF를 선택한 WPF 앱이 같은 PC의 Python FastAPI 서버에 비동기 작업을
요청하고, 서버가 CLOVA OCR과 DocLayout-YOLO를 실행한 뒤
`book.xml + review.json` ZIP을 반환하는 실제 연결 단계까지 구현됐다.

로컬 API는 DB 없이 작업 상태와 검수 수정을 메모리에 보관한다. 로그인과
회원가입은 화면·클라이언트 골격만 있으며 Debug의 개발 미리보기로 OCR
시연을 진행한다.

## 구현 완료

| 영역 | 현재 구현 |
| --- | --- |
| Windows 앱 | WPF/.NET 8, PDF 선택, 가져오기 옵션, 진행률, 실제 결과 검수 화면, UI 예외 안내·로그 |
| 로컬 API | FastAPI, Job 생성·조회·결과 ZIP·검수 PATCH |
| 일반 OCR | CLOVA General OCR 실제 HTTP 호출, 글자·좌표·신뢰도 변환 |
| 레이아웃 | DocLayout-YOLO 실제 추론, 표·수식·그림 영역 분류와 중복 제거 |
| 병합 | OCR과 특수 영역의 중복 제거, 간이 읽기 순서 정렬 |
| 결과 | 기본 DTBook `book.xml`, 픽셀 좌표·신뢰도·검수 상태 `review.json` |
| 설정 | 실제 키는 Git 제외 파일 `config/integration-api.env`에서만 읽음 |
| 검증 | Python wheel 빌드, 결과 패키지 테스트 2건, API health, 모델 추론, WPF Debug 빌드 통과 |

검수 화면의 예시 수식·신뢰도·문서 내용은 제거됐다. PDF 분석 결과가 없으면
실제 객체나 검수 건수가 표시되지 않으며, 결과 수신 후에만 텍스트·유형·좌표가
표시된다.

예상치 못한 UI 예외는 앱을 즉시 종료하지 않고 안내창을 표시하며
`%LOCALAPPDATA%\AccessibleOcr\logs\app-errors.log`에 기록한다. 분석 진행률은
읽기 전용 ViewModel 값이므로 `OneWay` 바인딩을 사용한다.

## 실행 구조

```text
AccessibleOcr.Desktop.exe
  -> http://localhost:8000 (daisy_ocr.server)
      -> CLOVA OCR: 페이지 일반 글자, 좌표, 신뢰도
      -> DocLayout-YOLO: 표, 수식, 그림 영역
      -> 병합 및 ZIP 생성: book.xml + review.json
  <- 실제 검수 결과
```

현재 로컬 API는 앱과 같은 PC에서 별도 PowerShell 프로세스로 실행한다.
이는 외부 서버나 DB가 아니라 로컬 보조 프로세스다. CLOVA 호출만 인터넷을
통해 네이버 클라우드로 나간다.

## CLOVA 키 적용

공유 파일 `config/integration-api.env.example`을
`config/integration-api.env`로 복사하고 다음 두 값의 오른쪽만 교체한다.

```text
CLOVA_OCR_INVOKE_URL=실제_Invoke_URL
CLOVA_OCR_SECRET=실제_Secret
```

현재 개발 PC의 두 값은 아직 실제 값으로 설정되지 않았다. 값 자체는 코드,
문서, Git, 채팅, 화면 녹화에 남기지 않는다.

## 실제 구현이지만 제한된 부분

- 특수 영역의 위치는 실제 모델이 검출한다.
- 표 셀 구조, 수식 MathML, 그래프 설명, 악보 변환 모델은 아직 연결되지 않았다.
- 따라서 특수 영역 내용은 전용 모델 연결 대기 안내와 해당 영역에서 CLOVA가 읽은 글자를 담고 `needs_review`로 표시한다.
- DTBook은 현재 읽기 순서의 기본 `<p>` 요소를 만드는 1차 패키지다. 제목·목록·표·MathML의 완전한 구조화는 후속이다.
- 검수 PATCH는 메모리 수신만 하며 API 재시작 시 사라진다.

## 아직 구현되지 않은 부분

1. 사용자 DB, 실제 로그인·회원가입, JWT 갱신과 서버 권한 검사
2. 작업·문서·검수 이력의 영구 DB 저장
3. 원본 PDF/결과 파일의 영구 저장소
4. 원본 페이지 이미지 위 실제 좌표 박스 오버레이
5. 모델팀의 표·수식·그래프·악보 전용 결과 연결
6. 구조화 DOCX, 접근 가능한 HTML, 완성 DAISY 내보내기
7. 설치 프로그램에서 Python 런타임과 로컬 API를 함께 배포·자동 실행하는 방식

## 다음 작업 우선순위

1. CLOVA 실제 키를 로컬 설정에 넣고 1~3페이지 테스트 PDF로 화면 녹화
2. 모델팀의 전용 변환 입출력 계약을 `TranscribedRegion` 어댑터에 연결
3. PDF 페이지 이미지 전달 및 검수 화면 좌표 오버레이
4. SQLite 기반 문서·검수 임시 저장 또는 중앙 DB 구조 결정
5. 인증 서버와 사용자 DB 구현

상세 실행 순서는 `docs/LOCAL_OCR_DEMO.md`를 따른다.
