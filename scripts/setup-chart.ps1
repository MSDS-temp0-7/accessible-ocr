$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if (-not (Test-Path .venv\Scripts\python.exe)) { throw '먼저 start-local-ocr.ps1로 기본 Python 환경을 준비하세요.' }
    if (-not (Test-Path .venv-chart\Scripts\python.exe)) {
        & .\.venv\Scripts\python.exe -m venv .venv-chart
        if ($LASTEXITCODE -ne 0) { throw '도표 가상환경 생성 실패' }
    }
    & .\.venv-chart\Scripts\python.exe -m pip install --cache-dir .model-cache\pip torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
    if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch 설치 실패' }
    & .\.venv-chart\Scripts\python.exe -m pip install --cache-dir .model-cache\pip -r ai_engine\requirements-integration.txt
    if ($LASTEXITCODE -ne 0) { throw '도표 의존성 설치 실패' }
    & .\.venv-chart\Scripts\python.exe -c "import torch; print('GPU:', torch.cuda.is_available()); assert torch.cuda.is_available(), 'CUDA GPU required'"
    if ($LASTEXITCODE -ne 0) { throw 'CUDA GPU 확인 실패' }
    Write-Host 'config/integration-api.env에서 CHART_RECOGNITION_ENABLED=true로 설정하세요.'
} finally { Pop-Location }
