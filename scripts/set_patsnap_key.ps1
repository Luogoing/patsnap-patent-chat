$ErrorActionPreference = "Stop"

Write-Host "This project now uses Zhihuiya MCP as the main channel."
& (Join-Path $PSScriptRoot "set_zhihuiya_mcp_key.ps1")
