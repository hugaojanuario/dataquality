$ErrorActionPreference = "Stop"

python -m pip install -e ".[build,jdbc]"
python -m PyInstaller --clean --noconfirm dataqualy.spec

Write-Host "Executável criado em dist\dataqualy.exe"

# @hugaojanuario
