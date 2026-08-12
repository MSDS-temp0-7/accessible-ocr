# OCR 파이프라인 연동 계약

## 앱의 책임

WPF 앱은 OCR 모델을 직접 실행하지 않는다. 사용자가 선택한 멀티페이지 PDF를 OCR API에 업로드하고, 비동기 Job 상태를 조회한 뒤 결과 패키지를 검수 UI로 표시한다.

통합 서버는 CLOVA OCR로 일반 텍스트·좌표·신뢰도를 얻고, 모델팀 API로 문서 구조와 특수 객체를 얻어 하나의 결과 패키지로 결합한다. CLOVA의 Invoke URL과 `X-OCR-SECRET`은 서버 환경변수에만 둔다.

```text
PDF 선택
  -> POST /api/v1/jobs (multipart: file, options)
  <- { job_id, status: queued }
  -> GET /api/v1/jobs/{job_id}
  <- { status: processing | done | failed, progress?, message? }
  -> GET /api/v1/jobs/{job_id}/result
  <- application/zip 또는 { result_url }
  -> ZIP: book.xml + review.json
```

경로는 `IO-SPEC_OCR-Layout-Formula_v0.2.md`의 비동기 Job 제안을 앱에서 실행 가능한 기본값으로 옮긴 것이다. 모델팀이 실제 OpenAPI를 제공하면 `src/AccessibleOcr.Desktop/appsettings.json`과 `HttpDocumentService`만 우선 맞춘다.

## 결과 패키지

| 파일 | 책임 | 앱 사용처 |
| --- | --- | --- |
| `book.xml` | DAISY3 DTBook 구조와 판독 순서 | 문단·표·수식·이미지의 내용과 요소 ID |
| `review.json` | 신뢰도, 페이지, 픽셀 좌표, 영역 이미지 참조 | 원본 하이라이트, 저신뢰 큐, 커서 동기화 |

- 요소 연결 키: DTBook의 `id` = `review.json.elements`의 키
- 좌표: `page_index`는 0-based, `bbox`는 `[x, y, w, h]` 픽셀
- 신뢰도: 엔진은 raw `0.0~1.0`만 제공한다. 색상 임계값은 UI 책임이다.
- 읽기 순서: DTBook 문서 순서가 기준이며 별도 순서 번호를 만들지 않는다.

## 현재 앱 구현

- 실제 Windows PDF 선택: `WindowsFilePicker`
- HTTP 업로드·폴링·결과 다운로드: `HttpDocumentService`
- ZIP 파싱: `OcrPackageReader`
- DTBook 요소 ID와 `review.json`을 `ReviewBlock`으로 결합
- 검수 수정 저장: `PATCH` 경로를 설정 파일에서 관리

## 모델팀 확인 필요 항목

1. Job 생성·상태·결과 API의 실제 경로와 응답 JSON
2. 인증 방식과 요청 헤더
3. 결과 ZIP 직접 반환 여부 또는 `result_url` 반환 여부
4. 부분 실패를 `review.json` 요소별 `error`로 표현하는 방식
5. 검수 수정·revision 저장 API의 최종 경로와 DTO
6. 원본 페이지 이미지와 `region_ref`를 내려받는 URL/권한 방식

## 로컬 비밀 설정

- 공유 표본: `config/integration-api.env.example`
- 실제 로컬 값: `config/integration-api.env` (`.gitignore` 적용)
- 교체 표식: `REPLACE_WITH_REAL_CLOVA_OCR_SECRET` 등
- WPF 설정의 `OcrApi.BaseUrl`은 CLOVA 주소가 아니라 우리 통합 서버 주소다.
