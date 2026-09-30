"""One-page real CLOVA + team chart integration test on isolated port 8002."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
import io
from xml.etree import ElementTree as ET

import requests
import psutil
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
out = ROOT / "artifacts/team-model-tests"
out.mkdir(parents=True, exist_ok=True)
with Image.open(out / "chart-input.png") as image:
    image.convert("RGB").save(out / "chart-test.pdf", "PDF", resolution=100)
env = dict(os.environ, OCR_API_PORT="8002", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
url = "http://127.0.0.1:8002"
log = (out / "api-test.log").open("w", encoding="utf-8")
server = subprocess.Popen([sys.executable, "-m", "daisy_ocr.server"], cwd=ROOT, env=env,
                          stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
(out / "test-server.pid").write_text(str(server.pid), encoding="ascii")
try:
    for _ in range(60):
        if server.poll() is not None:
            raise RuntimeError("Test API exited; see api-test.log")
        try:
            health = requests.get(url + "/health", timeout=2).json()
            break
        except requests.RequestException:
            time.sleep(1)
    else:
        raise RuntimeError("Test API startup timeout")
    with (out / "chart-test.pdf").open("rb") as source:
        response = requests.post(url + "/api/v1/jobs", files={"file": ("chart-test.pdf", source, "application/pdf")},
                                 data={"options": json.dumps({"PageRange": "1", "DetectMusic": False})}, timeout=30)
    response.raise_for_status()
    job = response.json()
    started = time.monotonic()
    while time.monotonic() - started < 900:
        job = requests.get(url + "/api/v1/jobs/" + job["job_id"], timeout=10).json()
        if job["status"] in {"done", "failed"}:
            break
        time.sleep(3)
    report = {"job_status": job["status"], "seconds": round(time.monotonic()-started, 1), "chart_health": health.get("chart")}
    if job["status"] == "done":
        response = requests.get(url + "/api/v1/jobs/" + job["job_id"] + "/result", timeout=30)
        response.raise_for_status()
        (out / "api-result.zip").write_bytes(response.content)
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            review = json.loads(z.read("review.json"))
            xml = ET.fromstring(z.read("book.xml"))
            text = "\n".join(xml.itertext())
            report.update(elements=list(review["elements"].values()), text=text)
        report["chart_success"] = any(e["error"] == "chart_review_required" for e in report["elements"])
    else:
        report["error"] = job.get("error", "Timed out")
    (out / "api-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("API job:", report["job_status"], "chart success:", report.get("chart_success", False), flush=True)
finally:
    # Stop only this test process tree, never the user's API on port 8000.
    parent = psutil.Process(server.pid)
    for child in reversed(parent.children(recursive=True)):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    server.terminate()
    server.wait(timeout=15)
    log.close()
