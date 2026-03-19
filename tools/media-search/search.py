"""
Semantic search over indexed images using CLIP text queries.

Usage:
    python search.py "3D printer" [--db index.db] [--faiss index.faiss] [--top 20] [--threshold 0.2]
    python search.py "3D printer" --export assets/search-results
    python search.py --batch queries.txt --export assets/search-results
"""

import argparse
import csv
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import faiss
import numpy as np
import open_clip
import torch


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_clip_text(model_name: str, device: torch.device):
    model, _, _ = open_clip.create_model_and_transforms(
        model_name, pretrained="openai", device=device,
    )
    model.eval()
    tokenizer = open_clip.get_tokenizer(model_name)
    return model, tokenizer


def text_embedding(model, tokenizer, query: str, device: torch.device) -> np.ndarray:
    tokens = tokenizer([query]).to(device)
    with torch.no_grad(), torch.amp.autocast(device_type=device.type):
        features = model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().astype(np.float32)


def search_index(
    index: faiss.Index,
    query_vec: np.ndarray,
    top_k: int,
) -> tuple[list[int], list[float]]:
    scores, ids = index.search(query_vec, top_k)
    return ids[0].tolist(), scores[0].tolist()


def get_image_info(conn: sqlite3.Connection, row_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, file_path, source, date_taken, width, height, video_origin FROM images WHERE id = ?",
        (row_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "file_path": row[1],
        "source": row[2],
        "date_taken": row[3],
        "width": row[4],
        "height": row[5],
        "video_origin": row[6],
    }


def run_query(
    query: str,
    model,
    tokenizer,
    device: torch.device,
    index: faiss.Index,
    conn: sqlite3.Connection,
    top_k: int,
    threshold: float,
) -> list[dict]:
    vec = text_embedding(model, tokenizer, query, device)
    ids, scores = search_index(index, vec, top_k)
    results = []
    for row_id, score in zip(ids, scores):
        if row_id < 0 or score < threshold:
            continue
        info = get_image_info(conn, row_id)
        if info:
            info["score"] = float(score)
            results.append(info)
    return results


def sanitize_dirname(query: str) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in query).strip().replace(" ", "_")


def export_results(results: list[dict], query: str, export_dir: Path):
    query_dir = export_dir / sanitize_dirname(query)
    query_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = query_dir / "manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "score", "file_path", "source", "date_taken", "video_origin", "exported_as"])
        for rank, r in enumerate(results, 1):
            src = Path(r["file_path"])
            if not src.exists():
                writer.writerow([rank, f"{r['score']:.4f}", r["file_path"], r["source"], r["date_taken"], r["video_origin"], "MISSING"])
                continue
            dest_name = f"{rank:03d}_{src.name}"
            dest = query_dir / dest_name
            shutil.copy2(src, dest)
            writer.writerow([rank, f"{r['score']:.4f}", r["file_path"], r["source"], r["date_taken"], r["video_origin"], dest_name])

    print(f"  Exported {len(results)} files to {query_dir}")
    print(f"  Manifest: {manifest_path}")


def print_results(results: list[dict], query: str):
    print(f"\n{'='*60}")
    print(f"Query: \"{query}\" — {len(results)} results")
    print(f"{'='*60}")
    for i, r in enumerate(results, 1):
        origin = f" [from video: {Path(r['video_origin']).name}]" if r["video_origin"] else ""
        date = f" ({r['date_taken']})" if r["date_taken"] else ""
        print(f"  {i:3d}. [{r['score']:.3f}] {r['file_path']}{date}{origin}")


def main():
    parser = argparse.ArgumentParser(description="Semantic image search with CLIP")
    parser.add_argument("query", nargs="?", help="Text query (e.g. '3D printer')")
    parser.add_argument("--batch", help="File with one query per line (batch mode)")
    parser.add_argument("--db", default="index.db", help="SQLite database path")
    parser.add_argument("--faiss", default="index.faiss", help="FAISS index path")
    parser.add_argument("--top", type=int, default=20, help="Number of results (default: 20)")
    parser.add_argument("--threshold", type=float, default=0.15, help="Minimum similarity score (default: 0.15)")
    parser.add_argument("--export", help="Export matched files to this directory")
    parser.add_argument("--model", default="ViT-B-32", help="CLIP model name (must match indexing model)")
    args = parser.parse_args()

    if not args.query and not args.batch:
        parser.error("Provide a query or --batch file")

    if not os.path.exists(args.faiss):
        print(f"Error: FAISS index not found at {args.faiss}. Run index.py first.", file=sys.stderr)
        sys.exit(1)

    device = get_device()
    print(f"Device: {device}")
    print(f"Loading CLIP model {args.model}...")
    model, tokenizer = load_clip_text(args.model, device)

    index = faiss.read_index(args.faiss)
    conn = sqlite3.connect(args.db)
    total = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    print(f"Index contains {total} images")

    # Collect queries
    queries = []
    if args.batch:
        with open(args.batch, encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        queries = [args.query]

    export_dir = Path(args.export) if args.export else None
    if export_dir:
        export_dir.mkdir(parents=True, exist_ok=True)

    for query in queries:
        results = run_query(query, model, tokenizer, device, index, conn, args.top, args.threshold)
        print_results(results, query)
        if export_dir:
            export_results(results, query, export_dir)

    conn.close()


if __name__ == "__main__":
    main()
