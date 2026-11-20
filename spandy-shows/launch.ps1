param([switch]$TrustedLocal, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run the setup commands in README.md to create the project environment first.' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\index.html'))) { throw 'Build the frontend first: pnpm run build. See README.md.' }
if ($TrustedLocal) {
    $env:SPANDY_EXECUTION_MODE='trusted-local'
    $env:SPANDY_TRUST_LOCAL_CODE='1'
    Write-Host 'Spandy Shows - private local mode for your own trusted code.'
} else {
    $env:SPANDY_EXECUTION_MODE='docker'
    Remove-Item Env:SPANDY_TRUST_LOCAL_CODE -ErrorAction SilentlyContinue
}
$env:SPANDY_ORIGINS="http://127.0.0.1:$Port,http://localhost:$Port"
Write-Host "Open http://127.0.0.1:$Port - See your code, step by step."
& $pythonExe -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
