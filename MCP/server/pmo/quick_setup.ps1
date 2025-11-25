# Quick Setup for PMO MCP Refactored Server
Write-Host "========================================"
Write-Host "PMO MCP Server - Quick Setup"
Write-Host "========================================"
Write-Host ""

# Step 1: Copy metadata
Write-Host "Step 1: Copying metadata files..."
if (-not (Test-Path "metadata")) {
    New-Item -ItemType Directory -Path "metadata" | Out-Null
}
Copy-Item -Path "..\metadata\*" -Destination "metadata\" -Recurse -Force
Write-Host "✓ Metadata files copied!" -ForegroundColor Green
Write-Host ""

# Step 2: Create .env file
Write-Host "Step 2: Creating .env file..."
if (-not (Test-Path ".env")) {
    Copy-Item -Path "config\.env.example" -Destination ".env"
    Write-Host "✓ .env file created!" -ForegroundColor Green
} else {
    Write-Host "✓ .env file already exists" -ForegroundColor Yellow
}
Write-Host ""

# Step 3: Install dependencies
Write-Host "Step 3: Installing Python dependencies..."
pip install -q pyyaml requests 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencies installed!" -ForegroundColor Green
} else {
    Write-Host "! Some dependencies may have issues (check manually)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "========================================"
Write-Host "Setup complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Edit .env if needed (default API URL: http://localhost:5000)"
Write-Host "2. Test: python server.py"
Write-Host "3. Run client: python ..\..\client\pmo\example_with_refactored_server.py"
Write-Host ""
