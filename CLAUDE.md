# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Central knowledge base and action hub for **MakerFaire Karlovy Vary 2026** booth: "Matterhackers Radošov: Radost z tvoření". Family maker team (Filip Novotný + family) presenting 3D printing, RC car, henna art, and more. Booth annotation: https://makerfaire.cz/projekt/matterhackers-radosov-radost-z-tvoreni/

Primary language for all content: **Czech**. Code comments and technical docs may be in English.

## Repository Structure

```
preparation/       Event logistics: checklists, packing list, timeline
web/               Static site presentation (HTML/CSS, no build system)
  index.html       Landing page with project cards
  projects/        Individual sub-project detail pages
  styles.css       Shared CSS (dark theme, amber/orange accents)
print-materials/   Markdown sources for laminated A4 info sheets with QR codes
subprojects/       Links and notes connecting to external specialized repos
assets/            Photos, QR codes, logos, 3D models (mostly .gitkeep placeholders)
```

## Sub-projects

| ID | Name | Status | Notes |
|----|------|--------|-------|
| voron | Voron 3D tiskárny (2.4r2, 0.2) | Working | CoreXY, Klipper firmware |
| rc-auto | RC LEGO auto | **BROKEN** | Modified firmware, drone motor hubs - needs repair |
| henna | Henna malování na kůži | Planned | Daughter's booth |
| compliant-models | Compliant 3D printed mechanisms | Planned | Print-in-place flexible geometry |
| photo-to-3d | Photo → parametric 3D model via LLM | Stretch goal | Pipeline not yet built |

## Web Presentation

- Pure static HTML/CSS, no framework, no build step
- Design: dark background (`--gray-950`), amber/orange accent palette (`--amber-*`, `--orange-*`)
- CSS uses custom properties defined in `web/styles.css :root`
- Responsive: mobile breakpoint at 640px
- To preview: open `web/index.html` directly in browser
- Deployment: TBD (likely GitHub Pages or similar static host)
- Each sub-project has a detail page at `web/projects/{id}.html` using shared styles

## Print Materials

- Each sub-project has a markdown file in `print-materials/` intended for A4 laminated sheets
- Include QR code placeholders linking to corresponding web pages
- Generate PDFs via pandoc: `pandoc {file}.md -o {file}.pdf --pdf-engine=wkhtmltopdf`

## Key Conventions

- Checklists use markdown checkboxes (`- [ ]`)
- Sub-project IDs are consistent across dirs: `voron`, `rc-auto`, `henna`, `compliant-models`, `photo-to-3d`
- 3D model files (`.stl`, `.step`, `.3mf`, `.obj`) and gcode are gitignored - use Git LFS if needed
- External specialized repos (RC car build, printer configs, OpenSCAD models) are referenced from `subprojects/README.md`, not duplicated here

## Cross-repo Integration

This repo coordinates with specialized repos (paths TBD):
- RC auto buildup repo
- 3D printer configs/mods
- OpenSCAD 3D modelling

When working on sub-project-specific code/hardware configs, check `subprojects/README.md` for the dedicated repo first. This repo owns: preparation logistics, web presentation, print materials, and overall coordination.

---

## Worktree: Booth Network Setup

**This worktree (`worktree-network-setup`) is scoped to planning and configuring the booth LAN** — secure local network for 3D printers, mini PC, and optional venue internet uplink.

### Hardware inventory

| Device | Network interface | Notes |
|--------|-------------------|-------|
| **Minisforum MS-S1 MAX** (AMD Strix Halo) | 2× 10GbE RJ45 (RTL8127), WiFi 7 (MT7925B), BT 5.4 | Main compute node; could double as software router |
| **Voron 2.4r2** (Klipper) | Ethernet (cable) | Must be on the local LAN |
| **Voron 0.2** (Klipper) | 2.4 GHz WiFi only | Needs a local AP broadcasting 2.4 GHz |
| Venue uplink | Ethernet drop or WiFi (TBD) | May not be available; plan for offline operation |

### Network architecture options (to be decided)

1. **Travel router (GL.iNet GL-MT3000 or similar)** + small unmanaged switch — dedicated network appliance, simplest day-of setup, independent of mini PC state
2. **MS-S1 MAX as Linux software router** — hostapd AP + dnsmasq DHCP + nftables NAT; no extra hardware, but couples network to the compute node
3. **Hybrid** — travel router for uplink/WiFi AP, mini PC wired directly to printers via its dual 10GbE ports

### Key requirements

- **Local LAN always works** — printers must be reachable from the mini PC regardless of venue internet
- **2.4 GHz WiFi AP** — required for Voron 0.2; must be reliable in a crowded 2.4 GHz venue environment
- **Security** — WPA2/3 on WiFi, no open ports to venue network, firewall between WAN and LAN
- **Portability** — everything fits in a bag, minimal cable mess, fast setup at the venue
- **Offline-capable** — the booth network must function without any venue uplink

### In scope

- Network topology design and documentation
- Hardware shopping list / packing checklist
- Linux network configuration (if using MS-S1 MAX as router): hostapd, dnsmasq, nftables, systemd-networkd
- Travel router configuration (if using GL.iNet): OpenWrt settings, SSID/password, DHCP reservations
- Klipper/Moonraker network requirements for both Vorons
- Security hardening (firewall rules, WiFi encryption, isolating WAN from LAN)

### Out of scope

- Web presentation (`web/`) — separate worktree
- Print materials, event logistics
- Klipper firmware or printer hardware (only network connectivity aspects)
- Sub-project repos (RC car, OpenSCAD models)
