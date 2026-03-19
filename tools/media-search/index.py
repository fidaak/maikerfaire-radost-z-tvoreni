"""
Index images (and extracted video keyframes) into a FAISS index with CLIP embeddings.

Usage:
    python index.py <folder> [--db index.db] [--faiss index.faiss] [--batch-size 64] [--model ViT-B-32]
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

import faiss
import numpy as np
import open_clip
import torch
import torch.utils.data
from PIL import Image, ExifTags
from tqdm import tqdm

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif"}
KEYFRAME_MARKER = "__keyframe__"  # substring present in paths produced by extract_frames.py

log = logging.getLogger("media-index")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stdout,
    )
    # Suppress noisy third-party loggers
    for noisy in ("PIL", "torch", "open_clip", "huggingface_hub", "timm",
                  "httpcore", "httpx", "urllib3", "filelock", "hf_xet"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_device() -> torch.device:
    if torch.cuda.is_available():
        dev = torch.device("cuda")
        props = torch.cuda.get_device_properties(0)
        log.info("GPU: %s  VRAM: %.1f GB  SM count: %d  Compute: %d.%d",
                 props.name, props.total_memory / 1e9, props.multi_processor_count,
                 props.major, props.minor)
        return dev
    log.warning("CUDA not available — running on CPU (will be slow)")
    return torch.device("cpu")


def init_db(db_path: str) -> sqlite3.Connection:
    log.debug("Opening DB: %s", db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            mtime REAL NOT NULL,
            source TEXT,
            date_taken TEXT,
            width INTEGER,
            height INTEGER,
            video_origin TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON images(file_path)")
    conn.commit()
    return conn


def get_indexed_files(conn: sqlite3.Connection) -> dict[str, float]:
    """Return {file_path: mtime} for already-indexed files."""
    rows = conn.execute("SELECT file_path, mtime FROM images").fetchall()
    log.debug("Loaded %d existing entries from DB", len(rows))
    return {r[0]: r[1] for r in rows}


def detect_source(file_path: str) -> str:
    p = file_path.lower()
    if "onedrive" in p:
        return "onedrive"
    if "takeout" in p or "google" in p:
        return "google"
    return "local"


def extract_exif_date(img: Image.Image) -> str | None:
    try:
        exif = img._getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, "")
                if tag == "DateTimeOriginal":
                    return str(value)
    except Exception:
        pass
    return None


def collect_images(folder: Path, indexed: dict[str, float]) -> list[Path]:
    """Walk folder, return image paths that are new or modified since last index."""
    log.info("Scanning %s ...", folder)
    t0 = time.time()
    total_seen = 0
    skipped_indexed = 0
    to_index = []

    for root, _dirs, files in os.walk(folder):
        for fname in files:
            if Path(fname).suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            total_seen += 1
            full = os.path.join(root, fname)
            mtime = os.path.getmtime(full)
            prev_mtime = indexed.get(full)
            if prev_mtime is not None and abs(mtime - prev_mtime) < 0.01:
                skipped_indexed += 1
                continue
            to_index.append(Path(full))

    elapsed = time.time() - t0
    log.info("Scan done in %.1fs: %d total, %d already indexed, %d to process",
             elapsed, total_seen, skipped_indexed, len(to_index))
    return to_index


class ImageDataset(torch.utils.data.Dataset):
    """Loads and preprocesses images; returns (tensor, original_index, ok_flag)."""
    def __init__(self, paths: list[Path], preprocess):
        self.paths = paths
        self.preprocess = preprocess

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        try:
            img = Image.open(self.paths[idx]).convert("RGB")
            tensor = self.preprocess(img)
            return tensor, idx, True
        except Exception:
            return torch.zeros(3, 224, 224), idx, False


def collate_fn(batch):
    tensors, indices, oks = zip(*batch)
    return torch.stack(tensors), list(indices), list(oks)


def load_clip(model_name: str, device: torch.device):
    log.info("Loading CLIP model %s (pretrained=openai) onto %s ...", model_name, device)
    t0 = time.time()
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained="openai", device=device,
    )
    model.eval()
    log.info("Model loaded in %.1fs", time.time() - t0)
    if device.type == "cuda":
        # Log GPU memory after model load
        alloc = torch.cuda.memory_allocated() / 1e6
        reserved = torch.cuda.memory_reserved() / 1e6
        log.debug("GPU memory after model load: %.0f MB allocated, %.0f MB reserved", alloc, reserved)
    return model, preprocess


def _gpu_stats() -> str:
    if not torch.cuda.is_available():
        return ""
    alloc = torch.cuda.memory_allocated() / 1e6
    reserved = torch.cuda.memory_reserved() / 1e6
    return f" | GPU mem: {alloc:.0f}/{reserved:.0f} MB"


def embed_images(
    paths: list[Path],
    model,
    preprocess,
    device: torch.device,
    batch_size: int,
    num_workers: int = 4,
) -> tuple[np.ndarray, list[int]]:
    """Return (embeddings [N, D], list of indices of failed images).

    Uses DataLoader with num_workers so CPU image loading overlaps GPU inference.
    """
    dataset = ImageDataset(paths, preprocess)
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
        prefetch_factor=2 if num_workers > 0 else None,
        pin_memory=(device.type == "cuda"),
        collate_fn=collate_fn,
        persistent_workers=(num_workers > 0),
    )

    n_batches = len(loader)
    log.info("Embedding %d images | batch=%d workers=%d pin_memory=%s",
             len(paths), batch_size, num_workers, device.type == "cuda")

    all_embeddings: list[np.ndarray] = []
    failed_indices: list[int] = []
    t_total = time.time()
    t_gpu_total = 0.0
    n_done = 0

    bar = tqdm(loader, desc="Embedding", unit="batch",
               bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")

    for batch_idx, (batch_tensor, indices, oks) in enumerate(bar):
        # Record failed images
        for idx, ok in zip(indices, oks):
            if not ok:
                failed_indices.append(idx)
                log.debug("Failed to load [%d] %s", idx, paths[idx].name)

        # Filter out failed (zero tensors)
        valid_mask = torch.tensor(oks, dtype=torch.bool)
        if not valid_mask.any():
            log.debug("Batch %d: all images failed", batch_idx)
            continue

        valid_tensor = batch_tensor[valid_mask]

        # GPU inference
        t_gpu = time.time()
        valid_tensor = valid_tensor.to(device, non_blocking=True)
        with torch.no_grad(), torch.amp.autocast(device_type=device.type):
            features = model.encode_image(valid_tensor)
            features = features / features.norm(dim=-1, keepdim=True)
        all_embeddings.append(features.cpu().numpy().astype(np.float32))
        t_gpu_total += time.time() - t_gpu

        n_done += valid_mask.sum().item()

        if (batch_idx + 1) % 10 == 0:
            elapsed = time.time() - t_total
            rate = n_done / max(elapsed, 0.01)
            eta_s = (len(paths) - n_done) / max(rate, 0.1)
            log.debug(
                "Batch %d/%d | %d/%d imgs | %.0f img/s | gpu %.1fs (%.0f%%)%s | ETA %.0fs",
                batch_idx + 1, n_batches, n_done, len(paths), rate,
                t_gpu_total, 100 * t_gpu_total / max(elapsed, 0.01),
                _gpu_stats(), eta_s,
            )

    elapsed = time.time() - t_total
    n_ok = len(paths) - len(failed_indices)
    log.info(
        "Embedding done: %d ok, %d failed | %.1fs | %.0f img/s | gpu %.1fs (%.0f%%)",
        n_ok, len(failed_indices), elapsed, n_ok / max(elapsed, 0.01),
        t_gpu_total, 100 * t_gpu_total / max(elapsed, 0.01),
    )

    if not all_embeddings:
        return np.empty((0, 512), dtype=np.float32), failed_indices
    return np.vstack(all_embeddings), failed_indices


def save_to_db(
    conn: sqlite3.Connection,
    paths: list[Path],
    failed_indices: set[int],
) -> list[int]:
    """Insert/update image metadata, return list of new row IDs in order (excluding failed)."""
    log.info("Saving metadata for %d images to DB ...", len(paths) - len(failed_indices))
    t0 = time.time()
    row_ids = []
    exif_ok = 0
    exif_fail = 0

    for i, p in enumerate(paths):
        if i in failed_indices:
            continue
        full = str(p)
        mtime = os.path.getmtime(full)
        source = detect_source(full)

        width, height, date_taken = None, None, None
        try:
            img = Image.open(p)
            width, height = img.size
            date_taken = extract_exif_date(img)
            if date_taken:
                exif_ok += 1
            else:
                exif_fail += 1
        except Exception as e:
            exif_fail += 1
            log.debug("Metadata read failed for %s: %s", p.name, e)

        video_origin = None
        if KEYFRAME_MARKER in full:
            video_origin = full.split(KEYFRAME_MARKER)[0]

        conn.execute("""
            INSERT INTO images (file_path, mtime, source, date_taken, width, height, video_origin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                mtime=excluded.mtime, source=excluded.source, date_taken=excluded.date_taken,
                width=excluded.width, height=excluded.height, video_origin=excluded.video_origin
        """, (full, mtime, source, date_taken, width, height, video_origin))

        row_id = conn.execute("SELECT id FROM images WHERE file_path = ?", (full,)).fetchone()[0]
        row_ids.append(row_id)

    conn.commit()
    log.info("DB save done in %.1fs | EXIF date found: %d, missing: %d",
             time.time() - t0, exif_ok, exif_fail)
    return row_ids


def build_faiss_index(
    faiss_path: str,
    new_embeddings: np.ndarray,
    new_ids: list[int],
    dimension: int,
):
    """Load existing FAISS index (if any) and add new embeddings with their DB row IDs."""
    if os.path.exists(faiss_path):
        log.info("Loading existing FAISS index from %s ...", faiss_path)
        index = faiss.read_index(faiss_path)
        log.debug("Existing index has %d vectors", index.ntotal)
    else:
        log.info("Creating new FAISS IndexFlatIP (dim=%d) ...", dimension)
        base = faiss.IndexFlatIP(dimension)
        index = faiss.IndexIDMap(base)

    if len(new_embeddings) > 0:
        log.info("Adding %d new embeddings to FAISS index ...", len(new_embeddings))
        ids_array = np.array(new_ids, dtype=np.int64)
        index.add_with_ids(new_embeddings, ids_array)

    log.info("Writing FAISS index (%d total vectors) to %s ...", index.ntotal, faiss_path)
    faiss.write_index(index, faiss_path)
    return index


def main():
    parser = argparse.ArgumentParser(description="Index images with CLIP embeddings")
    parser.add_argument("folder", help="Folder to scan for images")
    parser.add_argument("--db", default="index.db", help="SQLite database path (default: index.db)")
    parser.add_argument("--faiss", default="index.faiss", help="FAISS index path (default: index.faiss)")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size for CLIP encoding")
    parser.add_argument("--model", default="ViT-B-32", help="CLIP model name (default: ViT-B-32)")
    parser.add_argument("--workers", type=int, default=4, help="DataLoader worker processes for image loading (default: 4)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.verbose)
    log.info("=== media-index starting ===")
    log.info("Folder: %s | DB: %s | FAISS: %s | batch: %d | model: %s",
             args.folder, args.db, args.faiss, args.batch_size, args.model)

    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        log.error("Not a directory: %s", folder)
        sys.exit(1)

    device = get_device()

    conn = init_db(args.db)
    indexed = get_indexed_files(conn)
    log.info("Already indexed: %d images", len(indexed))

    to_index = collect_images(folder, indexed)
    if not to_index:
        log.info("Nothing to do — all images already indexed.")
        conn.close()
        return

    model, preprocess = load_clip(args.model, device)
    dim = model.visual.output_dim if hasattr(model.visual, "output_dim") else 512
    log.debug("Model output dim: %d", dim)

    t0 = time.time()
    embeddings, failed = embed_images(to_index, model, preprocess, device, args.batch_size, args.workers)
    failed_set = set(failed)

    row_ids = save_to_db(conn, to_index, failed_set)
    build_faiss_index(args.faiss, embeddings, row_ids, dim)

    total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    log.info("=== Done in %.1fs | Index now contains %d images ===", time.time() - t0, total)
    conn.close()


if __name__ == "__main__":
    main()
