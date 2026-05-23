$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root ".env.local"
$secure = Read-Host "Paste Zhihuiya MCP API key or full MCP link for local .env.local" -AsSecureString
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

if ($plain -match '[?&]apikey=([^&]+)') {
  $plain = [Uri]::UnescapeDataString($Matches[1])
}

if ($plain -notmatch '^sk') {
  Write-Warning "Input does not look like a Zhihuiya API key after parsing. It will still be saved, but authentication may fail."
}

$lines = @()
if (Test-Path -LiteralPath $target) {
  $lines = Get-Content -LiteralPath $target | Where-Object {
    $_ -notmatch '^ZHIHUIYA_MCP_API_KEY=' -and
    $_ -notmatch '^ZHIHUIYA_MCP_URL=' -and
    $_ -notmatch '^ZHIHUIYA_MCP_TIMEOUT=' -and
    $_ -notmatch '^ZHIHUIYA_MCP_DEFAULT_LIMIT=' -and
    $_ -notmatch '^ZHIHUIYA_NOVELTY_MCP_URL=' -and
    $_ -notmatch '^ZHIHUIYA_NOVELTY_MCP_API_KEY='
  }
}

$lines += "ZHIHUIYA_MCP_URL=https://connect.zhihuiya.com/2b0355/logic-mcp"
$lines += "ZHIHUIYA_MCP_API_KEY=$plain"
$lines += "ZHIHUIYA_MCP_TIMEOUT=30"
$lines += "ZHIHUIYA_MCP_DEFAULT_LIMIT=10"
$lines += "ZHIHUIYA_NOVELTY_MCP_URL=https://connect.zhihuiya.com/bec69d/mcp"
$lines += "ZHIHUIYA_NOVELTY_MCP_API_KEY=$plain"

Set-Content -LiteralPath $target -Value $lines -Encoding UTF8
Write-Host "Saved local Zhihuiya MCP config to .env.local (ignored by git)."
