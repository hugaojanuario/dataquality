param([switch]$SmokeTest)
$ErrorActionPreference = "Stop"

python -m pip install -e ".[build,jdbc]"
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências." }
python -m compileall -q src
if ($LASTEXITCODE -ne 0) { throw "Falha na compilação Python." }
python -m PyInstaller --clean --noconfirm sincro.spec
if ($LASTEXITCODE -ne 0) { throw "Falha no build PyInstaller." }

if ($SmokeTest) {
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:QT_QUICK_BACKEND = "software"
    $process = Start-Process -FilePath ".\dist\sincro.exe" -ArgumentList "--demo", "--screenshots", "build\desktop-smoke" -PassThru
    if (-not $process.WaitForExit(180000)) {
        $process.Kill()
        throw "Timeout no smoke test do executável."
    }
    if ($process.ExitCode -ne 0) { throw "O executável não concluiu a demonstração." }
    $count = (Get-ChildItem "build\desktop-smoke\*.png").Count
    if ($count -ne 32) { throw "Esperadas 32 capturas, encontradas $count." }
}
Write-Host "Executável criado em dist\sincro.exe"
