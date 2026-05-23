$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root ".env.local"
$secure = Read-Host "Paste Zhihuiya MCP API key for local .env.local" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
}
finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($plain)) {
  throw "API key is empty."
}

$lines = @()
if (Test-Path -LiteralPath $target) {
  $lines = Get-Content -LiteralPath $target | Where-Object {
    $_ -notmatch '^ZHIHUIYA_MCP_API_KEY=' -and
    $_ -notmatch '^ZHIHUIYA_MCP_URL=' -and
    $_ -notmatch '^ZHIHUIYA_MCP_TIMEOUT=' -and
    $_ -notmatch '^ZHIHUIYA_MCP_DEFAULT_LIMIT='
  }
}

$lines += "ZHIHUIYA_MCP_URL=https://connect.zhihuiya.com/2b0355/logic-mcp"
$lines += "ZHIHUIYA_MCP_API_KEY=$plain"
$lines += "ZHIHUIYA_MCP_TIMEOUT=30"
$lines += "ZHIHUIYA_MCP_DEFAULT_LIMIT=10"

Set-Content -LiteralPath $target -Value $lines -Encoding UTF8
Write-Host "Saved local Zhihuiya MCP config to .env.local (ignored by git)."
