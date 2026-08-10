# Accessible OCR

접근 가능한 문서 구조를 만들기 위한 Windows WPF OCR 검수 앱입니다. 사용자가 PDF를 선택하면 OCR API의 비동기 Job을 호출하고, 결과 패키지의 DAISY3 DTBook(`book.xml`)와 검수 사이드카(`review.json`)를 검수 화면에 표시합니다.

## 팀원 시작 방법

1. 저장소를 clone한 뒤 `AccessibleOcr.sln`을 Visual Studio 2022에서 엽니다.
2. .NET 8 SDK와 Visual Studio의 **.NET 데스크톱 개발** 워크로드가 설치되어 있는지 확인합니다.
3. `src/AccessibleOcr.Desktop/appsettings.Local.json.example`을 같은 폴더에 `appsettings.Local.json`으로 복사합니다.
4. `BaseUrl`을 개발용 OCR API 주소로 바꿉니다. 토큰·비밀번호 등 개인 값은 이 파일에만 두고 커밋하지 않습니다.
5. Visual Studio에서 `F5`를 눌러 실행합니다.

`appsettings.Local.json`은 `.gitignore`에 포함되어 있으므로 GitHub에 올라가지 않습니다. 공용 기본값은 `appsettings.json`에서 관리합니다.

## 문서 안내

- [개발 방향](docs/DEVELOPMENT_DIRECTION.md): 제품 범위, 화면별 진행 상태, 구현 우선순위
- [AI 컨텍스트](docs/AI_CONTEXT.md): AI에게 프로젝트 맥락을 전달할 때 사용하는 요약
- [OCR 파이프라인 연동](docs/OCR_PIPELINE_INTEGRATION.md): Job API, 결과 패키지, 미확정 계약
- [OCR/DAISY PRD](OCR-DAISY_PRD_v3.md) 및 [입출력 명세](IO-SPEC_OCR-Layout-Formula-v0.2.md): 모델·파이프라인 측 계약 참고

AI로 수정 작업을 시작할 때는 `docs/AI_CONTEXT.md`와 관련 기능의 명세 문서를 함께 제공하세요. API 경로·응답 형식을 확정 또는 변경하면 `docs/OCR_PIPELINE_INTEGRATION.md`도 같은 변경에서 갱신합니다.

## Git 작업 원칙

- 기능별 브랜치는 `codex/` 또는 팀에서 합의한 접두어로 만듭니다.
- 빌드 산출물, Visual Studio 개인 설정, `Backup/`, 개인 API 설정은 커밋하지 않습니다.
- 실사용 토큰, 비밀번호, 고객 문서는 어떤 경우에도 커밋하지 않습니다.
- PR에는 코드와 해당 문서 변경을 함께 올리고, Release 빌드 성공 여부를 적습니다.
