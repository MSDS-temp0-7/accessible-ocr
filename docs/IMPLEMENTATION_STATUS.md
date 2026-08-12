# 구현 진행 현황

최종 갱신: 2026-08-12

## 현재 단계

Windows WPF 앱은 PDF 선택, 가져오기 설정, 통합 OCR Job 요청·상태 조회, 결과 ZIP(`book.xml` + `review.json`) 파싱, 검수 화면 전달까지 구현되어 있다.

로그인 화면, HTTP 로그인 요청, 메모리 토큰 세션, 역할별 클라이언트 권한 골격도 구현되어 있다. 회원가입 화면은 입력·형식 검증까지만 구현되어 있으며 서버 또는 DB에 저장하지 않는다. 인증 서버와 DB가 아직 없으므로 실제 계정 로그인·가입은 성공할 수 없으며 Debug 빌드에서만 명시적인 개발 미리보기 진입을 제공한다.

현재 실제 CLOVA OCR Invoke URL과 `X-OCR-SECRET`, 모델팀 API 주소·키는 발급 전이다. 따라서 앱 UI와 통합 API 클라이언트 구조는 실행되지만 실제 OCR 처리는 아직 성공할 수 없다.

## 확정한 처리 구조

```text
AccessibleOcr.exe
  -> 우리 통합 API
      -> CLOVA OCR: 일반 텍스트, 좌표, 신뢰도
      -> 모델팀 API: 문서 구조, 표, 수식, 악보 등
      -> 결과 통합: book.xml + review.json
  <- 검수 결과 패키지
```

- Windows EXE에는 CLOVA 또는 모델팀의 비밀 키를 넣지 않는다.
- EXE의 `appsettings.Local.json`에는 우리 통합 API 주소만 넣는다.
- CLOVA와 모델팀 키는 통합 서버의 환경변수로만 관리한다.

## 키 발급 전 임시 설정

저장소의 `config/integration-api.env.example`에는 실제 비밀이 아닌 다음 표식이 들어 있다.

```text
CLOVA_OCR_INVOKE_URL=REPLACE_WITH_REAL_CLOVA_OCR_INVOKE_URL
CLOVA_OCR_SECRET=REPLACE_WITH_REAL_CLOVA_OCR_SECRET
MODEL_API_URL=REPLACE_WITH_REAL_MODEL_API_URL
MODEL_API_KEY=REPLACE_WITH_REAL_MODEL_API_KEY
```

현재 개발 PC에는 Git에서 제외되는 `config/integration-api.env`도 같은 표식으로 생성되어 있다. 실제 값이 발급되면 `=` 오른쪽의 `REPLACE_WITH_...` 부분만 교체한다.

예시:

```text
CLOVA_OCR_SECRET=실제로_발급받은_키
```

JSON은 표준상 주석을 허용하지 않기 때문에 키 교체 설명은 `.env` 파일의 `#` 주석과 이 문서에서 관리한다.

## 아직 구현되지 않은 부분

1. ASP.NET Core 통합 API 프로젝트
2. CLOVA OCR 실제 호출과 응답 변환
3. 모델팀 API 실제 호출과 응답 변환
4. 두 결과의 좌표·읽기 순서 병합
5. DB와 원본/결과 파일 저장소
6. 실키 적용 후 PDF 통합 테스트
7. 사용자 DB, 토큰 갱신, 자원봉사자 본인인증, 서버 측 권한 검사

## 로그인·권한 골격

- 로그인 API 가정: `POST /auth/login`
- 요청: `email`, `password`
- 응답: `accessToken`, `refreshToken`, `user.userId`, `user.role`
- 역할: `READER`, `INSPECTOR`, `VOLUNTEER`
- 토큰은 현재 메모리에만 유지하며 로그아웃 시 제거한다.
- `INSPECTOR`: 업로드·검수·내보내기 UI 허용
- `VOLUNTEER`: 검수 UI 허용, 업로드·내보내기 비활성화
- `READER`: 현재 제작·검수 기능 비활성화
- 회원가입 선택 역할: `READER`, `VOLUNTEER`. `INSPECTOR`는 관리자 부여 예정

위 권한은 화면 골격을 위한 클라이언트 제어다. 실제 보안은 통합 서버가 모든 API 요청마다 토큰과 역할을 다시 확인해야 한다.

회원가입 API 경로는 기존 명세에 없어 임의로 만들지 않았다. 향후 계약과 DB 연결 지점은 `docs/AUTHENTICATION_INTEGRATION.md`를 따른다.

## 다음 작업 시작 조건

- CLOVA OCR Invoke URL과 Secret 발급
- 모델팀 API 입력·출력·인증 명세 확정
- 통합 서버 배포 위치와 DB/파일 저장소 결정

실제 키를 채운 뒤에도 키 자체는 이 문서, 코드, 커밋 메시지, 이슈 또는 채팅에 복사하지 않는다.
