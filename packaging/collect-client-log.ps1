<#
  collect-client-log.ps1
  Grabs the Realmweave Godot client log (Godot writes it to the user data dir),
  copies it into build/logs/ (gitignored, but easy to find/share), and - if the
  GitHub CLI is available - uploads it to a secret gist and copies the link.

  Usage:  powershell -ExecutionPolicy Bypass -File packaging\collect-client-log.ps1
          add  -Gist  to also upload to a GitHub gist.
#>
param([switch]$Gist)

$repo   = Split-Path -Parent $PSScriptRoot          # packaging\.. = repo root
$src    = Join-Path $env:APPDATA 'Godot\app_userdata\Realmweave\logs\godot.log'
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$outdir = Join-Path $repo 'build\logs'
New-Item -ItemType Directory -Force -Path $outdir | Out-Null
$dst    = Join-Path $outdir "client-$stamp.log"

if (-not (Test-Path $src)) {
  Write-Host "No client log found at:`n  $src`nRun the client at least once first." -ForegroundColor Yellow
  exit 1
}
Copy-Item -Force $src $dst
Write-Host "Saved client log -> $dst"

if ($Gist) {
  if (Get-Command gh -ErrorAction SilentlyContinue) {
    $url = gh gist create $dst --desc "Realmweave client log $stamp"
    if ($LASTEXITCODE -eq 0 -and $url) {
      Write-Host "Gist: $url"
      try { Set-Clipboard $url; Write-Host "(link copied to clipboard)" } catch {}
    } else {
      Write-Host "gh gist create failed - is gh authenticated? (gh auth login)" -ForegroundColor Yellow
    }
  } else {
    Write-Host "gh (GitHub CLI) not found; skipped gist upload. Log is at $dst" -ForegroundColor Yellow
  }
}
