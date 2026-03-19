# Media Search — CLIP Semantic Search Pipeline

Find photos and videos across Google Photos (Takeout) and OneDrive using natural language queries.
Built for curating MakerFaire KV 2026 booth materials.

## Setup

```bash
cd tools/media-search
uv venv
uv pip install -e .
# Or install directly:
uv pip install open-clip-torch torch torchvision faiss-cpu Pillow tqdm ffmpeg-python
```

Requires: Python 3.10+, ffmpeg on PATH (for video keyframe extraction).

## Quick Start

### 4. Web UI (recommended)

```bash
uv pip install gradio
.venv/Scripts/python app.py   # opens http://localhost:7860
```

### 1. Index your photos

All sources go into one shared index (`photos.db` + `photos.faiss`).
Each run is incremental — already-indexed files are skipped. Source (onedrive/google/local) is tracked in the DB.

```bash
# Index OneDrive photos
python index.py "D:\tmp\onedrive-obrazky\images" --db photos.db --faiss photos.faiss --model ViT-L-14 --workers 8

# Add Google Takeout on top (incremental — skips already-indexed files)
python index.py "D:\photos\google-takeout" --db photos.db --faiss photos.faiss --model ViT-L-14 --workers 8
```

### 2. Search

```bash
# Single query
python search.py "3D printer" --db photos.db --faiss photos.faiss --model ViT-L-14
python search.py "LEGO car" --db photos.db --faiss photos.faiss --model ViT-L-14 --top 30

# Export results (copies files + creates manifest.csv)
python search.py "Voron printer" --db photos.db --faiss photos.faiss --model ViT-L-14 --export ../../assets/search-results

# Batch search (one query per line)
python search.py --batch queries.txt --db photos.db --faiss photos.faiss --model ViT-L-14 --export ../../assets/search-results
```

### 3. Video keyframes (optional)

```bash
# Extract keyframes from videos
python extract_frames.py "D:\videos\maker" --output keyframes

# Then index the extracted frames
python index.py keyframes
```

## How It Works

1. **Index**: Scans image folders, generates CLIP (ViT-L-14) embeddings, stores in FAISS index + SQLite metadata DB
2. **Search**: Encodes your text query with CLIP, finds nearest neighbor images by cosine similarity
3. **Export**: Copies matched files to output folder with a manifest CSV linking back to originals

### Data files

- `photos.db` — SQLite with file paths, EXIF dates, dimensions, source (google/onedrive)
- `photos.faiss` — FAISS vector index mapping DB row IDs to CLIP embeddings

Both are gitignored. Re-run `index.py` to rebuild.

## Suggested Queries for MakerFaire

```
3D printer
Voron printer
3D print filament
LEGO car
RC car
remote control car
henna tattoo
henna painting
flexible mechanism
compliant mechanism
workshop
soldering iron
electronics project
maker workspace
```

## Performance

- ~3000 images/min on NVIDIA GPU with ViT-B-32
- ~200 images/min on CPU
- FAISS search is instant (<1ms for 100k images)
- Incremental indexing skips already-processed files
