param(
  [string]$Version = "",
  [string]$OutputDir = "dist/release"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if (-not $Version) {
  $Manifest = Get-Content -Raw (Join-Path $Root "manifest.json") | ConvertFrom-Json
  $Version = $Manifest.version
}

$Version = $Version.Trim()
if (-not $Version) {
  throw "Version is required."
}

$Tag = if ($Version.StartsWith("v")) { $Version } else { "v$Version" }
$PlainVersion = $Tag.TrimStart("v")

$ManifestVersion = (Get-Content -Raw (Join-Path $Root "manifest.json") | ConvertFrom-Json).version
if ($ManifestVersion -ne $PlainVersion) {
  throw "manifest.json version $ManifestVersion does not match release version $PlainVersion."
}

$PyprojectText = Get-Content -Raw (Join-Path $Root "pyproject.toml")
$PyprojectMatch = [regex]::Match($PyprojectText, '(?m)^version\s*=\s*"([^"]+)"')
if ($PyprojectMatch.Success -and $PyprojectMatch.Groups[1].Value -ne $PlainVersion) {
  throw "pyproject.toml version $($PyprojectMatch.Groups[1].Value) does not match release version $PlainVersion."
}

$ReleaseDir = Join-Path $Root $OutputDir
$BundleName = "twitch-local-exporter-$Tag-windows"
$BundleRoot = Join-Path $ReleaseDir $BundleName
$UnpackedOutput = Join-Path $OutputDir "unpacked/twitch-local-exporter"
$ExtensionZip = Join-Path $ReleaseDir "twitch-local-exporter-extension-$Tag.zip"
$BundleZip = Join-Path $ReleaseDir "$BundleName.zip"
$HostExeSource = Join-Path $Root "native-host/dist/twitch-local-exporter-host.exe"
$HostExeAsset = Join-Path $ReleaseDir "twitch-local-exporter-host-$Tag-windows-x64.exe"

function Remove-SafeDirectory {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    return
  }

  $ResolvedRoot = (Resolve-Path $Root).Path
  $ResolvedPath = (Resolve-Path $Path).Path
  if (-not $ResolvedPath.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove directory outside workspace: $ResolvedPath"
  }
  Remove-Item -Path $Path -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Remove-SafeDirectory $BundleRoot
Remove-SafeDirectory (Join-Path $ReleaseDir "unpacked")

& (Join-Path $Root "scripts/package.ps1") -Output (Join-Path $OutputDir "twitch-local-exporter-extension-$Tag.zip") -UnpackedOutput $UnpackedOutput

New-Item -ItemType Directory -Force -Path $BundleRoot | Out-Null
Copy-Item -Path (Join-Path $Root $UnpackedOutput) -Destination (Join-Path $BundleRoot "extension") -Recurse -Force

New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot "native-host") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot "native-host/twitch_local_exporter") | Out-Null
Get-ChildItem -Path (Join-Path $Root "native-host/twitch_local_exporter") -File -Filter "*.py" |
  Copy-Item -Destination (Join-Path $BundleRoot "native-host/twitch_local_exporter") -Force
Copy-Item -Path (Join-Path $Root "native-host/twitch_local_exporter_host.py") -Destination (Join-Path $BundleRoot "native-host/twitch_local_exporter_host.py") -Force

if (Test-Path $HostExeSource) {
  New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot "native-host/dist") | Out-Null
  Copy-Item -Path $HostExeSource -Destination (Join-Path $BundleRoot "native-host/dist/twitch-local-exporter-host.exe") -Force
  Copy-Item -Path $HostExeSource -Destination $HostExeAsset -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot "scripts") | Out-Null
foreach ($Script in @("install-native.ps1", "uninstall-native.ps1", "update-tools.ps1", "build-native.ps1")) {
  Copy-Item -Path (Join-Path $Root "scripts/$Script") -Destination (Join-Path $BundleRoot "scripts/$Script") -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot "docs") | Out-Null
foreach ($Doc in @("PRIVACY.md", "NATIVE_HOST.md", "RELEASE_INSTALL.md")) {
  Copy-Item -Path (Join-Path $Root "docs/$Doc") -Destination (Join-Path $BundleRoot "docs/$Doc") -Force
}
foreach ($File in @("README.md", "CHANGELOG.md", "LICENSE", "manifest.json", "pyproject.toml")) {
  Copy-Item -Path (Join-Path $Root $File) -Destination (Join-Path $BundleRoot $File) -Force
}

if (Test-Path $BundleZip) {
  Remove-Item $BundleZip -Force
}
Compress-Archive -Path $BundleRoot -DestinationPath $BundleZip -Force

$ChangelogPath = Join-Path $Root "CHANGELOG.md"
$Changelog = Get-Content -Raw $ChangelogPath
$EscapedVersion = [regex]::Escape($PlainVersion)
$Match = [regex]::Match($Changelog, "(?ms)^##\s+$EscapedVersion[^\r\n]*\r?\n.*?(?=^##\s+|\z)")
$VersionNotes = if ($Match.Success) { $Match.Value.Trim() } else { "## $PlainVersion`n`nSee CHANGELOG.md for release details." }
$InstallNotes = Get-Content -Raw (Join-Path $Root "docs/RELEASE_INSTALL.md")
$ReleaseNotes = @"
# Twitch Local Exporter $Tag

$VersionNotes

## Install From This Release

$InstallNotes
"@
$ReleaseNotes | Set-Content -Encoding UTF8 -Path (Join-Path $ReleaseDir "RELEASE_NOTES.md")

$Artifacts = @($ExtensionZip, $BundleZip)
if (Test-Path $HostExeAsset) {
  $Artifacts += $HostExeAsset
}

$ChecksumLines = foreach ($Artifact in $Artifacts) {
  $Hash = Get-FileHash -Algorithm SHA256 -Path $Artifact
  "$($Hash.Hash.ToLowerInvariant())  $([System.IO.Path]::GetFileName($Artifact))"
}
$ChecksumLines | Set-Content -Encoding ASCII -Path (Join-Path $ReleaseDir "SHA256SUMS.txt")

$ReleaseManifest = [ordered]@{
  version = $PlainVersion
  tag = $Tag
  generatedAt = (Get-Date).ToUniversalTime().ToString("o")
  assets = $Artifacts | ForEach-Object { [System.IO.Path]::GetFileName($_) }
}
$ReleaseManifest | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path (Join-Path $ReleaseDir "release-manifest.json")

Write-Host "Created release assets in $ReleaseDir"
