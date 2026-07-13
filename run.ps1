param(
  [int]$Port = 0,   # 0 means: read from .env or fallback to 8766
  [string]$HostName = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# ── Read .env if present ──────────────────────────────────────
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
      $key = $Matches[1].Trim()
      $val = $Matches[2].Trim()
      if (-not [Environment]::GetEnvironmentVariable($key)) {
        [Environment]::SetEnvironmentVariable($key, $val, "Process")
      }
    }
  }
}

# ── Defaults ──────────────────────────────────────────────────
if (-not $HostName) { $HostName = [Environment]::GetEnvironmentVariable("SOUNDAO_HOST") || "127.0.0.1" }
if ($Port -eq 0) { $Port = [int]([Environment]::GetEnvironmentVariable("SOUNDAO_PORT") || "8766") }

# ── Delegate to restart_services.py ───────────────────────────
# It kills any stale server.py / agent_loop.py and starts both
# (server + agent_loop) in one shot.  This is the only supported
# way to bring the project up.  See AGENTS.md step 5.
$Python = $null
if (Test-Path (Join-Path $Root ".venv\Scripts\python.exe")) {
  $Python = Join-Path $Root ".venv\Scripts\python.exe"
} else {
  $Python = "python"
}
& $Python (Join-Path $Root "restart_services.py")
