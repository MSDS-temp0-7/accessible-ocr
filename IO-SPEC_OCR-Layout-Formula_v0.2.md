# 📤 I/O 정의서 — OCR 레이아웃 · 수식 변환 (F1 / F4)

> 담당: OCR 레이아웃 설정 + 수식 변환
> 대상 독자: 풀스택 팀
> 버전: **v0.2 (초안)** · 작성일: 2026-08-06
> 근거: `OCR-DAISY_PRD_v3.md` (F1, F4, F6, F11)
> v0.1 대비 변경: **출력을 커스텀 JSON → DAISY3(DTBook) 표준 문서 + 검수 사이드카 2층 구조로 전환**

이 문서는 담당 모듈이 **무엇을 입력받아 무엇을 내보내는지**만 규정합니다.
내부 엔진 구현/모델 선택은 범위 밖입니다.

---

## 0. 담당 범위 요약

| 모듈 | PRD | 이 문서에서 정의하는 것 |
|---|---|---|
| **F1 레이아웃/분류** | F1 (🔴 P0) 중 레이아웃·유형 분류·라우팅 | 멀티페이지 PDF → **DTBook 문서**(구조·판독순서) + 검수 사이드카(신뢰도·좌표) |
| **F4 수식 변환** | F4 (🟡 P1) | 수식 블록 → **MathML**(DTBook에 인라인 삽입) + 낭독 자연어(alttext) + 신뢰도 |

- F2(표)·F3(그래프)·F5(악보)의 **내부 변환은 각 담당**. F1은 해당 영역을 **검출·분류·라우팅**하고 DTBook에 자리(placeholder 요소)를 잡아준다.
- F4는 F1이 `formula`로 분류한 요소만 입력으로 받아 MathML을 채운다.

---

## 1. 출력 아키텍처 (핵심)

**출력은 2개 레이어로 분리된다.**

```
[F1/F4 출력 패키지]
 ├─ book.xml        ← DAISY3 DTBook 표준 문서
 │                     · 문서 구조 / 판독 순서(=문서 순서)
 │                     · 표(table), 수식(MathML), 그래프(img+prodnote)
 │                     · 원본 페이지 경계(pagenum)
 │                     · 검수 대상 요소마다 id 부여
 │
 └─ review.json     ← 검수 전용 사이드카 (DTBook element id 기준)
                       · id → confidence(0~1), bbox, region_ref
                       · DAISY export 시 폐기됨
```

- **레이아웃/구조/수식 = 100% DAISY3 표준(DTBook).** 커스텀 필드로 관리하지 않는다.
- **신뢰도·픽셀 좌표 = 사이드카.** DTBook 표준에 없는 값이라 분리하며, `id`로만 연결된다.
- F11 DAISY 출력은 `book.xml`을 **검증·패키징**만 하면 됨(사이드카는 무시).
- 검수 UI(F6/F7/F8)만 `review.json`을 읽어 원본 이미지 위 하이라이트·커서 동기화를 수행.

> ✅ **확정**: 검수 단계에서 원본 이미지 위 하이라이트/커서 동기화를 사용한다(F6/F7). 따라서 사이드카의 `bbox`/`region_ref`는 **유지**한다.

---

## 2. 연동 방식 (제안 · 확정 전)

**제안: 비동기 Job + 상태 조회/콜백** (멀티페이지 OCR은 동기 REST 타임아웃 위험)

```
[풀스택]  ──(1) PDF 업로드/Job 생성──▶  [OCR 파이프라인]
[풀스택]  ◀─(2) job_id, status=queued─
          ... 처리 ...
[풀스택]  ◀─(3) 완료 콜백(webhook) 또는 폴링(GET /jobs/{id})─
[풀스택]  ──(4) 결과 패키지(book.xml + review.json) 조회──▶
```

- **결과 전달 단위: 문서 전체 일괄** (v1 권장). DTBook·DAISY export가 문서 단위라 계약이 단순.
  페이지 단위 스트리밍은 `pagenum` 구조상 **후속에 비파괴적 추가** 가능. → TBD-B

---

## 3. 공통 규약

### 3.1 신뢰도 (confidence)
- **연속값 `0.0 ~ 1.0` (raw)** 로 통일. 1.0 = 최고 신뢰.
- 🟢/🟡/🔴 색상 임계값 매핑은 **프론트(F7) 책임**. 엔진은 raw만 제공.
- 위치: `review.json`, 필드명 `confidence`.

### 3.2 좌표계 (사이드카 전용)
- 단위 픽셀, 원점 좌상단. `bbox = [x, y, w, h]`
- 원본은 페이지 단위이므로 좌표는 `page_index`와 함께 제공.
- 페이지 렌더 배율 계산용으로 페이지 `width/height/dpi`를 `review.json`에 함께 제공.

### 3.3 식별자
- `page_index`: 0-based (사이드카/pagenum 매칭용)
- DTBook 요소 `id`: 문서 내 유일 (예: `e0012`). **사이드카 연결 키.**
- 판독 순서: **DTBook 문서 순서로 표현** (별도 정수 필드 없음).

### 3.4 인코딩
- XML/JSON 모두 UTF-8.

---

## 4. F1 출력 — DTBook 문서 + 사이드카

### 4.1 입력
| 필드 | 타입 | 설명 |
|---|---|---|
| `document_id` | string | 문서 식별자 |
| `file` | PDF (멀티페이지) | 원본 스캔 PDF |
| `options` | object (optional) | 임계값 등 튜닝 파라미터 (TBD-C) |

### 4.2 출력 A — `book.xml` (DTBook / DAISY3)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<dtbook version="2005-3" xml:lang="ko"
        xmlns="http://www.daisy.org/z3986/2005/dtbook/"
        xmlns:m="http://www.w3.org/1998/Math/MathML">
  <book>
    <bodymatter>
      <level1>
        <pagenum id="pg0" page="normal">1</pagenum>

        <!-- 본문(F1이 직접 텍스트 채움) -->
        <h1 id="e0001">제1장 서론</h1>
        <p id="e0002">이 장에서는 ...</p>

        <!-- 표(F2 담당, F1은 자리+분류만) -->
        <table id="e0010"><!-- F2가 tr/td 채움 --></table>

        <!-- 수식(F4가 MathML 채움) -->
        <p id="e0012">
          <m:math altimg="doc_001/p0/e0012.png"
                  alttext="x는 마이너스 b 플러스마이너스 ...">
            <!-- F4가 MathML 본문 삽입 -->
          </m:math>
        </p>

        <!-- 그래프(F3 담당) -->
        <imggroup id="e0020">
          <img src="doc_001/p0/e0020.png"/>
          <prodnote render="optional"><!-- F3 자연어 설명 --></prodnote>
        </imggroup>
      </level1>
    </bodymatter>
  </book>
</dtbook>
```

**유형 → DTBook 매핑**
| F1 분류 유형 | DTBook 표현 | 채우는 주체 |
|---|---|---|
| `text` (본문/제목) | `h1~6`, `p` | **F1** |
| `table` | `table` | F2 |
| `formula` | `<m:math>` | **F4** |
| `graph` | `imggroup`(img+prodnote) | F3 |
| `music` | `prodnote`/placeholder | F5 |
| 페이지 경계 | `pagenum` | **F1** |

- F1은 본문 텍스트를 채우고, 비본문 유형은 **빈 요소 + `id`**만 잡아 각 담당 엔진으로 라우팅.

### 4.3 출력 B — `review.json` (검수 사이드카)
```jsonc
{
  "document_id": "doc_001",
  "status": "done",
  "pages": [
    { "page_index": 0, "width": 2480, "height": 3508, "dpi": 300 }
  ],
  "elements": {
    "e0001": { "type": "text",    "confidence": 0.991, "page_index": 0, "bbox": [140, 220, 2100, 180] },
    "e0012": { "type": "formula", "confidence": 0.72,  "page_index": 0, "bbox": [300, 900, 1200, 260],
               "region_ref": "doc_001/p0/e0012.png" },
    "e0020": { "type": "graph",   "confidence": 0.65,  "page_index": 0, "bbox": [200, 1400, 1600, 900],
               "region_ref": "doc_001/p0/e0020.png" }
  }
}
```

- 키 = `book.xml`의 요소 `id`. 검수 UI가 이 좌표로 원본 이미지에 하이라이트.
- 낮은 `confidence`도 그대로 노출(유형 오분류를 검수에서 식별 — PRD F1 AC).

---

## 5. F4 수식 변환 I/O

### 5.1 입력
F1이 `formula`로 분류한 요소.
| 필드 | 타입 | 설명 |
|---|---|---|
| `element_id` | string | DTBook 요소 id (그대로 유지) |
| `region_ref` | string | 수식 크롭 이미지 (공유 스토리지 경로 참조 — 권장) |
| `context` | object (opt) | 주변 텍스트 힌트 (TBD-D) |

> region_ref 전달: **공유 스토리지 경로 참조** 권장(비동기 Job이 스토리지를 쓰므로 자연스러움). `bbox`가 사이드카에 항상 있으므로 F4가 직접 크롭하는 폴백도 가능.

### 5.2 출력 — DTBook `<m:math>` 채우기 + 사이드카 갱신
- `<m:math>` 내부에 **MathML(Presentation) 본문 삽입**
- `alttext` 속성 = **낭독용 자연어 텍스트**(내레이터/DAISY TTS용). 기본 언어 **`ko` 가정** → TBD-E
- `altimg` 속성 = 원본 크롭 이미지(폴백 표시용)
- `review.json`의 해당 `element_id` `confidence`를 F4가 재산출해 갱신

**범위 밖(현 확정)**
- LaTeX 동시 출력: ❌ (MathML만) — 확정
- 수학점자(Nemeth) 매핑: ❌ 담당 범위 제외 — 확정

---

## 6. 오류 / 상태

| status | 의미 |
|---|---|
| `queued` / `processing` / `done` / `failed` | 접수 / 처리중 / 완료 / 실패(`error` 사유) |

- 요소 단위 부분 실패 표현: 사이드카 element에 `error` 필드 vs 스킵 → TBD-F

---

## 7. 확정 / 미확정 정리

### ✅ 확정
- 출력 = **DAISY3 DTBook 표준 문서 + 검수 사이드카** 2층 구조
- 신뢰도 = 연속값 0~1 raw (색상 매핑은 프론트)
- 입력 = 멀티페이지 PDF
- F4 출력 = MathML + 낭독 자연어(alttext), **LaTeX·수학점자 제외**
- 검수 이미지 하이라이트 사용 → **사이드카 bbox/region_ref 유지**

### ❓ 미확정 (협의 필요)
| # | 항목 | 관련 |
|---|---|---|
| TBD-B | 페이지 단위 스트리밍 지원 여부 (v1은 문서 일괄 권장) | 2절 |
| TBD-C | F1 튜닝 파라미터(options) 노출 범위 | 4.1 |
| TBD-D | F4에 주변 텍스트 컨텍스트 전달 여부 | 5.1 |
| TBD-E | 낭독 자연어 언어 = 한국어 확정? | 5.2 |
| TBD-F | 요소 단위 부분 실패 표현 방식 | 6절 |
