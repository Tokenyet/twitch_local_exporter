$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Entry = Join-Path $Root "native-host\twitch_local_exporter_host.py"
$Dist = Join-Path $Root "native-host\dist"
$Build = Join-Path $Root "native-host\build"
$PythonDeps = @("opencc-python-reimplemented>=0.1.7")

New-Item -ItemType Directory -Force -Path $Dist, $Build | Out-Null

$PyInstallerArgs = @(
  "--onefile",
  "--clean",
  "--collect-all", "opencc",
  "--name", "twitch-local-exporter-host",
  "--distpath", $Dist,
  "--workpath", $Build,
  "--specpath", $Build,
  $Entry
)

if (Get-Command uv -ErrorAction SilentlyContinue) {
  & uv tool run --with $PythonDeps pyinstaller @PyInstallerArgs
} else {
  python -m pip install --upgrade pyinstaller @PythonDeps
  python -m PyInstaller @PyInstallerArgs
}

Write-Host "Built native host in $Dist"
