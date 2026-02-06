# Setup script using uv with hardlink workaround for Windows/OneDrive

Write-Host "Setting up environment with uv..." -ForegroundColor Green

# Set environment variable to use copy mode (fixes OneDrive hardlink issue)
$env:UV_LINK_MODE = "copy"

Write-Host "Creating virtual environment (using copy mode for OneDrive compatibility)..." -ForegroundColor Green
uv venv --link-mode=copy

Write-Host "Activating virtual environment..." -ForegroundColor Green
.\.venv\Scripts\Activate.ps1

Write-Host "Installing dependencies..." -ForegroundColor Green
uv pip install --link-mode=copy -r requirements.txt
uv pip install --link-mode=copy google-generativeai

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "To activate: .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "To run: python -m synthetic_notices.llm_main --count 100 --valid-ratio 0.3" -ForegroundColor Yellow
