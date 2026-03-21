# setup-hotspot.ps1
# Run as Administrator on MS-S1 MAX before the event.
# Overrides Windows ICS subnet to 192.168.0.x (matching home network)
# and applies firewall rules.

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

# ─── Configuration ────────────────────────────────────────────────────────────
# Match home network exactly so printers need no reconfiguration
$HotspotSSID     = "FMJL-IoT"
$GatewayIP       = "192.168.0.1"
$SubnetMask      = "255.255.255.0"
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "=== Booth Hotspot Setup ===" -ForegroundColor Cyan

# 1. Check adapter hosted-network support
Write-Host "`n[1/4] Checking WiFi adapter hosted-network support..." -ForegroundColor Yellow
netsh wlan show drivers | Select-String "Hosted network supported"

# 2. Override ICS subnet from 192.168.137.x → 192.168.0.x
Write-Host "`n[2/4] Overriding ICS subnet to $GatewayIP/$SubnetMask ..." -ForegroundColor Yellow

$svcName = "SharedAccess"
Stop-Service $svcName -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters"
Set-ItemProperty -Path $regPath -Name "ScopeAddress"     -Value $GatewayIP
Set-ItemProperty -Path $regPath -Name "ScopeAddressMask" -Value $SubnetMask

Start-Service $svcName
Start-Sleep -Seconds 2
Write-Host "ICS subnet set to $GatewayIP/$SubnetMask" -ForegroundColor Green

# 3. Set hotspot SSID via netsh (password must be set via Settings UI — netsh key is legacy)
Write-Host "`n[3/4] Configuring hotspot SSID..." -ForegroundColor Yellow
netsh wlan set hostednetwork mode=allow ssid=$HotspotSSID keyusage=persistent
Write-Host "SSID set to: $HotspotSSID" -ForegroundColor Green
Write-Host "Set the hotspot PASSWORD and BAND (2.4 GHz) via:" -ForegroundColor Yellow
Write-Host "  Settings > Network & internet > Mobile hotspot > Edit" -ForegroundColor Yellow

# 4. Firewall — block Moonraker API from venue WiFi (Public profile)
Write-Host "`n[4/4] Applying firewall rules..." -ForegroundColor Yellow
Remove-NetFirewallRule -DisplayName "Block Moonraker WAN" -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Block Moonraker WAN" `
    -Direction Inbound -Action Block -Protocol TCP `
    -LocalPort 7125,80 -Profile Public `
    -Description "Block Moonraker API from venue WiFi (WAN)"
Write-Host "Firewall rule applied." -ForegroundColor Green

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Settings > Mobile hotspot > Edit > set password + Band=2.4GHz > toggle ON"
Write-Host "  2. Verify: ipconfig should show hotspot adapter at $GatewayIP"
Write-Host "  3. Bridge hotspot virtual adapter + 10GbE Ethernet in ncpa.cpl"
Write-Host "  4. Connect T2UH to venue WiFi; set as 'Share from' source in hotspot settings"
Write-Host ""
Write-Host "Expected printer IPs:"
Write-Host "  Voron 0.2   -> 192.168.0.128  (WiFi, FMJL-IoT)"
Write-Host "  Voron 2.4r2 -> 192.168.0.100  (Ethernet, bridged)"
