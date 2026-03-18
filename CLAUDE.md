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
