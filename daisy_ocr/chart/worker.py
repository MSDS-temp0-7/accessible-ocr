"""JSON-lines worker. Model logs go to stderr, replies go to stdout."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HOME", str(ROOT / ".model-cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def load_analyzer():
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
    from ai_engine.chart_analyzer import ChartAnalyzer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU를 사용할 수 없습니다. 도표용 CUDA PyTorch 환경을 확인하세요.")
    torch.set_num_threads(4)
    model_id = os.environ.get("CHART_MODEL_ID", "Qwen/Qwen2.5-VL-7B-Instruct")
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
        ),
        device_map={"": 0}, torch_dtype=torch.float16,
        attn_implementation="sdpa",
    )
    model.eval()
    processor = AutoProcessor.from_pretrained(
        model_id, min_pixels=256 * 28 * 28,
        max_pixels=int(os.environ.get("CHART_MAX_PIXELS", str(512 * 28 * 28))),
    )
    return ChartAnalyzer(model, processor, pre_cropped=True)


def main():
    analyzer = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                if analyzer is None:
                    analyzer = load_analyzer()
                result = analyzer.analyze(request["image_path"])
            response = {"ok": True, "result": result}
        except Exception as exc:
            import traceback
            traceback.print_exc(file=sys.stderr)
            response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
