$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$platformTools = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools"
if (Test-Path $platformTools) {
    $env:PATH = "$platformTools;$env:PATH"
}

uv run android-telemetry-dock --config config.yaml
