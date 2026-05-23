$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root ".env.local"
$secure = Read-Host "Paste Patsnap/Eureka API key for local .env.local" -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
)

if ([string]::IsNullOrWhiteSpace($plain)) {
  throw "API key is empty."
}

$lines = @()
if (Test-Path -LiteralPath $target) {
  $lines = Get-Content -LiteralPath $target | Where-Object { $_ -notmatch '^PATSNAP_API_KEY=' }
}

$lines += "PATSNAP_API_KEY=$plain"
if (-not ($lines -match '^PATSNAP_BASE_URL=')) {
  $lines += "PATSNAP_BASE_URL=https://connect.patsnap.com"
}
if (-not ($lines -match '^PATSNAP_SEARCH_PATH=')) {
  $lines += "PATSNAP_SEARCH_PATH=/search/patent/nested-search-patent"
}
if (-not ($lines -match '^PATSNAP_COUNT_PATH=')) {
  $lines += "PATSNAP_COUNT_PATH=/search/patent/query-search-count"
}
if (-not ($lines -match '^PATSNAP_DEFAULT_LIMIT=')) {
  $lines += "PATSNAP_DEFAULT_LIMIT=10"
}

Set-Content -LiteralPath $target -Value $lines -Encoding UTF8
Write-Host "Saved local Patsnap key to .env.local (ignored by git)."
