# ──────────────────────────────────────────────────────────────
# Test script: verifies the offline dist directory for Windows
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/test-install-windows.ps1
# ──────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DIST = Join-Path $ROOT "dist\roboscope-offline-windows"
$PIP_PLATFORM = "win_amd64"

Write-Host "==> Test: offline dist for platform 'windows'"
Write-Host "    Dist:     $DIST"
Write-Host "    pip plat: $PIP_PLATFORM"
Write-Host ""

# Verify dist exists
if (-not (Test-Path $DIST)) {
    Write-Host "ERROR: $DIST does not exist. Run scripts/build-windows.ps1 first."
    exit 1
}

# Copy dist to temp (simulates extracting the ZIP)
$testDir = Join-Path $env:TEMP "roboscope-test-$([guid]::NewGuid().ToString('N').Substring(0,8))"
New-Item -ItemType Directory -Force -Path $testDir | Out-Null
Copy-Item -Recurse -Force "$DIST\*" $testDir

Write-Host "==> Checking dist contents..."

$reqFile = Join-Path $testDir "requirements.txt"
$wheelsDir = Join-Path $testDir "wheels"
$frontendDir = Join-Path $testDir "frontend_dist"
$srcDir = Join-Path $testDir "src"

Write-Host "    requirements.txt: $(if (Test-Path $reqFile) { 'OK' } else { 'MISSING' })"
$wheelCount = if (Test-Path $wheelsDir) { (Get-ChildItem -Path $wheelsDir).Count } else { 0 }
Write-Host "    wheels:           $wheelCount files"
Write-Host "    frontend_dist:    $(if (Test-Path $frontendDir) { 'OK' } else { 'MISSING' })"
Write-Host "    src/:             $(if (Test-Path $srcDir) { 'OK' } else { 'MISSING' })"
Write-Host ""

# Show requirements
Write-Host "==> requirements.txt:"
if (Test-Path $reqFile) {
    Get-Content $reqFile
} else {
    Write-Host "    (file missing!)"
}
Write-Host ""

# Test: can pip resolve all requirements from the wheels?
Write-Host "==> Testing pip install --dry-run (no actual install)..."

$pythonVersion = python --version 2>&1
Write-Host "    Python: $pythonVersion"
Write-Host "    pip platform: $PIP_PLATFORM"
Write-Host ""

Push-Location $testDir
try {
    python -m pip install `
        --no-index `
        --find-links=wheels `
        -r requirements.txt `
        --dry-run `
        --platform $PIP_PLATFORM `
        --python-version 3.12 `
        --implementation cp `
        --abi cp312 `
        --only-binary :all: `
        2>&1
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}

# Clean up
Remove-Item -Recurse -Force $testDir -ErrorAction SilentlyContinue

Write-Host ""
if ($result -eq 0) {
    Write-Host "==> TEST PASSED: All requirements can be resolved from wheels."
} else {
    Write-Host "==> TEST FAILED: pip could not resolve all requirements (exit code $result)."
    exit 1
}
