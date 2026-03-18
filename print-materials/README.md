# Tiskové materiály – laminované A4

Tento adresář obsahuje podklady pro laminované informační listy A4, které budou vystaveny na stánku.

## Jak vygenerovat tisknutelné A4

### Varianta 1: Pandoc (doporučeno)

```bash
# Instalace pandoc (pokud nemáte)
# Windows: winget install JohnMacFarlane.Pandoc
# Linux: sudo apt install pandoc

# Generování PDF z markdown
pandoc voron.md -o voron.pdf --pdf-engine=wkhtmltopdf -V geometry:margin=2cm -V fontsize=12pt
```

### Varianta 2: VS Code

1. Otevřete `.md` soubor ve VS Code
2. Nainstalujte rozšíření **Markdown PDF**
3. Ctrl+Shift+P → "Markdown PDF: Export (pdf)"

### Varianta 3: Ruční tisk

1. Otevřete `.md` soubor v prohlížeči (např. přes GitHub)
2. Ctrl+P → Tisk do PDF
3. Nastavte okraje a velikost A4

## Doporučení pro laminování

- Tisk na bílý papír 80–100 g/m²
- Laminovací fólie 80 mic (matná vypadá lépe)
- Nechte okraj min. 5 mm kolem obsahu
- QR kódy: nahraďte placeholder text vygenerovaným QR kódem (min. 3×3 cm)

## Soubory

| Soubor | Projekt |
|--------|---------|
| `voron.md` | Voron 3D tiskárny |
| `rc-auto.md` | RC LEGO auto |
| `henna.md` | Henna malování |
| `compliant-models.md` | Compliant modely |
| `photo-to-3d.md` | Foto → 3D model |
