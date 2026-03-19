"""
Gradio visual search UI for the ~29k photo collection.
Uses CLIP ViT-L-14 text embeddings to search photos semantically.

Usage:
    uv pip install gradio
    .venv/Scripts/python app.py   # opens http://localhost:7860
"""

import os
import sqlite3
from pathlib import Path

import faiss
import gradio as gr
from PIL import Image

from search import get_device, get_image_info, load_clip_text, search_index, text_embedding

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).parent
DB_PATH = HERE / "photos.db"
FAISS_PATH = HERE / "photos.faiss"
MODEL_NAME = "ViT-L-14"

# ---------------------------------------------------------------------------
# Global resources (loaded once at startup)
# ---------------------------------------------------------------------------
_model = None
_tokenizer = None
_device = None
_index = None
_conn = None


def _load_resources() -> None:
    global _model, _tokenizer, _device, _index, _conn
    print(f"Device: ", end="", flush=True)
    _device = get_device()
    print(_device)
    print(f"Loading CLIP model {MODEL_NAME}...")
    _model, _tokenizer = load_clip_text(MODEL_NAME, _device)
    print(f"Loading FAISS index from {FAISS_PATH}...")
    _index = faiss.read_index(str(FAISS_PATH))
    # check_same_thread=False: Gradio uses threads, SQLite is read-only here
    _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    total = _conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    print(f"Ready — {total} images indexed.")


# ---------------------------------------------------------------------------
# Search function
# ---------------------------------------------------------------------------
def search(query: str, source: str, top_k: int, threshold: float, cols: int):
    if not query.strip():
        return gr.update(), "Zadej dotaz.", [], []

    vec = text_embedding(_model, _tokenizer, query.strip(), _device)

    # Over-fetch when filtering by source so we can fill top_k after filtering
    fetch_k = int(top_k) * 5 if source != "all" else int(top_k)
    ids, scores = search_index(_index, vec, fetch_k)

    results_data = []
    gallery_items = []
    paths = []
    for row_id, score in zip(ids, scores):
        if row_id < 0 or score < threshold:
            continue
        info = get_image_info(_conn, row_id)
        if not info:
            continue
        if source != "all" and info["source"] != source:
            continue
        path = Path(info["file_path"])
        if not path.exists():
            continue
        try:
            img = Image.open(path)
            img.thumbnail((800, 800))
            date = info["date_taken"][:10] if info["date_taken"] else "?"
            caption = f"#{len(gallery_items)+1} · {float(score):.3f} · {date} · {info['source']}"
            gallery_items.append((img, caption))
            paths.append(str(path))
            results_data.append({"image": img, "caption": caption, "path": str(path)})
        except Exception:
            pass
        if len(gallery_items) >= int(top_k):
            break

    if gallery_items:
        status = f"{len(gallery_items)} výsledků pro '{query}'"
    else:
        status = f"Žádné výsledky pro '{query}' (zkus jiný dotaz nebo snížit min. skóre)"

    return gr.update(value=gallery_items, columns=int(cols)), status, results_data, paths


# ---------------------------------------------------------------------------
# Redisplay — reflows gallery without re-running CLIP/FAISS
# ---------------------------------------------------------------------------
def redisplay(results_data: list, cols: int):
    if not results_data:
        return gr.update()
    gallery_items = [(r["image"], r["caption"]) for r in results_data]
    return gr.update(value=gallery_items, columns=int(cols))


# ---------------------------------------------------------------------------
# Native OS viewer
# ---------------------------------------------------------------------------
def open_in_viewer(evt: gr.SelectData, paths: list) -> str:
    if not paths or evt.index >= len(paths):
        return ""
    path = paths[evt.index]
    try:
        os.startfile(path)
        return f"Otevřeno: {Path(path).name}"
    except Exception as e:
        return f"Chyba: {e}"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Hledání fotek") as demo:
        gr.Markdown("## Hledání fotek — CLIP semantic search")

        results_state = gr.State([])
        paths_state = gr.State([])

        with gr.Row():
            query_box = gr.Textbox(
                label="Dotaz (anglicky)",
                placeholder="3D printer, birthday party, cat on sofa...",
                scale=4,
            )
            search_btn = gr.Button("Hledat", variant="primary", scale=1)

        with gr.Row():
            source_radio = gr.Radio(
                choices=["all", "google", "onedrive"],
                value="all",
                label="Zdroj",
            )
            top_k_slider = gr.Slider(5, 60, value=20, step=5, label="Počet výsledků")
            threshold_slider = gr.Slider(0.05, 0.40, value=0.15, step=0.01, label="Min. skóre")
            cols_slider = gr.Slider(2, 8, value=5, step=1, label="Sloupce")

        status_text = gr.Textbox(label="Status", interactive=False, max_lines=1)

        gallery = gr.Gallery(
            label="Výsledky",
            columns=5,
            object_fit="cover",
            height="auto",
        )

        viewer_status = gr.Textbox(label="Prohlížeč", interactive=False, max_lines=1)

        search_inputs = [query_box, source_radio, top_k_slider, threshold_slider, cols_slider]
        search_outputs = [gallery, status_text, results_state, paths_state]
        search_btn.click(fn=search, inputs=search_inputs, outputs=search_outputs)
        query_box.submit(fn=search, inputs=search_inputs, outputs=search_outputs)

        cols_slider.change(fn=redisplay, inputs=[results_state, cols_slider], outputs=[gallery])
        gallery.select(fn=open_in_viewer, inputs=[paths_state], outputs=[viewer_status])

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _load_resources()
    demo = build_ui()
    demo.launch(inbrowser=True)
