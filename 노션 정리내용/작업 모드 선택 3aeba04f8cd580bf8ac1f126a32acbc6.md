# 작업 모드 선택

카테고리: 인증
설명: 사용자가 리더/검수자 중 어떤 모드로 진입할지 선택합니다 (F13).  
Method: POST
URL: /auth/mode
param: mode (READER/INSPECTOR)
사용자: 공통

### Request

| key | 설명 | value 타입 | 옵션 | Nullable | 예시 |
| --- | --- | --- | --- | --- | --- |
| `mode` | 진입할 작업 모드 | `String` | READER, INSPECTOR, VOLUNTEER | N | `"READER"` |

### Response

| key | 설명 | value 타입 | 옵션 | Nullable | 예시 |
| --- | --- | --- | --- | --- | --- |
| `isAuthorized` | 권한 확인 결과 | `Boolean` |  | N | `true` |
| `redirectPath` | 이동할 프론트엔드 라우팅 경로 | `String` |  | N | `"/reader/dashboard"` |

**Example**

```jsx
{
  "isAuthorized": true,
  "redirectPath": "/reader/dashboard"
}
```

### Status

| status | response content |
| --- | --- |
| 200 | 정상 모드 선택 완료 |
| 401 | {"errorCode": "AUTH_01", "message": "로그인이 필요합니다."} |
| 403 | {"errorCode": "AUTH_03", "message": "해당 모드에 접근할 권한이 없습니다(예: 미인증 자원봉사자)."} |