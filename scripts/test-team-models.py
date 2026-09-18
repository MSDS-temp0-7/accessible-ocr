"""Run real local inference on labelled test samples; never substitutes stored results."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(ROOT / "config/integration-api.env")
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["chart", "music", "all"], default="all")
    args = parser.parse_args()
    out = ROOT / "artifacts/team-model-tests"
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    if args.mode in {"chart", "all"}:
        from daisy_ocr.chart.adapter import recognize_chart_region, _worker
        os.environ["CHART_RECOGNITION_ENABLED"] = "true"
        image = Image.new("RGB", (800, 600), "white")
        d = ImageDraw.Draw(image)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
        d.text((210, 30), "Quarterly sales (units)", font=font, fill="black")
        d.line([(100, 100), (100, 500), (740, 500)], fill="black", width=3)
        for n in [0, 10, 20, 30]:
            y = 500 - n * 10
            d.text((45, y - 15), str(n), font=font, fill="black")
            d.line((95, y, 740, y), fill="#cccccc")
        for x, value, label in [(220, 10, "Q1"), (420, 20, "Q2"), (620, 30, "Q3")]:
            d.rectangle((x - 40, 500 - value * 10, x + 40, 498), fill="#2266cc")
            d.text((x - 20, 460 - value * 10), str(value), font=font, fill="black")
            d.text((x - 22, 520), label, font=font, fill="black")
        image.save(out / "chart-input.png")
        started = time.monotonic()
        try:
            text, score = recognize_chart_region(image, out / "charts", page_index=0, region_index=0)
            report["chart"] = {"success": True, "seconds": round(time.monotonic() - started, 1), "text": text, "quality_score": score,
                               "expected": {"Q1": 10, "Q2": 20, "Q3": 30}, "note": "Synthetic integration fixture; quality score is not accuracy."}
        except Exception as exc:
            report["chart"] = {"success": False, "error": str(exc)}
        finally:
            image.close()
            _worker.close()
    if args.mode in {"music", "all"}:
        from daisy_ocr.music.adapter import recognize_music_region, music_runtime_status
        started = time.monotonic()
        try:
            with Image.open(ROOT / "daisy-music/audiveris_input/M01_4000.png") as image:
                result = recognize_music_region(image, out / "music", page_index=0, region_index=0)
            report["music"] = {"success": True, "seconds": round(time.monotonic() - started, 1),
                               "text": result.text, "confidence": result.confidence, "needs_review": result.needs_review,
                               "has_music_xml": bool(result.music_xml), "runtime": music_runtime_status()}
        except Exception as exc:
            report["music"] = {"success": False, "error": str(exc), "runtime": music_runtime_status()}
    path = out / f"{args.mode}-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, result in report.items():
        print(name, "PASS" if result["success"] else "FAIL", result.get("error", ""))
    print("Report:", path)
    return 0 if all(result["success"] for result in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
