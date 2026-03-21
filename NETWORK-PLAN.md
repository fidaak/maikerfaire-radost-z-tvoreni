# Booth Network Setup — Windows Mobile Hotspot Plan

**Platform**: MS-S1 MAX running Windows 11 + WSL2 (dev environment unchanged)
**Strategy**: Mimic home network exactly — printers don't know they moved

---

## Key addresses

| Device | IP | Connection | Notes |
|--------|----|-----------|-------|
| **Voron 0.2** | `192.168.0.128` | 2.4 GHz WiFi | SSID: `FMJL-IoT`, WPA2, static IP |
| **Voron 2.4r2** | `192.168.0.100` | Ethernet | static IP |
| **MS-S1 MAX (gateway)** | `192.168.0.1` | — | ICS subnet override |
| **Phone** | DHCP | 2.4 GHz WiFi | same SSID |

**Hotspot SSID**: `FMJL-IoT` | **Band**: 2.4 GHz | **Security**: WPA2-AES

---

## Architecture

```
Venue WiFi (WAN, untrusted)
        │
        │ [Archer T2UH AC600 — station/client mode]
        │
  ┌─────┴──────────────────────────────────────────┐
  │           MS-S1 MAX (Windows 11)               │
  │   Windows Mobile Hotspot + ICS (NAT)           │
  │   Subnet overridden to 192.168.0.x             │
  │  [MT7925B — AP, 2.4 GHz]  [10GbE eth0]        │
  └──────────┬─────────────────────┬───────────────┘
             │                     │ (bridged)
     SSID: FMJL-IoT          Ethernet cable
     192.168.0.x              192.168.0.x
       • Voron 0.2 → .128       • Voron 2.4r2 → .100
       • Phone → DHCP
```

Offline-first: LAN works without venue internet. ICS only NATs outbound.

---

## Setup steps

### 1. Override ICS subnet to 192.168.0.x

Windows ICS defaults to `192.168.137.x`. Change it to match home via registry.
**Run `setup-hotspot.ps1` as Administrator** (handles this automatically), or manually:

```powershell
# PowerShell (Administrator)
Stop-Service SharedAccess -Force
$path = "HKLM:\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters"
Set-ItemProperty -Path $path -Name ScopeAddress    -Value "192.168.0.1"
Set-ItemProperty -Path $path -Name ScopeAddressMask -Value "255.255.255.0"
Start-Service SharedAccess
```

After this change, Mobile Hotspot will assign `192.168.0.x` addresses and the gateway will be `192.168.0.1`.

> **Important**: do this BEFORE enabling the hotspot. If you change it after, disable and re-enable the hotspot to force the new subnet.

### 2. Enable Mobile Hotspot

1. Settings → Network & internet → **Mobile hotspot**
2. **"Share my internet connection from"** → Archer T2UH (venue WiFi connection)
3. Click **Edit**:
   - Network name: `FMJL-IoT`
   - Password: same as home WiFi password
   - Band: **2.4 GHz**
4. Toggle **Mobile hotspot ON**

Check with `ipconfig` — the hotspot virtual adapter should show `192.168.0.1`.

### 3. Bridge Ethernet into hotspot LAN

So Voron 2.4r2 (wired) is on the same subnet:

1. `Win+R` → `ncpa.cpl`
2. Ctrl+click both: **Ethernet adapter (10GbE)** + **Local Area Connection\* N** (hotspot virtual adapter)
3. Right-click → **Bridge Connections** — wait ~1 min
4. Verify: after bridging, ping `192.168.0.100` from the host should reach Voron 2.4r2

> If Mobile Hotspot turns off after bridging: re-enable it in Settings.

### 4. Connect venue WiFi (WAN, optional)

1. Plug in Archer T2UH
2. Settings → Wi-Fi → connect to venue network → set **Public network**
3. In Mobile Hotspot settings: set "Share from" to the T2UH connection
4. Printers continue working whether or not this step succeeds

### 5. Moonraker config on each printer

In `moonraker.conf` (at `~/printer_data/config/moonraker.conf`):

```ini
[authorization]
trusted_clients:
    127.0.0.1
    192.168.0.0/24

[update_manager]
# Disable GitHub polling — booth may run offline
enable_auto_refresh: False
```

Restart: `sudo systemctl restart moonraker`

### 6. Access printers

| From | Voron 2.4r2 | Voron 0.2 |
|------|-------------|-----------|
| Browser (phone / PC) | `http://192.168.0.100` | `http://192.168.0.128` |
| mDNS (if hostname set) | `http://voron24.local` | `http://voron0.local` |
| WSL2 (mirrored mode) | same IPs | same IPs |

---

## Pre-event test procedure

**Test at home**, before the event. Goal: reproduce booth conditions on the home network.

### Phase 1 — Subnet + hotspot

1. Run `setup-hotspot.ps1` as Administrator
2. Enable Mobile Hotspot with SSID `FMJL-IoT`, 2.4 GHz, home WiFi password
3. Run `ipconfig` → confirm hotspot adapter shows `192.168.0.1 / 255.255.255.0`
4. Connect your **phone** to `FMJL-IoT` (it may briefly choose the home router signal instead — move to a different room if needed, or temporarily rename the home router's SSID)
5. Phone gets an IP in `192.168.0.x` from the hotspot DHCP

### Phase 2 — Ethernet bridge

6. Plug a short Cat6 cable from the MS-S1 MAX 10GbE port to Voron 2.4r2
7. Bridge the Ethernet adapter + hotspot virtual adapter in `ncpa.cpl`
8. On Voron 2.4r2: verify it still has static IP `192.168.0.100` and gateway `192.168.0.1`
9. From host: `ping 192.168.0.100` → should reply

### Phase 3 — Voron 0.2 WiFi

10. Power on Voron 0.2 — it will try to connect to `FMJL-IoT`
11. In a typical home setup the home router and the hotspot both broadcast `FMJL-IoT` — Voron 0.2 will connect to whichever is stronger
12. To force it to the hotspot: temporarily disable the `FMJL-IoT` SSID on the home router (or reduce its TX power), or move the Voron 0.2 close to the MS-S1 MAX
13. From host: `ping 192.168.0.128` → should reply

### Phase 4 — Mainsail / Moonraker

14. From phone (connected to hotspot): open `http://192.168.0.100` → Mainsail for Voron 2.4r2
15. From phone: open `http://192.168.0.128` → Mainsail for Voron 0.2
16. Send a `G28` home command via Mainsail — verify Klipper responds
17. From WSL2: `curl -s http://192.168.0.100/api/printer | head` → should return JSON

### Phase 5 — Offline test

18. Disconnect the MS-S1 MAX from venue/home WiFi entirely (turn off T2UH or forget the network)
19. Re-check: `ping 192.168.0.100` and `ping 192.168.0.128` still work
20. Mainsail still loads from phone — ✓ booth is offline-capable

### Phase 6 — Teardown + restore

21. Delete the bridge in `ncpa.cpl` (right-click bridge → Delete)
22. Re-enable the home router's `FMJL-IoT` SSID if you disabled it
23. Printers reconnect to home router automatically — no config changes needed

---

## Conflict risk at the venue

If the venue happens to have an open WiFi named `FMJL-IoT` (unlikely but worth checking): the printers would connect to that instead. Mitigation: before the event, scan for SSIDs and rename to something unique if there's a conflict.

---

## Security

- **Hotspot**: WPA2-AES (Windows Mobile Hotspot default). No WPA3 available on Windows hotspot as of 2025. Strong password sufficient.
- **Venue WiFi adapter (T2UH)**: Windows treats it as Public network — inbound connections blocked by default.
- **Printers**: `trusted_clients` in `moonraker.conf` restricted to `192.168.0.0/24`. No Moonraker port exposed on WAN adapter.
- **Offline risk surface**: when no venue WiFi is connected, there is no WAN interface at all — only the local LAN exists.

Explicit firewall rule to block Moonraker API from any Public (WAN) interface:

```powershell
New-NetFirewallRule -DisplayName "Block Moonraker WAN" `
    -Direction Inbound -Action Block -Protocol TCP `
    -LocalPort 7125,80 -Profile Public
```

---

## Hardware roles summary

| Adapter | Role | Why |
|---------|------|-----|
| **MT7925B** (internal PCIe WiFi 7) | Local AP — broadcasts `FMJL-IoT` hotspot | Best Windows hosted-network support; PCIe, not USB |
| **Archer T2UH AC600** (USB, MT7610U) | Venue WiFi WAN client | MT7610U has no reliable AP mode (Windows or Linux); excellent as STA |
| **10GbE eth0** | Wired LAN, bridged to hotspot | Voron 2.4r2 |

### Fallback: same-adapter STA+AP (MT7925B only)

If T2UH fails or venue WiFi unavailable:
- Connect MT7925B to venue WiFi → Windows 11 automatically creates virtual AP on same chip
- T2UH unplugged — unused

---

## Files in this repo

```
network-config/
  windows/
    setup-hotspot.ps1          Run as Administrator before event
    voron-wpa_supplicant.conf  Reference — Voron 0.2 already configured for FMJL-IoT
    voron-dhcpcd.conf          Reference — Voron 0.2 static IP config
    voron24r2-static-ip.md     Reference — Voron 2.4r2 static IP + Moonraker auth
    moonraker-booth.conf       Moonraker snippet: trusted_clients + disable update_manager
  linux/
    README.md                  Full bare-Linux router alternative (hostapd+dnsmasq+nftables)
    hostapd/ dnsmasq/ nftables/ sysctl/ systemd-networkd/ wpa_supplicant/
```
