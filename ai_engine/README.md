[AI Module Specification] F3: 도표/그래프 자연어 설명 생성 및 무감독 검수 엔진본 문서는 점자도서 자동 변환 파이프라인 내 F3 모듈(그래프/도표 자연어 설명 생성 및 무감독 자동 검수 엔진)에 대한 개발자 전용 API 명세서입니다. 백엔드 및 통합 파이프라인 구축 시 필요한 클래스 인터페이스, 입출력 JSON 스펙, 작업 라우팅 지침을 명시합니다.1. 모듈 개요 (Overview)모듈 위치: ai_engine/chart_analyzer.py주요 기능:[F1 레이아웃 오려내기]: 스캔 페이지 내 표(Table) 및 도표(Picture) 영역 자동 탐지 및 절단 (DocLayNet YOLOv8).[F3 대체 텍스트 생성]: Vision-Language Model (Qwen2.5-VL-7B) 기반 축/범례/수치 데이터 추출 및 멀티모달 캡셔닝 생성.[F7/F8 무감독 품질 검수]: Ground Truth(정답지) 없이 수치 논리 일치율 및 양식 준수율 기반 자동 무결성 검증 및 신뢰도 라우팅.Plaintext[입력: 스캔 페이지 / 이미지]
       │
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│  ChartAnalyzer (ai_engine/chart_analyzer.py)                           │
│  ├── 1. DocLayNet YOLOv8 ➔ 표/도표 영역 절단 (Crop)                    │
│  ├── 2. Qwen2.5-VL ➔ 서식 지정 추론 (Title/Axis/Data/Description)       │
│  └── 3. Auto-Validation ➔ Structure Score & Consistency Score 산출     │
└────────────────────────────────────────────────────────────────────────┘
       │
       ▼
[출력: Response Dictionary (JSON)]
 ├─ status == "PASS" (종합 점수 ≥ 0.8) ➔ DAISY (Z39.86) / HWP 변환 파이프라인 이관
 └─ status == "FLAG" (종합 점수 < 0.8) ➔ 점자 교열사 검수 큐 (F8 Review Queue) 이동
2. 파일 및 프로젝트 구조 (Directory Structure)백엔드 파이프라인 구축 시 ai_engine/ 디렉터리 내의 코드를 참조하도록 배치합니다.Plaintextproject_root/
├── ai_engine/
│   ├── config.py           # 프롬프트, YOLO/VLM 파라미터 및 임계값 설정
│   ├── chart_analyzer.py   # ChartAnalyzer 메인 파이프라인 클래스[cite: 1]
│   ├── requirements.txt    # 필수 파이썬 라이브러리 목록 (PyTorch, Transformers, YOLO 등)[cite: 1]
│   ├── test_run.py         # 백엔드 연동 전 단독 모듈 테스트 스크립트[cite: 1]
│   └── README.md           # 본 API 명세서 문서[cite: 1]
└── main.py                 # 백엔드 메인 서비스 엔드포인트
3. 클래스 인터페이스 및 연동 방법 (SDK Usage)3.1. 초기화 (__init__)서버 스타트업 시 1회 전역 로드된 VLM 모델과 프로세서를 바인딩하여 엔진을 초기화합니다. (VRAM 메모리 재로드 방지)Pythonfrom ai_engine.chart_analyzer import ChartAnalyzer

# 백엔드 파이프라인 개시 시 1회 바인딩
analyzer = ChartAnalyzer(vlm_model=model, vlm_processor=processor)
3.2. 분석 실행 (analyze)스캔본 이미지 파일 경로(문자열) 또는 PIL.Image 객체를 전달받아 분석 결과를 반환합니다.Python# 이미지 경로(str) 또는 PIL.Image 객체 입력 지원
result = analyzer.analyze(image_input="path/to/scanned_page.png")
3.3. 백엔드 연동 코드 예시 (main.py)Pythonimport torch
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from ai_engine.chart_analyzer import ChartAnalyzer

# 1. 4비트 양자화 모델 로드[cite: 2]
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True
)

model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct",
    quantization_config=quantization_config,
    device_map="auto"
)
processor = AutoProcessor.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct",
    min_pixels=256 * 28 * 28,
    max_pixels=1280 * 28 * 28
)

# 2. AI 분석기 엔진 초기화
analyzer = ChartAnalyzer(vlm_model=model, vlm_processor=processor)

# 3. 요청 처리 함수
def process_scanned_page(image_path):
    response = analyzer.analyze(image_path)

    # 4. 검수 신뢰도 기반 파이프라인 라우팅
    for chart in response["results"]:
        if chart["status"] == "PASS":
            # 자동 통과: DAISY/HWP 변환 파이프라인(F11/F12) 이관
            send_to_daisy_pipeline(chart["parsed_data"])
        else:
            # 저신뢰 구간: 교열사 검수 큐(F8) 라우팅
            send_to_reviewer_queue(chart)
4. 반환 데이터 규격 (API Response Specification)analyzer.analyze() 메서드가 반환하는 응답 객체(Python Dictionary / JSON) 규격입니다[cite: 1].4.1. Response JSON ExampleJSON{
  "feature_id": "F3",
  "total_charts_found": 1,
  "results": [
    {
      "chart_index": 1,
      "status": "PASS",
      "confidence_score": 0.85,
      "parsed_data": {
        "graph_type": "선 그래프",
        "title": "연도별 점자도서 발행 수",
        "axis": "- x_axis: 연도\n- y_axis: 발행 수(권)",
        "legend": "없음",
        "data": "2021년 100권, 2022년 150권, 2023년 230권",
        "description": "2021년부터 2023년까지 점자도서 발행 수가 지속적으로 증가함."
      },
      "raw_text": "graph_type: 선 그래프\ntitle: 연도별 점자도서 발행 수..."
    }
  ]
}
4.2. Field Descriptions (필드 상세 명세)Field NameTypeFormatDescription & Routing Specificationfeature_idString"F3" 고정기능 분류 식별자 (그래프/도표 자연어 설명 생성)[cite: 1, 4]total_charts_foundInteger$\ge 0$DocLayNet YOLO가 자른 페이지 내 도표/표 총 개수[cite: 1, 2, 4]resultsArrayList of Objects각 도표별 분석 및 무감독 검수 결과 리스트[cite: 1, 4]└ chart_indexInteger$1, 2, 3 \dots$페이지 내 도표 순서 인덱스[cite: 1, 4]└ statusString"PASS" | "FLAG"작업 라우팅 상태 값- "PASS": 신뢰도 점수 $\ge 0.8$ (자동 통과 및 DAISY 변환)- "FLAG": 신뢰도 점수 $< 0.8$ (교열자 F8 큐 라우팅)[cite: 1, 2, 4, 5]└ confidence_scoreFloat$0.00 \sim 1.00$무감독 자동 검수 엔진이 산출한 무결성 점수[cite: 1, 2, 4, 5]└ parsed_dataObjectKey-Value대체 텍스트 구성 요소 6종 데이터 딕셔너리    └─ graph_typeStringPlain Text도표 유형 (막대 그래프, 선 그래프, 표 등)    └─ titleStringPlain Text도표 또는 표의 제목    └─ axisStringMulti-line TextX축 및 Y축 이름 및 측정 단위    └─ legendStringPlain Text범례 정보    └─ dataStringText/Numeric이미지 내 추출 원본 수치 데이터 세트    └─ descriptionStringNatural Languagedata 수치 기반 변화 추세 및 설명 문장└ raw_textStringUTF-8 StringVLM 추론 생 원문 (디버깅용)[cite: 1, 4]5. 무감독 검수 알고리즘 산출 명세 (Validation Logic)Ground Truth(정답지)가 없는 스캔본에 대해 아래 산식으로 수치 무결성 점수를 자동 계산합니다.$$\text{Total Score} = (\text{Structure Score} \times 0.4) + (\text{Consistency Score} \times 0.6)$$양식 구조 완성도 ($\text{Structure Score}$ / 40%): 필수 키 6개 항목 중 정상 파싱된 필드의 비율.수치-문맥 일치도 ($\text{Consistency Score}$ / 60%): data 필드 수치 집합($S_{\text{data}}$)과 description 필드 수치 집합($S_{\text{desc}}$) 간 교차 검증을 통한 환각(Hallucination) 감지.$$\text{Consistency Score} = \frac{\vert{}S_{\text{data}} \cap S_{\text{desc}}\vert{}}{\vert{}S_{\text{data}}\vert{}}$$
