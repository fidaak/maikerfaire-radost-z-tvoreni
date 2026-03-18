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

## Worktree: Web Presentation

**This worktree (`worktree-web-presentation`) is scoped to the web presentation** — everything under `web/`.

### Current state

| File | Purpose |
|------|---------|
| `web/index.html` | Landing page with project cards |
| `web/styles.css` | Shared CSS (custom properties, dark theme, responsive) |
| `web/projects/voron.html` | Voron 3D printers detail page |
| `web/projects/rc-auto.html` | RC LEGO car detail page |
| `web/projects/henna.html` | Henna art detail page |
| `web/projects/compliant-models.html` | Compliant mechanisms detail page |
| `web/projects/photo-to-3d.html` | Photo-to-3D pipeline detail page |

### Key conventions (web)

- **Pure static HTML/CSS** — no framework, no bundler, no build step
- **Dark theme**: background `--gray-950`, amber/orange accent palette (`--amber-*`, `--orange-*`)
- **Custom properties** in `web/styles.css :root`
- **Responsive**: mobile breakpoint at 640 px
- **Czech content** — all user-facing text is in Czech
- Preview by opening `web/index.html` directly in a browser

### In scope

- HTML pages and structure (`web/`)
- CSS styling, layout, responsiveness (`web/styles.css`)
- Adding/editing project detail pages (`web/projects/*.html`)
- Image and asset references used by the site

### Out of scope

- Print materials (`print-materials/`) — separate worktree / main branch
- Event preparation and logistics (`preparation/`)
- Sub-project hardware, firmware, configs (`subprojects/`)
- Deployment infrastructure (not yet decided)
