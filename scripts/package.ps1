param(
  [string]$Output = "dist/twitch-local-exporter.zip",
  [string]$UnpackedOutput = "dist/unpacked/twitch-local-exporter"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist"
$Destination = Join-Path $Root $Output
$UnpackedDestination = Join-Path $Root $UnpackedOutput

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
if (Test-Path $Destination) {
  Remove-Item $Destination
}

$PackageItems = @(
  "manifest.json",
  "src",
  "popup",
  "options",
  "icons",
  "_locales"
)

$Paths = $PackageItems | ForEach-Object { Join-Path $Root $_ }

if (Test-Path $UnpackedDestination) {
  $ResolvedRoot = (Resolve-Path $Root).Path
  $ResolvedUnpacked = (Resolve-Path $UnpackedDestination).Path
  if (-not $ResolvedUnpacked.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove unpacked output outside workspace: $ResolvedUnpacked"
  }
  Remove-Item $UnpackedDestination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $UnpackedDestination | Out-Null
foreach ($Item in $PackageItems) {
  Copy-Item -Path (Join-Path $Root $Item) -Destination $UnpackedDestination -Recurse -Force
}

Compress-Archive -Path $Paths -DestinationPath $Destination -Force
Write-Host "Created $Destination"
Write-Host "Created $UnpackedDestination"
