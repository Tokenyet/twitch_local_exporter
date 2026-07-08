param(
  [string]$AppDir = (Join-Path $env:LOCALAPPDATA "TwitchLocalExporter"),
  [ValidateSet("tiny", "base", "small", "medium", "large")]
  [string]$WhisperModel = "small",
  [switch]$SkipFfmpeg,
  [switch]$SkipDeno,
  [switch]$SkipTwitchDownloader,
  [switch]$SkipWhisper
)

$ErrorActionPreference = "Stop"
$ToolsDir = Join-Path $AppDir "tools"
$ModelsDir = Join-Path $ToolsDir "models"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("twitch-local-exporter-tools-" + [Guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Force -Path $ToolsDir, $ModelsDir, $TempDir | Out-Null

function Download-File {
  param([string]$Url, [string]$Destination)
  Write-Host "Downloading $Url"
  Invoke-WithRetry -Action "download $Url" -Script {
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing | Out-Null
  }
}

function Invoke-WithRetry {
  param(
    [scriptblock]$Script,
    [string]$Action,
    [int]$Attempts = 3
  )

  for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
    try {
      return & $Script
    } catch {
      if ($Attempt -ge $Attempts) {
        throw
      }
      Write-Warning "$Action failed on attempt $Attempt of $Attempts. Retrying..."
      Start-Sleep -Seconds (2 * $Attempt)
    }
  }
}

function Read-ToolVersion {
  param(
    [string]$FilePath,
    [string[]]$Arguments = @("--version")
  )
  if (-not (Test-Path $FilePath)) {
    return ""
  }

  try {
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $FilePath
    $StartInfo.Arguments = ($Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join " "
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true

    $Process = [System.Diagnostics.Process]::Start($StartInfo)
    if (-not $Process.WaitForExit(10000)) {
      $Process.Kill()
      return ""
    }

    $Output = $Process.StandardOutput.ReadToEnd()
    if (-not $Output) {
      $Output = $Process.StandardError.ReadToEnd()
    }
    return ($Output -split "\r?\n" | Where-Object { $_.Trim() } | Select-Object -First 1).Trim()
  } catch {
    return ""
  }
}

function ConvertTo-CommandLineArgument {
  param([string]$Value)
  if ($Value -notmatch '[\s"]') {
    return $Value
  }
  $Escaped = $Value -replace '"', '\"'
  return '"' + $Escaped + '"'
}

try {
  $YtDlpPath = Join-Path $ToolsDir "yt-dlp.exe"
  Download-File "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" $YtDlpPath

  if (-not $SkipTwitchDownloader) {
    $Release = Invoke-WithRetry -Action "fetch TwitchDownloader release metadata" -Script {
      Invoke-RestMethod -Uri "https://api.github.com/repos/lay295/TwitchDownloader/releases/latest" -Headers @{ "User-Agent" = "twitch-local-exporter" }
    }
    $Asset = $Release.assets |
      Where-Object { $_.name -match "(?i)^TwitchDownloaderCLI-.*-Windows-x64\.zip$" } |
      Select-Object -First 1
    if (-not $Asset) {
      throw "Could not find a Windows x64 TwitchDownloaderCLI release asset."
    }
    $TwitchDownloaderZip = Join-Path $TempDir $Asset.name
    Download-File $Asset.browser_download_url $TwitchDownloaderZip
    $TwitchDownloaderExtract = Join-Path $TempDir "twitch-downloader"
    Expand-Archive -Path $TwitchDownloaderZip -DestinationPath $TwitchDownloaderExtract -Force
    $TwitchDownloaderExe = Get-ChildItem -Path $TwitchDownloaderExtract -Recurse -Filter TwitchDownloaderCLI.exe | Select-Object -First 1
    if (-not $TwitchDownloaderExe) {
      throw "Downloaded TwitchDownloaderCLI archive did not contain TwitchDownloaderCLI.exe"
    }
    Get-ChildItem -Path $TwitchDownloaderExe.Directory.FullName -File |
      Copy-Item -Destination $ToolsDir -Force
  }

  if (-not $SkipDeno) {
    $DenoZip = Join-Path $TempDir "deno.zip"
    Download-File "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip" $DenoZip
    $DenoExtract = Join-Path $TempDir "deno"
    Expand-Archive -Path $DenoZip -DestinationPath $DenoExtract -Force
    $DenoExe = Get-ChildItem -Path $DenoExtract -Recurse -Filter deno.exe | Select-Object -First 1
    if (-not $DenoExe) {
      throw "Downloaded Deno archive did not contain deno.exe"
    }
    Copy-Item $DenoExe.FullName (Join-Path $ToolsDir "deno.exe") -Force
  }

  if (-not $SkipFfmpeg) {
    $FfmpegZip = Join-Path $TempDir "ffmpeg.zip"
    Download-File "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $FfmpegZip
    $FfmpegExtract = Join-Path $TempDir "ffmpeg"
    Expand-Archive -Path $FfmpegZip -DestinationPath $FfmpegExtract -Force
    $FfmpegExe = Get-ChildItem -Path $FfmpegExtract -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    $FfprobeExe = Get-ChildItem -Path $FfmpegExtract -Recurse -Filter ffprobe.exe | Select-Object -First 1
    if (-not $FfmpegExe -or -not $FfprobeExe) {
      throw "Downloaded ffmpeg archive did not contain ffmpeg.exe and ffprobe.exe"
    }
    Copy-Item $FfmpegExe.FullName (Join-Path $ToolsDir "ffmpeg.exe") -Force
    Copy-Item $FfprobeExe.FullName (Join-Path $ToolsDir "ffprobe.exe") -Force
  }

  if (-not $SkipWhisper) {
    $Release = Invoke-WithRetry -Action "fetch whisper.cpp release metadata" -Script {
      Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest" -Headers @{ "User-Agent" = "twitch-local-exporter" }
    }
    $Asset = $Release.assets |
      Where-Object { $_.name -match "(?i)(win|windows).*(x64|amd64).*\.zip$|whisper.*bin.*x64.*\.zip$" } |
      Select-Object -First 1
    if ($Asset) {
      $WhisperZip = Join-Path $TempDir $Asset.name
      Download-File $Asset.browser_download_url $WhisperZip
      $WhisperExtract = Join-Path $TempDir "whisper"
      Expand-Archive -Path $WhisperZip -DestinationPath $WhisperExtract -Force
      $WhisperExe = Get-ChildItem -Path $WhisperExtract -Recurse -Filter whisper-cli.exe | Select-Object -First 1
      if ($WhisperExe) {
        Copy-Item $WhisperExe.FullName (Join-Path $ToolsDir "whisper-cli.exe") -Force
        Get-ChildItem -Path $WhisperExe.Directory.FullName -Filter *.dll | Copy-Item -Destination $ToolsDir -Force
      } else {
        Write-Warning "Could not find whisper-cli.exe in $($Asset.name)"
      }
    } else {
      Write-Warning "Could not find a Windows x64 whisper.cpp release asset."
    }

    $ModelPath = Join-Path $ModelsDir "ggml-$WhisperModel.bin"
    if (-not (Test-Path $ModelPath)) {
      Download-File "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$WhisperModel.bin" $ModelPath
    }
  }

  $Versions = [ordered]@{
    updatedAt = (Get-Date).ToString("o")
    ytDlp = Read-ToolVersion (Join-Path $ToolsDir "yt-dlp.exe")
    twitchDownloaderCli = Read-ToolVersion (Join-Path $ToolsDir "TwitchDownloaderCLI.exe")
    ffmpeg = Read-ToolVersion (Join-Path $ToolsDir "ffmpeg.exe") @("-version")
    deno = Read-ToolVersion (Join-Path $ToolsDir "deno.exe")
    whisperModel = "ggml-$WhisperModel.bin"
  }
  $Versions | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path (Join-Path $ToolsDir "versions.json")
  Write-Host "Tools installed in $ToolsDir"
} finally {
  if (Test-Path $TempDir) {
    Remove-Item -Path $TempDir -Recurse -Force
  }
}
