$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

uv run android-telemetry-dock --serve-api --api-host 0.0.0.0 --api-port 8080 --api-token local-token --config config.yaml
