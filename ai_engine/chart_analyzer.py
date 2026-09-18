# chart_analyzer.py
import os
import gc
import re
import torch
from PIL import Image

# config.py로부터 설정값 모듈 임포트
from .config import CHART_PROMPT, DOCLAYNET_REPO_ID, DOCLAYNET_FILENAME, PASS_THRESHOLD

class ChartAnalyzer:
    def __init__(self, vlm_model, vlm_processor, *, pre_cropped=False):
        """
        시스템 시작 시 백엔드 파이프라인에서 전역 로드된 Qwen2.5-VL 모델과 프로세서를 바인딩합니다.[cite: 1, 4]
        """
        self.model = vlm_model
        self.processor = vlm_processor
        self.prompt = CHART_PROMPT  # config.py의 프롬프트 참조[cite: 1]
        self.pre_cropped = pre_cropped
        if pre_cropped:
            return
        from ultralytics import YOLO
        from huggingface_hub import hf_hub_download

        # 1. 문서 전용 YOLO (DocLayNet) 모델 로드 (PRD F1)[cite: 2]
        print("📥 [DocLayNet YOLO] 레이아웃 분석 모델을 초기화 중입니다...")
        try:
            model_path = hf_hub_download(
                repo_id=DOCLAYNET_REPO_ID,
                filename=DOCLAYNET_FILENAME
            )
            self.layout_model = YOLO(model_path)
        except Exception as e:
            raise RuntimeError("DocLayNet 모델 로드 실패") from e

    def crop_components(self, raw_image):
        """스캔 이미지에서 표(Table) 및 도표(Picture) 영역을 가위질(Crop)합니다."""
        results = self.layout_model(raw_image)
        cropped_images = []

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])  # DocLayNet: 6=Picture(도표), 8=Table(표)[cite: 2]
                conf = float(box.conf[0])
                if cls_id in [6, 8] and conf >= 0.25:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cropped_img = raw_image.crop((x1, y1, x2, y2))
                    cropped_images.append(cropped_img)

        return cropped_images if cropped_images else [raw_image]

    def analyze(self, image_input):
        """
        [백엔드 호출 메인 함수][cite: 1, 4]
        스캔 이미지 경로 또는 PIL Image를 받아 전처리, 추론, 무감독 검수를 거친 후
        JSON 연동용 딕셔너리를 반환합니다.[cite: 1, 4]
        """
        # 1. 입력 타입 처리 (파일 경로 문자열인 경우 PIL Image로 변환)[cite: 1, 4]
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"❌ 파일을 찾을 수 없습니다: {image_input}")
            raw_image = Image.open(image_input)
        else:
            raw_image = image_input

        # 2. 도표 영역 절단 (PRD F1 전처리)[cite: 2]
        target_charts = [raw_image] if self.pre_cropped else self.crop_components(raw_image)
        analysis_results = []

        # 3. 크롭된 도표들에 대해 순차적 VLM 분석 및 무감독 검수 실행[cite: 1]
        for idx, chart_img in enumerate(target_charts):
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": chart_img},
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ]

            text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.processor(text=[text], images=[chart_img], padding=True, return_tensors="pt").to("cuda")

            # GPU 메모리 비우기[cite: 2]
            gc.collect()
            torch.cuda.empty_cache()

            # Qwen2.5-VL Greedy Search 추론 (환각 차단)[cite: 2]
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False,
                )

            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]

            output_text = self.processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False
            )[0]

            # 4. 무감독 무결성 검수 (PRD F7/F8)[cite: 2]
            score, parsed_data = self._auto_validate(output_text)

            analysis_results.append({
                "chart_index": idx + 1,
                "status": "PASS" if score >= PASS_THRESHOLD else "FLAG",  # PASS_THRESHOLD(0.8) 기준 라우팅
                "confidence_score": round(score, 2),
                "parsed_data": parsed_data,
                "raw_text": output_text
            })

        # 백엔드로 전달될 최종 JSON 규격 딕셔너리 리턴[cite: 1, 4]
        return {
            "feature_id": "F3",
            "total_charts_found": len(target_charts),
            "results": analysis_results
        }

    def _auto_validate(self, text):
        """무감독 수치 일치율 및 양식 구조 완성도를 수학적으로 검증합니다.[cite: 2, 5]"""
        required_keys = ["graph_type", "title", "axis", "legend", "data", "description"]
        parsed_data = {}

        for i, key in enumerate(required_keys):
            pattern = rf"(?:^|\n){key}:[ \t]*(.*?)(?=\n(?:" + "|".join(required_keys) + r"):|\Z)"
            match = re.search(pattern, text, re.DOTALL)
            parsed_data[key] = match.group(1).strip() if match else ""

        # 구조 완성도 점수 계산[cite: 2, 5]
        valid_keys_count = sum(1 for v in parsed_data.values() if len(v) > 0)
        structure_score = valid_keys_count / len(required_keys)

        # 수치 교차 일치율 (data vs description)[cite: 2, 5]
        data_numbers = set(re.findall(r'\d+\.?\d*', parsed_data.get('data', '')))
        desc_numbers = set(re.findall(r'\d+\.?\d*', parsed_data.get('description', '')))

        if data_numbers and desc_numbers:
            consistency_score = len(data_numbers.intersection(desc_numbers)) / len(data_numbers.union(desc_numbers))
        elif not data_numbers and not desc_numbers:
            consistency_score = 1.0
        else:
            consistency_score = 0.0

        total_score = (structure_score * 0.4) + (consistency_score * 0.6)
        return total_score, parsed_data
