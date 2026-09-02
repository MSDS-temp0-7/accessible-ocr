param(
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$localConfig = Join-Path $repositoryRoot "config\integration-api.env"

if (-not (Test-Path -LiteralPath $localConfig)) {
    throw "config\integration-api.env 파일이 없습니다. integration-api.env.example을 복사하고 CLOVA 값을 입력하세요."
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uvExecutable = $uvCommand.Source
} else {
    $fallbackUv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path -LiteralPath $fallbackUv) {
        $uvExecutable = $fallbackUv
    } else {
        throw "uv를 찾을 수 없습니다. https://docs.astral.sh/uv/ 의 Windows 설치 안내에 따라 먼저 설치하세요."
    }
}

Push-Location $repositoryRoot
try {
    if (-not $SkipSync) {
        # 한글이 포함된 프로젝트 경로에서도 Python 3.11이 안정적으로 실행되도록
        # 편집형 .pth 링크 대신 일반 wheel 설치를 사용한다.
        & $uvExecutable sync --no-dev --no-editable --reinstall-package daisy-ocr
        if ($LASTEXITCODE -ne 0) { throw "Python 의존성 설치에 실패했습니다." }
    }

    Write-Host "Accessible OCR 로컬 API를 http://localhost:8000 에서 시작합니다."
    Write-Host "이 창을 닫으면 OCR API도 종료됩니다."
    & $uvExecutable run --no-sync daisy-ocr-api
    if ($LASTEXITCODE -ne 0) { throw "로컬 OCR API 실행에 실패했습니다." }
}
finally {
    Pop-Location
}
