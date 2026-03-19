# Changelog — media-search

## v0.4.0 — 2026-03-19

### Added
- Pagination: fetch up to 2000 candidates from FAISS per query; store all metadata (no PIL) in state; render one page at a time from disk on demand
- **← Zpět / Další →** navigation buttons in the status bar; disabled until first search
- Status line shows `Strana X / Y · Z výsledků`

### Changed
- `top_k` hard-cap slider removed; replaced by **"Na stránku"** (items per page, 10–60)
- Column resize now re-reads the current page from disk — no stale PIL cache
- All above-threshold results are always reachable through pagination

## v0.3.0 — 2026-03-19

### Added
- `app.py`: detail panel shown on gallery photo click
  - File path, source, date, dimensions
  - Keyword match table: 18 predefined MakerFaire-relevant English terms scored against the selected photo via CLIP cosine similarity; keyword embeddings pre-computed at startup (zero per-click overhead)
  - **"Otevřít v prohlížeči" button** — explicit user action; replaces previous auto-open behavior

### Changed
- `app.py`: gallery click no longer auto-opens the native viewer; `os.startfile` moved behind the explicit button
- `app.py`: compact control layout — source filter changed to `gr.Dropdown`, sliders use `min_width` caps, both status messages share one row, gallery label removed; ~180 px vertical space saved for the gallery

## v0.2.0 — 2026-03-19

### Added
- `app.py`: Gradio 6.9.0 web UI for semantic photo search
  - Text query input with source filter (all / google / onedrive)
  - Top-k and similarity threshold sliders
  - **Real-time column resize** (2–8 columns) — reflows gallery without re-running CLIP/FAISS
  - **Native OS viewer** — click any photo to open it in the system image viewer (`os.startfile`)
  - Status bar showing last opened filename

## v0.1.0 — 2026-03-18

### Added
- `index.py`: incremental FAISS indexer — scans image folders, generates CLIP embeddings, stores in FAISS + SQLite; skips already-indexed files
- `search.py`: CLI semantic search — text query → nearest-neighbor images by cosine similarity; supports single query, batch file, and `--export` to copy results with manifest CSV
- `extract_frames.py`: video keyframe extractor — uses ffmpeg to pull keyframes from video files for downstream indexing
