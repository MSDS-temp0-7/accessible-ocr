# Git 추적·제외 파일 안내

최종 갱신: 2026-09-16

이 문서는 저장소를 clone한 팀원이 GitHub에 포함된 파일과 각 개발자 PC에만
남는 파일을 구분하기 위한 기준이다. 실제 비밀값, 사용자 문서, 실행 중간 파일은
Git에 올리지 않는다.

## GitHub에 포함하는 항목

- `src/`: WPF Windows 앱 소스
- `daisy_ocr/`: PDF OCR·레이아웃·결과 패키지 로컬 API
- `daisy_ocr/music/`: `daisy-music` 연결 어댑터
- `daisy-music/api/`, `daisy-music/services/`: 모델팀 악보 API·처리 파이프라인
- `daisy-music/ground_truth/`, `evaluation/`, `variants/`: 제공된 검증 자료
- `daisy-music/audiveris_input/`, `audiveris_output/`: 제공된 대표 입출력 샘플
- `docs/`: 사람용 개발 문서와 AI 컨텍스트
- `config/integration-api.env.example`: 통합 API 환경설정 템플릿
- `daisy-music/**/.env.example`: 악보 API 환경설정 템플릿
- `ocr_test_sample.pdf`: 종단 간 시연용 3페이지 테스트 PDF
- 화면설계서, PRD, I/O 명세와 솔루션·의존성 잠금 파일

공유용 `*.env.example`에는 실제 키나 PC 고유 경로를 넣지 않는다. 예시값과
설명만 커밋한다.

## GitHub에 올라가지 않는 현재 로컬 항목

| 경로·패턴 | 제외 이유 | 팀원이 준비하는 방법 |
| --- | --- | --- |
| `config/integration-api.env` | CLOVA Secret과 PC별 경로 포함 | `.example`을 복사하고 자신의 값 입력 |
| `.env`, `.env.*` | API 키·로컬 환경값 가능 | 필요한 서비스의 `.env.example` 참고 |
| `appsettings.Local.json` | 개발자별 API 주소·설정 | 같은 폴더의 `.example`을 복사 |
| `.venv/` | PC별 Python 가상환경 | `scripts/start-local-ocr.ps1` 실행 |
| `.dotnet-cli/` | 로컬 .NET CLI 상태 | .NET SDK가 자동 생성 |
| `.vs/`, `.idea/` | IDE 사용자 설정 | Visual Studio/IDE가 자동 생성 |
| `bin/`, `obj/`, `dist/` | 빌드·배포 산출물 | 소스에서 다시 빌드 |
| `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/` | Python 캐시 | 실행·테스트 시 자동 생성 |
| `Backup/`, `UpgradeLog.htm` | 로컬 변환·백업 자료 | 업로드하지 않음 |
| `*.db`, `*.db-shm`, `*.db-wal` | 로컬 DB와 임시 트랜잭션 | 향후 마이그레이션으로 생성 |
| `artifacts/`, `tmp/`, `*.log` | 테스트·렌더·로그 | 필요 시 다시 실행 |

## `daisy-music`에서 제외하는 실행 산출물

다음 폴더는 모델 소스가 아니라 API 실행 때 반복 생성되는 업로드·중간·결과
파일이다. 이미지나 악보 원본이 들어올 수 있으므로 Git에 올리지 않는다.

- `daisy-music/api_uploads/`
- `daisy-music/music_api_runs/`
- `daisy-music/music_recognition_runs/`
- `daisy-music/audiveris_runs/`
- `daisy-music/audiveris_auto_test/`
- `daisy-music/parsed_output/`
- `daisy-music/confidence_output/`
- `daisy-music/feature_output/`
- `daisy-music/spoken_output/`
- `daisy-music/summary_output/`
- `daisy-music/pipeline_output/`

제공된 대표 `.mxl`, `.omr`, 평가 JSON과 이미지 샘플 중 위 실행 폴더 밖에 있는
자료는 재현과 모델 검증을 위해 추적한다.

## clone 후 로컬에서 만들어야 하는 파일

```powershell
Copy-Item config\integration-api.env.example config\integration-api.env
Copy-Item src\AccessibleOcr.Desktop\appsettings.Local.json.example `
  src\AccessibleOcr.Desktop\appsettings.Local.json
```

`integration-api.env`에는 CLOVA Invoke URL·Secret을 넣는다. 악보 인식까지
사용할 PC는 Java와 Audiveris를 설치하고 `AUDIVERIS_CMD`도 실제 경로로
교체한다. 이 두 로컬 파일은 `git status`에 나타나지 않는 것이 정상이다.

## 업로드 전 확인

```powershell
git status --short
git status --short --ignored
git diff --check
```

- 실제 키·토큰·비밀번호가 staged 파일에 없는지 확인한다.
- 사용자가 올린 실제 업무 PDF나 API 업로드 파일을 추가하지 않는다.
- `bin`, `obj`, `.venv`, `api_uploads`, 실행 결과 폴더를 `git add -f`로 강제
  추가하지 않는다.
- 새 로컬 전용 경로가 생기면 `.gitignore`와 이 문서를 같은 커밋에서 갱신한다.
