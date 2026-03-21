# Voron 2.4r2 — Static IP via Ethernet

Static IP `192.168.0.100` already configured on the printer for home use.
No changes needed — the booth network uses the same `192.168.0.x` subnet.

## Verify current config on the printer

If running dhcpcd (Raspberry Pi OS / Debian):
```bash
cat /etc/dhcpcd.conf
# Should contain:
# interface eth0
# static ip_address=192.168.0.100/24
# static routers=192.168.0.1
```

If running NetworkManager:
```bash
nmcli con show --active
nmcli -f IP4 con show "Wired connection 1"
```

## If static IP is NOT set (using DHCP instead)

Fix with dhcpcd:
```
# /etc/dhcpcd.conf — append:
interface eth0
static ip_address=192.168.0.100/24
static routers=192.168.0.1
static domain_name_servers=1.1.1.1 8.8.8.8
```

Or NetworkManager:
```bash
nmcli con mod "Wired connection 1" \
  ipv4.method manual \
  ipv4.addresses 192.168.0.100/24 \
  ipv4.gateway 192.168.0.1 \
  ipv4.dns "1.1.1.1 8.8.8.8"
nmcli con up "Wired connection 1"
```

## Moonraker authorization (moonraker.conf)

```ini
[authorization]
trusted_clients:
    127.0.0.1
    192.168.0.0/24

[update_manager]
enable_auto_refresh: False
```

Restart: `sudo systemctl restart moonraker`

## Access URLs

| From | URL |
|------|-----|
| Phone / PC browser | http://192.168.0.100 |
| WSL2 | http://192.168.0.100 |
| Voron 0.2 | http://192.168.0.128 |
