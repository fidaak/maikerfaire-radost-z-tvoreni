# Changelog — media-search

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
