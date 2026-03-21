# MakerBooth Network — Linux Software Router Configuration

Complete configuration stack for running the MS-S1 MAX (AMD Strix Halo) as a
software router for the booth LAN at MakerFaire Karlovy Vary 2026.

## Topology

```
Internet (venue)
      |
  [venue AP]
      | WiFi (WPA2, DHCP client)
   wlan0  ← MT7925B (internal WiFi 7)   [WAN]
      |
  [MS-S1 MAX — Linux router]
      |
   br-lan  192.168.100.1/24             [LAN bridge]
   /  |  \
eth0  eth1  wlan1 (AP)
 |     |       |
Voron  switch  Voron 0.2
2.4r2  etc.    (WiFi, 2.4 GHz)
(.10)          (.11)
```

## File Map

```
network-config/
  wpa_supplicant/
    wpa_supplicant-wlan0.conf     WAN WiFi credentials
  systemd-networkd/
    10-wan.network                wlan0 DHCP client (WAN)
    20-br-lan.netdev              create br-lan bridge
    30-eth0.network               eth0 → br-lan slave
    30-eth1.network               eth1 → br-lan slave
    40-br-lan.network             br-lan static IP 192.168.100.1/24
  hostapd/
    hostapd.conf                  wlan1 AP (2.4 GHz, WPA2-PSK)
    hostapd-systemd-override.conf systemd drop-in for hostapd.service
  dnsmasq/
    dnsmasq.conf                  DHCP + DNS for br-lan
    resolved-no-stub.conf         disable systemd-resolved port 53
  nftables/
    nftables.conf                 firewall + NAT masquerade
  sysctl/
    99-router.conf                ip_forward + hardening
```

## Installation

### 1. Packages

```bash
apt install hostapd dnsmasq nftables wpasupplicant
# Disable NetworkManager if present (conflicts with systemd-networkd):
systemctl disable --now NetworkManager
systemctl enable --now systemd-networkd
```

### 2. RTL8812AU driver (TP-Link Archer T2UH)

**Kernel 6.14+**: no action needed; `rtw88_8812au` module loads automatically.

**Kernel < 6.14**: install out-of-tree DKMS driver:

```bash
apt install dkms build-essential linux-headers-$(uname -r)
git clone https://github.com/aircrack-ng/rtl8812au.git
cd rtl8812au
make dkms_install
# OR use morrownr's fork:
# git clone https://github.com/morrownr/8812au-20210820.git
# cd 8812au-20210820 && sudo ./install-driver.sh
```

Verify AP mode is available after driver load:
```bash
iw list | grep -A 20 "Supported interface modes"
# Must show "AP" in the list
```

### 3. systemd-networkd

```bash
cp network-config/systemd-networkd/*.network  /etc/systemd/network/
cp network-config/systemd-networkd/*.netdev   /etc/systemd/network/
systemctl restart systemd-networkd
networkctl status    # verify interfaces
```

### 4. wpa_supplicant (WAN WiFi client)

```bash
# Edit the config with actual venue SSID + passphrase:
cp network-config/wpa_supplicant/wpa_supplicant-wlan0.conf /etc/wpa_supplicant/
# Or generate with:
wpa_passphrase "VENUE_SSID" "passphrase" > /etc/wpa_supplicant/wpa_supplicant-wlan0.conf

systemctl enable --now wpa_supplicant@wlan0
# wpa_supplicant@wlan0.service reads /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
# systemd-networkd sees carrier on wlan0 once association succeeds,
# then applies DHCP from 10-wan.network
```

### 5. hostapd (2.4 GHz AP on wlan1)

```bash
# Review channel selection in hostapd.conf (default: channel=6)
cp network-config/hostapd/hostapd.conf /etc/hostapd/

# Install systemd override:
mkdir -p /etc/systemd/system/hostapd.service.d/
cp network-config/hostapd/hostapd-systemd-override.conf \
   /etc/systemd/system/hostapd.service.d/override.conf

# On Debian/Ubuntu also set DAEMON_CONF:
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd

systemctl daemon-reload
systemctl enable --now hostapd
```

### 6. dnsmasq

```bash
# Disable systemd-resolved stub listener first:
mkdir -p /etc/systemd/resolved.conf.d/
cp network-config/dnsmasq/resolved-no-stub.conf \
   /etc/systemd/resolved.conf.d/no-stub.conf
systemctl restart systemd-resolved

# Fix /etc/resolv.conf:
rm /etc/resolv.conf
ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf

# Install dnsmasq config:
cp network-config/dnsmasq/dnsmasq.conf /etc/dnsmasq.conf

# IMPORTANT: update the static lease MACs before copying:
# aa:bb:cc:dd:ee:01 → actual Voron 2.4r2 Ethernet MAC
# aa:bb:cc:dd:ee:02 → actual Voron 0.2 WiFi MAC

systemctl enable --now dnsmasq
```

### 7. nftables

```bash
cp network-config/nftables/nftables.conf /etc/nftables.conf
nft -f /etc/nftables.conf         # apply immediately
nft list ruleset                  # verify
systemctl enable --now nftables   # persist across reboots
```

### 8. sysctl (IP forwarding)

```bash
cp network-config/sysctl/99-router.conf /etc/sysctl.d/
sysctl -p /etc/sysctl.d/99-router.conf   # apply immediately
```

### 9. Service startup order

Correct order (handled by systemd dependencies):

1. `systemd-networkd` — creates br-lan bridge, configures eth0/eth1 slaves, brings up wlan0
2. `wpa_supplicant@wlan0` — associates to venue WiFi; networkd then runs DHCP on wlan0
3. `hostapd` — starts after br-lan exists; adds wlan1 to bridge
4. `dnsmasq` — starts after br-lan has its IP; listens on 192.168.100.1:53 and :67
5. `nftables` — loaded at boot; applies rules before any network traffic flows

---

## Key IP Assignments

| Host | Interface | IP | MAC (edit in dnsmasq.conf) |
|------|-----------|----|---------------------------|
| MS-S1 MAX (router) | br-lan | 192.168.100.1 | — |
| Voron 2.4r2 | eth0 or eth1 | 192.168.100.10 | aa:bb:cc:dd:ee:01 ← REPLACE |
| Voron 0.2 | wlan1 AP | 192.168.100.11 | aa:bb:cc:dd:ee:02 ← REPLACE |
| DHCP pool | any | 192.168.100.100–199 | dynamic |

## Troubleshooting

### Check interface state
```bash
networkctl list
networkctl status br-lan
ip addr show br-lan
ip route show
```

### Check wlan0 WAN association
```bash
wpa_cli -i wlan0 status
# state=COMPLETED means connected
```

### Check AP clients
```bash
iw dev wlan1 station dump
# Lists connected stations with signal strength
```

### Check DHCP leases
```bash
cat /var/lib/misc/dnsmasq.leases
# or via dnsmasq log:
journalctl -u dnsmasq -f
```

### Test NAT / internet
```bash
# From router:
ping -c3 1.1.1.1
# From a LAN client (if curl is available on Voron):
curl -s https://ipinfo.io/ip
```

### Check firewall
```bash
nft list ruleset
# Live packet counter:
nft list chain inet filter input
```

### hostapd debug
```bash
# Run foreground with verbose output:
hostapd -dd /etc/hostapd/hostapd.conf
```

### dnsmasq port conflict diagnosis
```bash
ss -tlnp | grep :53
# If you see systemd-resolved still on 127.0.0.53:53, check
# /etc/systemd/resolved.conf.d/no-stub.conf was applied.
```

## Offline operation

When venue WiFi is unavailable (wlan0 has no carrier):
- br-lan stays up at 192.168.100.1/24
- dnsmasq continues to serve DHCP + DNS to LAN clients
- hostapd continues to serve 2.4 GHz to Voron 0.2
- nftables masquerade rule is harmless (no traffic reaches wlan0)
- External DNS queries from LAN clients will fail (NXDOMAIN/timeout)
  — acceptable for printer operation (Klipper/Moonraker don't need internet)

## Security notes

- Change `wpa_passphrase` in hostapd.conf before the event
- Keep venue WiFi credentials in wpa_supplicant-wlan0.conf on-device only
- nftables drops all WAN→LAN new connections; printers not exposed to venue
- No SSH port is opened from WAN side (firewall input drops it)
- To allow SSH from WAN for remote management, add to nftables input chain:
  `iifname $WAN_IF tcp dport 22 accept` (not recommended at a public event)
