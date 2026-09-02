# 실제 PDF OCR 시연 실행 방법

최종 갱신: 2026-09-03

이 문서는 한 대의 Windows PC에서 WPF 앱, 로컬 Python API, CLOVA OCR,
DocLayout-YOLO를 연결하여 PDF 시연을 실행하는 절차다. DB나 로그인 서버는
필요하지 않으며 Debug 빌드의 `개발 미리보기로 열기`를 사용한다.

## 1. 최초 준비

필요한 프로그램:

- Visual Studio 2022의 `.NET 데스크톱 개발` 워크로드
- .NET 8 SDK
- Python 패키지 실행 도구 `uv`
- CLOVA OCR Invoke URL과 Secret

`config/integration-api.env.example`을 같은 폴더의
`integration-api.env`로 복사하고 아래 두 값의 오른쪽만 실제 발급값으로
교체한다.

```text
CLOVA_OCR_INVOKE_URL=실제_Invoke_URL
CLOVA_OCR_SECRET=실제_Secret
```

`integration-api.env`는 Git에서 제외된다. 키를 코드, 문서, 커밋, 이슈,
채팅 또는 화면 녹화에 노출하지 않는다.

## 2. 로컬 OCR API 실행

저장소 루트에서 PowerShell을 열고 다음을 실행한다.

```powershell
.\scripts\start-local-ocr.ps1
```

스크립트는 필요한 Python 3.11 환경을 설치하고
`http://localhost:8000`에서 API를 시작한다. `Application startup complete`
메시지가 보이면 그 PowerShell 창을 켜 둔다. 이 창을 닫으면 API도 종료된다.

첫 PDF 분석에서는 DocLayout-YOLO 가중치를 한 번 내려받을 수 있어 이후
실행보다 오래 걸린다. CLOVA OCR은 페이지마다 외부 API를 호출하므로 발급
계정의 과금·호출 한도를 확인한다.

## 3. Windows 앱 실행

1. Visual Studio에서 `AccessibleOcr.sln`을 연다.
2. 시작 프로젝트가 `AccessibleOcr.Desktop`인지 확인한다.
3. 구성은 `Debug`, 플랫폼은 `Any CPU`로 두고 `F5`를 누른다.
4. 로그인 화면에서 `개발 미리보기로 열기`를 누른다.
5. 홈에서 PDF를 선택한다.
6. 가져오기 설정을 확인하고 분석 화면으로 이동한다.
7. `분석 시작`을 누르고 완료될 때까지 기다린다.
8. 검수 작업공간에서 실제 OCR 요소, 신뢰도, 좌표와 텍스트를 확인한다.
9. 왼쪽에서 페이지를 고르고, 객체 목록 또는 중앙 페이지의 색상 박스를 선택해
   같은 객체가 오른쪽 검사 패널에 연결되는지 확인한다.

분석 중 `새 프로젝트`나 `내보낸 파일` 화면으로 이동해도 처리는 계속된다.
좌측 메뉴 또는 상단의 `진행 중 작업 · n%` 버튼을 누르면 같은 분석 화면으로
돌아간다. 작업 중에는 새 PDF 선택과 분석 중복 시작이 비활성화된다.

## 4. 현재 시연에서 실제로 동작하는 것

- PDF 페이지 이미지 렌더링
- CLOVA OCR 일반 글자·좌표·신뢰도 추출
- DocLayout-YOLO 표·수식·그림 영역 검출
- OCR 조각과 비텍스트 영역의 중복 제거 및 읽기 순서 병합
- `book.xml`과 `review.json` ZIP 생성
- WPF 분석 진행률, 객체 수, 검수 목록, 실제 인식 텍스트 표시
- 페이지·객체 목록 스크롤과 실제 PDF 페이지 이미지 표시
- 글·표·그림·수식·악보 검출 영역의 유형별 좌표 박스 및 선택 연동
- 검수 수정 요청의 로컬 메모리 수신

## 5. 아직 시연용 제한인 것

- 표 셀 구조, 수식 MathML, 그래프 설명, 악보 변환 전용 모델은 아직 연결되지 않았다.
- 특수 영역은 실제 위치를 검출하지만, 내용에는 `전용 모델 연결 전 검수 필요` 안내와 해당 영역에서 CLOVA가 읽은 글자만 들어간다.
- 오버레이 확대·축소, 페이지 맞춤, 유형별 표시 필터는 아직 없다.
- 검수 수정은 서버 메모리에만 남고 API 종료 시 사라진다.
- 화면 이동 중 작업은 유지되지만 앱이나 로컬 API를 종료한 뒤에는 복구되지 않는다.
- 로그인·회원가입은 UI 골격이며 실제 사용자 DB와 인증 서버가 없다.
- DOCX/HTML/DAISY 완성본 내보내기는 아직 없다.

## 문제 확인

- 앱에 `연결할 수 없음`이 표시되면 로컬 API PowerShell 창이 실행 중인지 확인한다.
- CLOVA 관련 오류면 `integration-api.env`의 URL과 Secret을 다시 확인한다.
- 시연 중에는 Secret이 보일 수 있는 설정 파일이나 터미널 명령을 화면에 띄우지 않는다.
- Python 환경을 다시 만들 때도 시작 스크립트를 사용한다. 한글 프로젝트 경로 호환을 위해 일반 wheel 설치 방식이 적용돼 있다.
