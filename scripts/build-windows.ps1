# ──────────────────────────────────────────────────────────────
# RoboScope — Build script for standalone offline Windows distribution
#
# Creates a self-contained directory 'dist/roboscope-offline-windows/'
# that can be zipped and deployed on a Windows machine without internet.
#
# Must be run on a Windows host so that pip resolves Windows-specific
# environment markers correctly (e.g. tzdata on sys_platform=='win32').
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/build-windows.ps1
# ──────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$UV_BASE = "https://github.com/astral-sh/uv/releases/latest/download"
$UV_ARCHIVE = "uv-x86_64-pc-windows-msvc.zip"
$UV_BIN_NAME = "uv-windows.exe"
$WHEEL_PLATFORM = "win_amd64"
$ZIP_NAME = "roboscope_offline_windows.zip"

$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DIST = Join-Path $ROOT "dist\roboscope-offline-windows"

Write-Host "==> RoboScope Build (offline, windows)"
Write-Host "    Root: $ROOT"
Write-Host "    Dist: $DIST"
Write-Host ""

# ── 1. Clean previous build ──────────────────────────────────
if (Test-Path $DIST) {
    Remove-Item -Recurse -Force $DIST
}
New-Item -ItemType Directory -Force -Path $DIST | Out-Null

# ── 2. Build frontend ────────────────────────────────────────
Write-Host "==> Building frontend..."
Push-Location (Join-Path $ROOT "frontend")
try {
    # npm writes warnings to stderr; temporarily allow non-terminating errors
    $oldEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    npm ci --prefer-offline 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) {
        npm install 2>&1 | ForEach-Object { "$_" }
    }
    npm run build 2>&1 | ForEach-Object { "$_" }
    $ErrorActionPreference = $oldEAP
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally {
    Pop-Location
}

# Copy built frontend into dist as frontend_dist/
Copy-Item -Recurse -Force (Join-Path $ROOT "frontend\dist") (Join-Path $DIST "frontend_dist")
Write-Host "    Frontend built: $DIST\frontend_dist"

# ── 3. Copy backend source ───────────────────────────────────
Write-Host "==> Copying backend..."
Copy-Item -Recurse -Force (Join-Path $ROOT "backend\src") (Join-Path $DIST "src")
Copy-Item -Force (Join-Path $ROOT "backend\pyproject.toml") $DIST

# Copy example test files for the seeded "Examples" project
$examplesDir = Join-Path $ROOT "backend\examples"
if (Test-Path $examplesDir) {
    Copy-Item -Recurse -Force $examplesDir (Join-Path $DIST "examples")
    Write-Host "    Examples: $DIST\examples"
}

# Copy migrations if they exist
$migrationsDir = Join-Path $ROOT "backend\migrations"
if (Test-Path $migrationsDir) {
    Copy-Item -Recurse -Force $migrationsDir (Join-Path $DIST "migrations")
    $alembicIni = Join-Path $ROOT "backend\alembic.ini"
    if (Test-Path $alembicIni) {
        Copy-Item -Force $alembicIni $DIST
    }
}

# Copy README
Copy-Item -Force (Join-Path $ROOT "scripts\dist-README.md") (Join-Path $DIST "README.md")
Write-Host "    README: $DIST\README.md"

# ── 3b. Download uv binary for Windows ───────────────────────
Write-Host "==> Downloading uv binary for windows..."
$uvBinDir = Join-Path $DIST "uv-bin"
New-Item -ItemType Directory -Force -Path $uvBinDir | Out-Null

try {
    $uvZipPath = Join-Path $uvBinDir $UV_ARCHIVE
    Invoke-WebRequest -Uri "$UV_BASE/$UV_ARCHIVE" -OutFile $uvZipPath -UseBasicParsing
    Expand-Archive -Path $uvZipPath -DestinationPath $uvBinDir -Force
    # The archive extracts to a subdirectory; find uv.exe and move it
    $uvExe = Get-ChildItem -Path $uvBinDir -Recurse -Filter "uv.exe" | Select-Object -First 1
    if ($uvExe) {
        Move-Item -Force $uvExe.FullName (Join-Path $uvBinDir $UV_BIN_NAME)
    }
    # Clean up archive and extracted subdirectory
    Remove-Item -Force $uvZipPath -ErrorAction SilentlyContinue
    Get-ChildItem -Path $uvBinDir -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "    uv binary: $UV_BIN_NAME"
} catch {
    Write-Host "    WARN: failed to download uv binary for windows: $_"
}

# ── 4. Download Python wheels for offline install ─────────────
Write-Host "==> Downloading Python wheels for windows ($WHEEL_PLATFORM)..."
$wheelsDir = Join-Path $DIST "wheels"
New-Item -ItemType Directory -Force -Path $wheelsDir | Out-Null

# Extract dependencies from pyproject.toml
$depsFile = Join-Path $env:TEMP "roboscope-deps-$([guid]::NewGuid().ToString('N').Substring(0,8)).txt"
$pyScript = Join-Path $env:TEMP "roboscope-read-deps.py"
# Write Python script to temp file to avoid PowerShell heredoc quoting issues
@'
import pathlib
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        import sys
        lines = pathlib.Path("pyproject.toml").read_text().splitlines()
        in_deps = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("dependencies") and "=" in stripped:
                in_deps = True
                continue
            if in_deps:
                if stripped == "]":
                    break
                dep = stripped.strip(",").strip('"').strip("'")
                if dep and dep != "[":
                    print(dep)
        sys.exit(0)
data = tomllib.loads(pathlib.Path("pyproject.toml").read_text())
for dep in data["project"]["dependencies"]:
    print(dep)
'@ | Set-Content -Path $pyScript -Encoding UTF8

Push-Location (Join-Path $ROOT "backend")
try {
    python $pyScript | Out-File -FilePath $depsFile -Encoding UTF8
} finally {
    Pop-Location
    Remove-Item -Force $pyScript -ErrorAction SilentlyContinue
}

# Windows: uvicorn[standard] includes uvloop which is Unix-only; strip extras
$reqFile = Join-Path $env:TEMP "roboscope-reqs-$([guid]::NewGuid().ToString('N').Substring(0,8)).txt"
(Get-Content $depsFile) -replace 'uvicorn\[standard\]', 'uvicorn' | Set-Content -Path $reqFile -Encoding UTF8

# pip writes warnings/progress to stderr; temporarily allow non-terminating errors
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"

# Download platform-specific binary wheels for multiple Python versions
foreach ($pyver in @("3.10", "3.11", "3.12", "3.13", "3.14")) {
    $abi = "cp$($pyver -replace '\.','')"
    Write-Host "    Downloading wheels for $WHEEL_PLATFORM (Python $pyver)..."
    python -m pip download `
        -r $reqFile `
        -d $wheelsDir `
        --platform $WHEEL_PLATFORM `
        --python-version $pyver `
        --implementation cp `
        --abi $abi `
        --only-binary :all: `
        2>&1 | Select-String -Pattern "error|saved" -CaseSensitive:$false | ForEach-Object { $_.Line }
}

# Download for host platform — this is the critical step!
# Running natively on Windows, pip correctly resolves sys_platform=='win32'
# markers, pulling in tzdata, colorama, and other Windows-conditional deps.
Write-Host "    Downloading wheels for host platform (native Windows resolution)..."
python -m pip download -r $reqFile -d $wheelsDir 2>&1 | ForEach-Object { "$_" } | Out-Null

# Ensure conditional transitive deps are included
Write-Host "    Downloading conditional dependencies..."
foreach ($pkg in @("tomli>=2.0.0", "exceptiongroup>=1.0.0", "typing_extensions>=4.0.0", "greenlet>=3.1.0")) {
    python -m pip download $pkg -d $wheelsDir --no-deps 2>&1 | ForEach-Object { "$_" } | Out-Null
}

$ErrorActionPreference = $oldEAP

# Save requirements for install scripts
Copy-Item -Force $reqFile (Join-Path $DIST "requirements.txt")
Remove-Item -Force $depsFile, $reqFile -ErrorAction SilentlyContinue

$wheelCount = (Get-ChildItem -Path $wheelsDir -Filter "*.whl").Count
Write-Host "    Wheels: $wheelCount packages"

# ── 5. Create .env template ──────────────────────────────────
@"
# RoboScope Configuration
# Copy this to .env and adjust as needed.

# Database (SQLite default — no setup required)
DATABASE_URL=sqlite:///./roboscope.db

# Secret key for JWT tokens (change in production!)
SECRET_KEY=CHANGE-ME-IN-PRODUCTION

# Server
HOST=0.0.0.0
PORT=8145
DEBUG=false

# Logging
LOG_LEVEL=INFO

# Directories (defaults shown — adjust if needed)
# WORKSPACE_DIR=~/.roboscope/workspace
# REPORTS_DIR=~/.roboscope/reports
# VENVS_DIR=~/.roboscope/venvs
"@ | Set-Content -Path (Join-Path $DIST ".env.example") -Encoding UTF8

# ── 6. Create Windows install/start/stop scripts ─────────────
@"
@echo off
echo ==> Installing RoboScope...

cd /d "%~dp0"

:: Create virtual environment with uv
uv-bin\uv-windows.exe venv .venv

:: Install dependencies offline
uv-bin\uv-windows.exe pip install --python .venv\Scripts\python.exe --no-index --find-links=wheels -r requirements.txt

if not exist .env copy .env.example .env

echo.
echo ==> RoboScope installed successfully!
echo     Start with: start-windows.bat
"@ | Set-Content -Path (Join-Path $DIST "install-windows.bat") -Encoding ASCII

@"
@echo off
cd /d "%~dp0"

:: Load port from .env if present
set PORT=8145
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if "%%a"=="PORT" set PORT=%%b
    )
)

:: Check if port is already in use
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo Error: Port %PORT% is already in use.
    echo.
    echo Process using port %PORT%:
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING"
    echo.
    echo Options:
    echo   1. Stop the other process:  stop-windows.bat
    echo   2. Change the port in .env: PORT=9000
    exit /b 1
)

if not exist .venv (
    echo Error: Run install-windows.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat

echo ==> Starting RoboScope...
echo     URL: http://localhost:%PORT%
echo     API: http://localhost:%PORT%/api/v1/docs
echo     Default login: admin@roboscope.local / admin123
echo.

python -m uvicorn src.main:app --host 0.0.0.0 --port %PORT%
"@ | Set-Content -Path (Join-Path $DIST "start-windows.bat") -Encoding ASCII

@"
@echo off
cd /d "%~dp0"

:: Load port from .env if present
set PORT=8145
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if "%%a"=="PORT" set PORT=%%b
    )
)

echo ==> Stopping RoboScope on port %PORT%...

set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo     Stopping PID %%p...
    taskkill /PID %%p /F >nul 2>&1
    set FOUND=1
)

if %FOUND%==0 (
    echo     No process found on port %PORT%.
) else (
    echo     RoboScope stopped.
)
"@ | Set-Content -Path (Join-Path $DIST "stop-windows.bat") -Encoding ASCII

# ── 7. Create ZIP ─────────────────────────────────────────────
Write-Host ""
Write-Host "==> Creating ZIP archive..."
$zipPath = Join-Path $ROOT "dist\$ZIP_NAME"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path $DIST -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "==> Build complete!"
Write-Host "    Distribution: $zipPath"
Write-Host "    Directory:    $DIST"
Write-Host ""
Write-Host "To deploy on Windows:"
Write-Host "  1. Extract $ZIP_NAME"
Write-Host "  2. Run install-windows.bat"
Write-Host "  3. Run start-windows.bat"
