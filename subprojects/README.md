# Sub-projekty

Tento repozitář slouží jako **centrální koordinační bod** pro MakerFaire KV 2026. Jednotlivé technické sub-projekty mají (nebo budou mít) vlastní specializované repozitáře.

## Struktura

| Sub-projekt | Repozitář | Stav |
|-------------|-----------|------|
| Voron 3D tiskárny | `TBD` | Placeholder |
| RC LEGO auto | `TBD` | Placeholder |
| Henna malování | – (nepotřebuje repo) | – |
| Compliant modely | `TBD` | Placeholder |
| Photo → 3D model | `TBD` | Placeholder |

## Jak to souvisí

```
makerfaire-radost-z-tvoreni/     ← tento repozitář (koordinace, web, příprava)
├── subprojects/                 ← odkazy na dílčí repozitáře
│
├── voron-config/                ← (externí repo) konfigurace tiskáren
├── rc-lego-car/                 ← (externí repo) firmware a dokumentace RC auta
├── compliant-models/            ← (externí repo) CAD soubory modelů
└── photo-to-3d-pipeline/        ← (externí repo) AI pipeline kód
```

## Co patří kam

### Tento repozitář (makerfaire-radost-z-tvoreni)
- Webová prezentace
- Tiskové materiály (laminované A4)
- Checklisty, packing list, timeline
- Fotky a loga
- Koordinace celého projektu

### Externí repozitáře
- Zdrojový kód a konfigurace jednotlivých projektů
- CAD soubory a modely
- Firmware
- Technická dokumentace specifická pro daný sub-projekt

## Přidání nového sub-projektu

1. Vytvořte nový repozitář pro sub-projekt
2. Aktualizujte tabulku výše s odkazem
3. Přidejte stránku do `web/projects/`
4. Přidejte tiskový materiál do `print-materials/`
5. Aktualizujte master checklist v `preparation/checklist.md`
