<#
.SYNOPSIS
    NimbusSeat-Runner: restrict Duo/Moonlight and manager ports to LAN only.
.DESCRIPTION
    Creates Windows Firewall rules that allow the streaming and API ports
    ONLY from private LAN subnets and block everything else.
    Run once as Administrator:
        powershell -ExecutionPolicy Bypass -File setup_firewall_lan_only.ps1
#>
#Requires -RunAsAdministrator

$LanSubnets = @("192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12")

# Duo (Apollo/Sunshine fork) Moonlight ports + NimbusSeat API/discovery
$TcpPorts = @(47984, 47989, 47990, 48010, 48120)
$UdpPorts = @(47998, 47999, 48000, 48002, 48121)

$Prefix = "NimbusSeat"

Write-Host "Removing old $Prefix rules..." -ForegroundColor Yellow
Get-NetFirewallRule -DisplayName "$Prefix*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule

Write-Host "Allowing TCP $($TcpPorts -join ', ') from LAN..." -ForegroundColor Green
New-NetFirewallRule -DisplayName "$Prefix Allow TCP LAN" -Direction Inbound `
    -Protocol TCP -LocalPort $TcpPorts -RemoteAddress $LanSubnets -Action Allow | Out-Null

Write-Host "Allowing UDP $($UdpPorts -join ', ') from LAN..." -ForegroundColor Green
New-NetFirewallRule -DisplayName "$Prefix Allow UDP LAN" -Direction Inbound `
    -Protocol UDP -LocalPort $UdpPorts -RemoteAddress $LanSubnets -Action Allow | Out-Null

Write-Host "Blocking the same ports from anywhere else..." -ForegroundColor Green
New-NetFirewallRule -DisplayName "$Prefix Block TCP WAN" -Direction Inbound `
    -Protocol TCP -LocalPort $TcpPorts -Action Block | Out-Null
New-NetFirewallRule -DisplayName "$Prefix Block UDP WAN" -Direction Inbound `
    -Protocol UDP -LocalPort $UdpPorts -Action Block | Out-Null

Write-Host "Done. Streaming is now LAN-only." -ForegroundColor Cyan
Write-Host "Reminder: do NOT enable UPnP or port forwarding for these ports."
