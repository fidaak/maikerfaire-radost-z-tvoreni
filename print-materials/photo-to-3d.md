# Foto → 3D model

## Z fotografie k vytištěnému objektu pomocí AI

Experimentální pipeline: vyfotíte objekt mobilem a moderní AI (LLM) vygeneruje parametrický 3D model, který lze rovnou vytisknout.

---

### Jak to funguje?

1. **Fotografie** – vyfotíte jednoduchý objekt mobilem
2. **AI analýza** – LLM analyzuje tvar, rozměry a geometrii
3. **3D model** – AI vygeneruje parametrický model (OpenSCAD / CadQuery)
4. **Tisk** – model se naslicuje a vytiskne na Voron tiskárně

---

### Technologie

| Krok | Nástroj |
|------|---------|
| Vstup | Fotoaparát / mobil |
| Zpracování | LLM (velký jazykový model) |
| CAD výstup | OpenSCAD / CadQuery |
| Slicing | PrusaSlicer / OrcaSlicer |
| Tisk | Voron 2.4r2 / 0.2 |

---

### Stretch goal

Tento projekt je experimentální. Pokud se pipeline podaří dotáhnout, návštěvníci si budou moci vyfotit jednoduchý předmět a odnést si jeho 3D vytištěnou kopii.

---

**Matterhackers Radošov** · MakerFaire KV 2026

[QR KÓD – odkaz na web projektu]
