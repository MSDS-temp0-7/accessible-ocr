# config.py
# PRD F3 대체 텍스트 생성용 표준 프롬프트[cite: 2]
CHART_PROMPT = """이 그래프를 정밀하게 분석하여 아래 서식으로만 대답하세요.

graph_type: [예: 막대 그래프, 선 그래프, 표]
title: [그래프 또는 표의 제목]

axis:
- x_axis: [X축 이름 및 단위]
- y_axis: [Y축 이름 및 단위]

legend: [범례 정보]

data: [이미지에서 직접 확인 가능한 모든 숫자 데이터를 순서대로 정확하게 적으세요. 추측하지 마세요.]

description: [data에 명시된 숫자를 바탕으로 변화 추세를 설명하세요.]

주의: data 항목에 작성한 숫자와 description 항목에서 언급하는 숫자는 서로 완벽히 일치해야 합니다."""

# DocLayNet YOLO 가중치 레포지토리 및 파일명[cite: 2]
DOCLAYNET_REPO_ID = "michaelfeil/bnn-yolov8-doclaynet"
DOCLAYNET_FILENAME = "yolov8n-doclaynet.pt"

# 무감독 자동 검수 승인 임계값 (0.8 = 80%)[cite: 2, 5]
PASS_THRESHOLD = 0.8