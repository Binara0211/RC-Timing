param(
  [string]$Target = "C:\RC-Timing\rc_rock_crawling_timing_system"
)

$ErrorActionPreference = "Stop"
$Source = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
$Target = [System.IO.Path]::GetFullPath($Target)

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "RC ROCK CRAWLING TIMING SYSTEM - V2 UI UPGRADE" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Target: $Target"

if (-not (Test-Path $Target)) {
  throw "Existing installation not found at $Target"
}
if (-not (Test-Path (Join-Path $Target "run.py"))) {
  throw "Target does not look like the RC Timing project (run.py missing)."
}
if ($Source.TrimEnd('\') -eq $Target.TrimEnd('\')) {
  Write-Host "This is already the target project folder. No copy is required." -ForegroundColor Yellow
  Write-Host "Run scripts\LAUNCH_OPERATOR.bat to start V2."
  exit 0
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $Target ("upgrade_backup_" + $stamp)
New-Item -ItemType Directory -Path $backup -Force | Out-Null

# Preserve the working timing data and calibration by design.
$preserve = @("config", "data", "backups", "exports", "logs", "markers")
Write-Host "Preserving: config, database, backups, exports, logs and markers" -ForegroundColor Green

foreach ($item in @("app", "tests", "run.py", "requirements.txt", "VERSION.txt", "README.md", "DEPLOYMENT_GUIDE.md", "ARCHITECTURE.md", "QA_REPORT.md")) {
  $old = Join-Path $Target $item
  if (Test-Path $old) { Copy-Item $old -Destination $backup -Recurse -Force }
}

foreach ($dir in @("app", "tests")) {
  $dest = Join-Path $Target $dir
  if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
  Copy-Item (Join-Path $Source $dir) -Destination $Target -Recurse -Force
}

foreach ($file in @("run.py", "requirements.txt", "VERSION.txt", "README.md", "DEPLOYMENT_GUIDE.md", "ARCHITECTURE.md", "QA_REPORT.md", "CHANGELOG.md", "START_HERE.txt")) {
  $src = Join-Path $Source $file
  if (Test-Path $src) { Copy-Item $src -Destination (Join-Path $Target $file) -Force }
}

# Copy current scripts, but never touch persistent user data folders.
Copy-Item (Join-Path $Source "scripts\*") -Destination (Join-Path $Target "scripts") -Force

$py = Join-Path $Target ".venv\Scripts\python.exe"
if (Test-Path $py) {
  Write-Host "Updating Python dependencies (includes tzdata)..." -ForegroundColor Cyan
  & $py -m pip install -r (Join-Path $Target "requirements.txt")
  if ($LASTEXITCODE -ne 0) { throw "Dependency update failed." }
} else {
  Write-Host ".venv was not found. Run scripts\INSTALL_WINDOWS.bat once." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "UPGRADE COMPLETE" -ForegroundColor Green
Write-Host "Your existing config and rc_timing.db were preserved." -ForegroundColor Green
Write-Host "Backup of replaced UI/code files: $backup"
Write-Host "Start with: scripts\LAUNCH_OPERATOR.bat"
