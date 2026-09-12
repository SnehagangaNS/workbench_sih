# ============================================================================
# setup_windows.ps1
# One-time setup. Run from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
# ============================================================================

Write-Host "=== Local Workbench setup ===" -ForegroundColor Cyan

# 1. Python venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "Activating virtual environment..."
. .\.venv\Scripts\Activate.ps1

Write-Host "Installing Python dependencies (this can take a few minutes)..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt

# 2. Check for Ollama
Write-Host "`nChecking for Ollama..." -ForegroundColor Cyan
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($null -eq $ollama) {
    Write-Host "  Ollama NOT found." -ForegroundColor Red
    Write-Host "  Download and install from https://ollama.com/download/windows (one-time, needs internet)."
    Write-Host "  Re-run this script after installing."
} else {
    Write-Host "  Ollama found: $($ollama.Source)" -ForegroundColor Green
}

# 3. Check for Tesseract (printed-text OCR)
Write-Host "`nChecking for Tesseract OCR..." -ForegroundColor Cyan
$tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if ($null -eq $tesseract) {
    Write-Host "  Tesseract NOT found." -ForegroundColor Red
    Write-Host "  Download from https://github.com/UB-Mannheim/tesseract/wiki (installer, one-time, needs internet)."
    Write-Host "  Make sure to add it to PATH during install, or set pytesseract.pytesseract.tesseract_cmd manually."
} else {
    Write-Host "  Tesseract found: $($tesseract.Source)" -ForegroundColor Green
}

# 4. Check for Poppler (needed by pdf2image to rasterize scanned PDFs)
Write-Host "`nChecking for Poppler (pdftoppm)..." -ForegroundColor Cyan
$poppler = Get-Command pdftoppm -ErrorAction SilentlyContinue
if ($null -eq $poppler) {
    Write-Host "  Poppler NOT found." -ForegroundColor Red
    Write-Host "  Download a Windows build from https://github.com/oschwartz10612/poppler-windows/releases"
    Write-Host "  Extract it and add the 'Library\bin' folder to your PATH."
} else {
    Write-Host "  Poppler found: $($poppler.Source)" -ForegroundColor Green
}

Write-Host "`n=== Setup script done. Next: run scripts\pull_models.ps1 to download models (needs internet, one-time). ===" -ForegroundColor Cyan
