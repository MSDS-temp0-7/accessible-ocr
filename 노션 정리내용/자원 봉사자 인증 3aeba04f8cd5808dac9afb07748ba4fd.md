# 자원 봉사자 인증

카테고리: 인증
설명: 봉사자 큐 접근 전 본인인증을 수행합니다 (F15, Step V1). 
Method: POST
URL: /auth/verify
param: verificationData
사용자: 공통

### Request

| key | 설명 | value 타입 | 옵션 | Nullable | 예시 |
| --- | --- | --- | --- | --- | --- |
| `verificationData` | 본인인증 데이터 객체 | `Object` |  | N | `{"provider":...}` |
| `verificationData.provider` | 인증 제공자 (PASS, 카카오 등) | `String` | PASS, KAKAO, NAVER | N | `"PASS"` |
| `verificationData.token` | 본인인증 결과 토큰/코드 | `String` |  | N | `"auth_token_string"` |

### Response

| key | 설명 | value 타입 | 옵션 | Nullable | 예시 |
| --- | --- | --- | --- | --- | --- |
| `isVerified` | 인증 성공 여부 | `Boolean` |  | N | `true` |
| `verifiedAt` | 인증 완료 일시 | `String` | ISO 8601 포맷 | N | `"2026-07-31T21:00:00Z"` |

**Example**

```jsx
{
  "isVerified": true,
  "verifiedAt": "2026-07-31T21:00:00Z"
}
```

### Status

| status | response content |
| --- | --- |
| 200 | 본인인증 성공 |
| 400 | {errorCode: AUTH_05, message: 본인인증 정보가 유효하지 않습니다.} |
| 401 | {errorCode: AUTH_01, message: 로그인이 필요합니다.} |