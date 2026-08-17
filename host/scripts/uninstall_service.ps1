#Requires -RunAsAdministrator
$ServiceName = "NimbusSeatHost"
Stop-Service $ServiceName -ErrorAction SilentlyContinue
nssm remove $ServiceName confirm
Write-Host "Service removed."
