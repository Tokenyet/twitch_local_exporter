$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$IconDir = Join-Path $Root "icons"

New-Item -ItemType Directory -Force -Path $IconDir | Out-Null
Add-Type -AssemblyName System.Drawing

foreach ($Size in @(16, 32, 48, 128)) {
  $Bitmap = New-Object System.Drawing.Bitmap $Size, $Size
  $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
  $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

  $Background = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(15, 118, 110))
  $Accent = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 255, 255))
  $Shadow = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(38, 0, 0, 0))

  $Graphics.FillRectangle($Background, 0, 0, $Size, $Size)

  $Pad = [Math]::Max(2, [Math]::Round($Size * 0.18))
  $TriLeft = $Pad + [Math]::Round($Size * 0.12)
  $TriTop = $Pad
  $TriBottom = $Size - $Pad
  $TriRight = $Size - $Pad
  $Triangle = @(
    [System.Drawing.Point]::new($TriLeft + 1, $TriTop + 1),
    [System.Drawing.Point]::new($TriRight + 1, [Math]::Round($Size / 2) + 1),
    [System.Drawing.Point]::new($TriLeft + 1, $TriBottom + 1)
  )
  $Graphics.FillPolygon($Shadow, $Triangle)
  $Triangle = @(
    [System.Drawing.Point]::new($TriLeft, $TriTop),
    [System.Drawing.Point]::new($TriRight, [Math]::Round($Size / 2)),
    [System.Drawing.Point]::new($TriLeft, $TriBottom)
  )
  $Graphics.FillPolygon($Accent, $Triangle)

  $Path = Join-Path $IconDir "icon$Size.png"
  $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)

  $Graphics.Dispose()
  $Bitmap.Dispose()
  $Background.Dispose()
  $Accent.Dispose()
  $Shadow.Dispose()
}

Write-Host "Generated icons in $IconDir"
