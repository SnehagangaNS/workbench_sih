# ============================================================================
# pull_models.ps1
# Downloads any models referenced in config/models.yaml that aren't already
# pulled. Run `ollama list` first to see what you have - if you already have
# everything config/models.yaml expects, you don't need this at all.
#
# Run from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\pull_models.ps1
# ============================================================================

Write-Host "=== Local Workbench: checking/pulling models ===" -ForegroundColor Cyan

# Core set currently referenced in config/models.yaml (as of your setup):
$models = @(
    "qwen2.5-coder:7b-instruct-q4_K_M",
    "qwen2.5:3b-instruct-q4_K_M",
    "moondream:latest",
    "nomic-embed-text"
)

foreach ($m in $models) {
    Write-Host "`nChecking $m ..." -ForegroundColor Yellow
    ollama pull $m
}

Write-Host "`n=== Optional upgrades (skip if you're short on time/bandwidth) ===" -ForegroundColor Cyan
Write-Host "  Better general/document quality: ollama pull llama3.1:8b-instruct-q4_K_M"
Write-Host "  Better OCR/handwriting/drawing accuracy: ollama pull qwen2.5vl:3b"
Write-Host "  If you pull either, edit config/models.yaml to register it (see comments in that file)."

Write-Host "`n=== Done. Run 'ollama list' to confirm, then you can go fully offline. ===" -ForegroundColor Cyan
