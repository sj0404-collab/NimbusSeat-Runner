<#
.SYNOPSIS
    Install NimbusSeat host-manager as a Windows service via NSSM.
.NOTES
    Requires NSSM (https://nssm.cc) in PATH and Python 3.11+.
    Run as Administrator from the repository's host\ directory.
#>
#Requires -RunAsAdministrator

$ServiceName = "NimbusSeatHost"
$Python = (Get-Command python).Source
$HostDir = Split-Path -Parent $PSScriptRoot   # ...\host

nssm install $ServiceName $Python "-m" "nimbusseat_host" "run"
nssm set $ServiceName AppDirectory $HostDir
nssm set $ServiceName DisplayName "NimbusSeat Host Manager"
nssm set $ServiceName Description "Second gaming seat manager: Duo/Moonlight streaming, ASTER multiseat, 6h timer, LAN-only."
nssm set $ServiceName Start SERVICE_AUTO_START
nssm set $ServiceName AppStdout "$HostDir\logs\service.log"
nssm set $ServiceName AppStderr "$HostDir\logs\service.err.log"
New-Item -ItemType Directory -Force -Path "$HostDir\logs" | Out-Null

Start-Service $ServiceName
Write-Host "Service '$ServiceName' installed and started." -ForegroundColor Cyan
