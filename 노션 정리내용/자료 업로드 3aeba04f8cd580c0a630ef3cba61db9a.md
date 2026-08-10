# 자료 업로드

카테고리: 문서 관리
설명: PDF 및 스캔 이미지를 업로드하고 AI 파이프라인 처리를 시작합니다 (F1, F14). 
Method: POST
URL: /documents/upload
param: file (form-data)
사용자: 공통

### Request

| key | 설명 | value 타입 | 옵션 | Nullable | 예시 |
| --- | --- | --- | --- | --- | --- |
| `file` | 업로드할 원본 문서 파일 | `File` | .pdf, .jpg, .png 등 | N | `(Binary Data)` |

### Response

| key | 설명 | value 타입 | 옵션 | Nullable | 예시 |
| --- | --- | --- | --- | --- | --- |
| `documentId` | 서버에 생성된 문서의 고유 ID | `String` |  | N | `doc_998877` |
| `fileName` | 업로드된 원본 파일명 | `String` |  | N | `science_book.pdf` |
| `status` | 현재 AI 파이프라인 처리 상태 | `String` | PROCESSING, AI_DRAFT | N | `PROCESSING` |
| `message` | 상태 안내 메시지 | `String` |  | N | `AI 초안이 생성 중입니다.` |

**Example**

```jsx
{
  "documentId": "doc_998877",
  "fileName": "science_book.pdf",
  "status": "PROCESSING",
  "message": "AI 초안이 생성 중입니다."
}
```

### Status

| status | response content |
| --- | --- |
| 201 | 정상 업로드 및 파이프라인 시작 |
| 400 | {errorCode: REQ_02, message: 지원하지 않는 파일 형식이거나 용량을 초과했습니다.} |
| 401 | {errorCode: AUTH_01, message: 로그인이 필요합니다.} |