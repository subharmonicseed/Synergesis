param(
    [int]$Port = 8051,
    [int]$ApiPort = 8181,
    [int]$AgentsPort = 8052,
    [string]$GitHubToken
)

$ErrorActionPreference = "Stop"

# Set environment for this session
$env:ARCHON_SERVER_PORT = "$ApiPort"
$env:ARCHON_MCP_PORT = "$Port"
$env:ARCHON_AGENTS_PORT = "$AgentsPort"
$env:PROJECTS_ENABLED = "true"
$env:ARCHON_ORIGIN = "http://localhost:$ApiPort"
# Avoid Unicode console issues on Windows
$env:PYTHONIOENCODING = "utf-8"

# Optionally set GitHub token for this session only
if ($GitHubToken) {
    $env:GITHUB_TOKEN = $GitHubToken
    Write-Host "Using provided GITHUB_TOKEN for this session." -ForegroundColor Yellow
} elseif ($env:GITHUB_TOKEN) {
    Write-Host "GITHUB_TOKEN detected in environment." -ForegroundColor Yellow
} else {
    Write-Host "No GITHUB_TOKEN set; GitHub tools will be limited to public data." -ForegroundColor Yellow
}

Write-Host "Starting Archon MCP server on port $Port..." -ForegroundColor Cyan

# Move to project python root
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

# Launch server
python -m src.mcp.mcp_server
