# Build paper/main.pdf: regenerate the generated inputs, check them, then pdflatex -> bibtex -> pdflatex x2.
# Needs MiKTeX (installed per user via winget) and the project venv. Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts/build_paper.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$bin = "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64"
& $py (Join-Path $root "scripts\lit\gap_table_tex.py")
& $py (Join-Path $root "scripts\lit\lit_numbers.py")
& $py (Join-Path $root "scripts\lit\make_bib.py")
& $py (Join-Path $root "scripts\check_paper_macros.py")
if ($LASTEXITCODE -ne 0) { throw "paper macro/citation check failed" }
Push-Location (Join-Path $root "paper")
try {
    & "$bin\pdflatex.exe" -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    & "$bin\bibtex.exe" main | Out-Null
    & "$bin\pdflatex.exe" -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    & "$bin\pdflatex.exe" -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    Select-String -Path main.log -Pattern "Overfull|undefined|Rerun to get" | ForEach-Object { $_.Line }
    Write-Output "built paper/main.pdf"
} finally { Pop-Location }
