# Accessible OCR

접근 가능한 문서 구조를 만들기 위한 Windows WPF OCR 검수 앱입니다. 사용자가 PDF를 선택하면 OCR API의 비동기 Job을 호출하고, 결과 패키지의 DAISY3 DTBook(`book.xml`)와 검수 사이드카(`review.json`)를 검수 화면에 표시합니다.

## 팀원 시작 방법

1. 저장소를 clone한 뒤 `AccessibleOcr.sln`을 Visual Studio 2022에서 엽니다.
2. .NET 8 SDK와 Visual Studio의 **.NET 데스크톱 개발** 워크로드가 설치되어 있는지 확인합니다.
3. `src/AccessibleOcr.Desktop/appsettings.Local.json.example`을 같은 폴더에 `appsettings.Local.json`으로 복사합니다.
4. `BaseUrl`을 개발용 OCR API 주소로 바꿉니다. 토큰·비밀번호 등 개인 값은 이 파일에만 두고 커밋하지 않습니다.
5. Visual Studio에서 `F5`를 눌러 실행합니다.

앱은 로그인 화면에서 시작합니다. 인증 서버가 아직 없다면 Debug 빌드에서만 표시되는 `개발 미리보기로 열기`로 UI를 확인할 수 있습니다. 이 기능은 실제 로그인이나 서버 권한 검사를 대신하지 않으며 Release 빌드에서는 표시되지 않습니다.

`appsettings.Local.json`은 `.gitignore`에 포함되어 있으므로 GitHub에 올라가지 않습니다. 공용 기본값은 `appsettings.json`에서 관리합니다.

## 문서 안내

- [개발 방향](docs/DEVELOPMENT_DIRECTION.md): 제품 범위, 화면별 진행 상태, 구현 우선순위
- [AI 컨텍스트](docs/AI_CONTEXT.md): AI에게 프로젝트 맥락을 전달할 때 사용하는 요약
- [OCR 파이프라인 연동](docs/OCR_PIPELINE_INTEGRATION.md): Job API, 결과 패키지, 미확정 계약
- [구현 진행 현황](docs/IMPLEMENTATION_STATUS.md): 현재 구현 범위, CLOVA/모델 키 교체 위치, 다음 작업 조건
- [로그인·회원가입·권한 연동](docs/AUTHENTICATION_INTEGRATION.md): 현재 인증 골격과 향후 API·DB 연결 기준
- [OCR/DAISY PRD](OCR-DAISY_PRD_v3.md) 및 [입출력 명세](IO-SPEC_OCR-Layout-Formula_v0.2.md): 모델·파이프라인 측 계약 참고

통합 서버용 CLOVA/모델 API 키는 `config/integration-api.env.example`을 `integration-api.env`로 복사한 뒤 `REPLACE_WITH_...` 값만 교체합니다. 실제 키 파일은 GitHub에 올라가지 않습니다.

AI로 수정 작업을 시작할 때는 `docs/AI_CONTEXT.md`와 관련 기능의 명세 문서를 함께 제공하세요. API 경로·응답 형식을 확정 또는 변경하면 `docs/OCR_PIPELINE_INTEGRATION.md`도 같은 변경에서 갱신합니다.

## Git 작업 원칙

- 기능별 브랜치는 `codex/` 또는 팀에서 합의한 접두어로 만듭니다.
- 빌드 산출물, Visual Studio 개인 설정, `Backup/`, 개인 API 설정은 커밋하지 않습니다.
- 실사용 토큰, 비밀번호, 고객 문서는 어떤 경우에도 커밋하지 않습니다.
- PR에는 코드와 해당 문서 변경을 함께 올리고, Release 빌드 성공 여부를 적습니다.
