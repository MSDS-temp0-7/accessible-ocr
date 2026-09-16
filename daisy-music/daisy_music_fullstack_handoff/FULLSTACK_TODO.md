# 풀스택팀 연동 시 확인/설정해야 할 항목

이 문서는 코드를 넘겨받은 뒤 풀스택/백엔드 담당자가 실제 환경에 맞게 채워야 하는 값과 결정해야 하는 사항을 정리한 체크리스트입니다.

---

# 1. 반드시 설정할 값

## Audiveris 실행 경로

```text
AUDIVERIS_CMD=/실제/서버/Audiveris/경로
```

확인:

```bash
$AUDIVERIS_CMD -version
```

권장 검증 버전:

```text
5.10.2
```

---

## Ollama 주소

기존 Ollama가 있다면:

```text
OLLAMA_BASE_URL=http://<ollama-host>:11434
```

확인할 모델:

```text
qwen3:8b
```

중요:

프론트가 Ollama를 직접 호출하지 않고 Music API 백엔드만 호출해야 합니다.

---

## 프론트 CORS

실제 프론트 주소로 변경합니다.

```text
CORS_ORIGINS=https://frontend.example.com
```

개발 localhost 값은 운영 배포 전에 정리합니다.

---

# 2. 서버에서 결정할 값

```text
MUSIC_UPLOAD_ROOT
MUSIC_RECOGNITION_ROOT
MAX_MUSIC_UPLOAD_BYTES
AUDIVERIS_TIMEOUT
LOCAL_LLM_TIMEOUT
API PORT
```

---

# 3. API 응답에서 정리할 값

현재 개발 버전은 서버 내부 경로를 일부 반환할 수 있습니다.

```text
outputPath
runDir
artifacts.musicXmlPath
artifacts.omrProjectPath
```

운영 전 선택:

```text
A. 제거
B. 관리자만 반환
C. artifactId로 변경
D. download endpoint로 제공
```

권장: C 또는 D.

---

# 4. 파일 보관 정책 결정

결정해야 할 것:

```text
업로드 원본을 얼마나 보관할지
전처리 이미지를 보관할지
.mxl을 장기 보관할지
.omr을 장기 보관할지
log 보관 기간
실패 작업 보관 기간
MusicContent JSON 보관 기간
```

---

# 5. DB/문서 IR 연결

현재 Music API는 최종 JSON을 반환합니다.

풀스택에서 아래와 연결할지 결정합니다.

```text
문서 objectId
pageId
bbox
userId
검수 상태
검수자
수정 이력
```

향후 전체 OCR 파이프라인과 합칠 때는 `type="music"`인 IR object 안에 MusicContent를 넣는 구조를 권장합니다.

---

# 6. 프론트에서 우선 구현할 화면

1차 연동에서는 최소한 아래만 있으면 됩니다.

```text
악보 이미지 업로드
↓
분석 중 표시
↓
요약(summary.text)
↓
Review 경고
↓
상세 설명(spokenText)
```

검수 화면에서 추가:

```text
confidence
review.reasons
mapping
summary.claims
```

---

# 7. 에러 UI

다음 에러 코드를 사용자 메시지로 매핑하는 것을 권장합니다.

```text
INVALID_FILE_TYPE
→ JPG/JPEG/PNG 파일을 업로드해주세요.

FILE_TOO_LARGE
→ 업로드 가능한 파일 크기를 초과했습니다.

MUSIC_RECOGNITION_FAILED
→ 악보를 인식하지 못했습니다. 다른 이미지로 다시 시도해주세요.

MUSIC_RECOGNITION_TIMEOUT
→ 악보 분석 시간이 초과되었습니다.
```

서버 내부 exception 전체를 일반 사용자에게 그대로 노출하지 않는 것을 권장합니다.

---

# 8. 운영 규모가 커졌을 때 추후 고려

현재 1차 연동에서는 동기 API로 충분합니다.

처리량이 늘면:

```text
POST /recognize
↓
jobId 즉시 반환
↓
queue
↓
worker가 Audiveris 실행
↓
GET /jobs/{jobId}
```

형태로 변경을 고려할 수 있습니다.

Docker도 현재 필수는 아니며, 환경 불일치가 반복되거나 서버가 늘어날 때 도입하면 됩니다.

---

# 9. 향후 기능 담당 경계

현재 음악 모듈:

```text
악보 이미지
→ MusicXML/OMR
→ 구조화
→ confidence/review
→ spokenText
→ summary
```

향후:

```text
점자악보 변환
→ 음악 파트에서 변환 모듈 추가 가능

DAISY/HWP
→ 전체 문서 IR / 출력 serializer와 협의 필요

Playback
→ MusicContent IR 안정화 후 연결
```
