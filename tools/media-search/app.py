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
import numpy as np
from PIL import Image

from search import get_device, get_image_info, load_clip_text, search_index, text_embedding

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).parent
DB_PATH = HERE / "photos.db"
FAISS_PATH = HERE / "photos.faiss"
MODEL_NAME = "ViT-L-14"

PREDEFINED_KEYWORDS = [
    "3D printer",
    "Voron 3D printer",
    "3D printing filament",
    "CoreXY printer",
    "LEGO car",
    "RC car remote control",
    "drone motor",
    "henna tattoo art",
    "henna painting hands",
    "compliant mechanism",
    "flexible 3D print",
    "maker workshop",
    "soldering electronics",
    "children crafting",
    "family maker project",
    "FDM print in progress",
    "Klipper firmware screen",
    "maker fair exhibition booth",
]

# ---------------------------------------------------------------------------
# Global resources (loaded once at startup)
# ---------------------------------------------------------------------------
_model = None
_tokenizer = None
_device = None
_index = None
_conn = None
_kw_embeddings: dict[str, np.ndarray] = {}


def _load_resources() -> None:
    global _model, _tokenizer, _device, _index, _conn, _kw_embeddings
    print("Device: ", end="", flush=True)
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
    print("Pre-computing keyword embeddings...")
    for kw in PREDEFINED_KEYWORDS:
        vec = text_embedding(_model, _tokenizer, kw, _device)  # (1, 512)
        _kw_embeddings[kw] = vec[0]  # (512,)
    print(f"Done — {len(_kw_embeddings)} keyword embeddings cached.")


# ---------------------------------------------------------------------------
# Search function
# ---------------------------------------------------------------------------
def search(query: str, source: str, top_k: int, threshold: float, cols: int):
    if not query.strip():
        return gr.update(), "Zadej dotaz.", [], [], []

    vec = text_embedding(_model, _tokenizer, query.strip(), _device)

    # Over-fetch when filtering by source so we can fill top_k after filtering
    fetch_k = int(top_k) * 5 if source != "all" else int(top_k)
    ids, scores = search_index(_index, vec, fetch_k)

    results_data = []
    gallery_items = []
    paths = []
    row_ids = []
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
            row_ids.append(int(row_id))
            results_data.append({"image": img, "caption": caption, "path": str(path)})
        except Exception:
            pass
        if len(gallery_items) >= int(top_k):
            break

    if gallery_items:
        status = f"{len(gallery_items)} výsledků pro '{query}'"
    else:
        status = f"Žádné výsledky pro '{query}' (zkus jiný dotaz nebo snížit min. skóre)"

    return gr.update(value=gallery_items, columns=int(cols)), status, results_data, paths, row_ids


# ---------------------------------------------------------------------------
# Redisplay — reflows gallery without re-running CLIP/FAISS
# ---------------------------------------------------------------------------
def redisplay(results_data: list, cols: int):
    if not results_data:
        return gr.update()
    gallery_items = [(r["image"], r["caption"]) for r in results_data]
    return gr.update(value=gallery_items, columns=int(cols))


# ---------------------------------------------------------------------------
# Image select — populate detail panel with metadata + keyword scores
# ---------------------------------------------------------------------------
def on_image_select(evt: gr.SelectData, paths: list, row_ids: list) -> tuple:
    if not row_ids or evt.index >= len(row_ids):
        return "_Klikni na snímek pro zobrazení detailů._", "", gr.update(interactive=False)

    path = paths[evt.index]
    row_id = row_ids[evt.index]

    info = get_image_info(_conn, row_id)
    p = Path(path)
    date = info["date_taken"][:10] if info and info["date_taken"] else "?"
    dims = f"{info['width']} × {info['height']}" if info and info.get("width") else "?"
    source = info["source"] if info else "?"

    try:
        img_vec = _index.reconstruct(row_id)  # (512,) — retrieves stored image embedding
        kw_scores = sorted(
            ((kw, float(np.dot(img_vec, kw_vec))) for kw, kw_vec in _kw_embeddings.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        score_rows = "\n".join(
            f"| {kw} | {score:.3f} | {'█' * max(0, int(score * 25))} |"
            for kw, score in kw_scores
        )
        kw_table = "| Klíčové slovo | Skóre | |\n|---|---|---|\n" + score_rows
    except Exception as e:
        kw_table = f"_Chyba při výpočtu skóre: {e}_"

    detail = (
        f"**`{p.name}`**  \n"
        f"`{path}`  \n"
        f"Datum: **{date}** · Zdroj: **{source}** · Rozměry: **{dims}**\n\n"
        "---\n\n"
        "### Shoda s klíčovými slovy\n\n"
        + kw_table
    )

    return detail, path, gr.update(interactive=True)


# ---------------------------------------------------------------------------
# Open in native OS viewer (explicit button press only)
# ---------------------------------------------------------------------------
def open_selected(path: str) -> str:
    if not path:
        return "Žádný snímek nevybrán."
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
        row_ids_state = gr.State([])
        selected_path_state = gr.State("")

        # ── Row 1: query + button ──────────────────────────────────────────
        with gr.Row():
            query_box = gr.Textbox(
                label="Dotaz (anglicky)",
                placeholder="3D printer, birthday party, cat on sofa...",
                scale=5,
                min_width=200,
            )
            search_btn = gr.Button("Hledat", variant="primary", scale=1, min_width=90)

        # ── Row 2: compact filter controls ────────────────────────────────
        with gr.Row(variant="compact"):
            source_drop = gr.Dropdown(
                choices=["all", "google", "onedrive"],
                value="all",
                label="Zdroj",
                scale=1,
                min_width=130,
            )
            top_k_slider = gr.Slider(5, 60, value=20, step=5, label="Výsledků", scale=2, min_width=120)
            threshold_slider = gr.Slider(0.05, 0.40, value=0.15, step=0.01, label="Min. skóre", scale=2, min_width=120)
            cols_slider = gr.Slider(2, 8, value=5, step=1, label="Sloupce", scale=1, min_width=100)

        # ── Status line (two signals on one row) ──────────────────────────
        with gr.Row(variant="compact"):
            status_text = gr.Textbox(
                show_label=False, container=False,
                interactive=False, max_lines=1,
                placeholder="Status…",
                scale=3,
            )
            viewer_status = gr.Textbox(
                show_label=False, container=False,
                interactive=False, max_lines=1,
                placeholder="Otevřený soubor…",
                scale=2,
            )

        # ── Gallery ───────────────────────────────────────────────────────
        gallery = gr.Gallery(
            columns=5,
            object_fit="cover",
            height="auto",
            show_label=False,
        )

        # ── Detail panel ──────────────────────────────────────────────────
        with gr.Row():
            with gr.Column(scale=4):
                detail_md = gr.Markdown("_Klikni na snímek pro zobrazení detailů._")
            with gr.Column(scale=0, min_width=190):
                open_btn = gr.Button("Otevřít v prohlížeči", interactive=False)

        # ── Event wiring ──────────────────────────────────────────────────
        search_inputs = [query_box, source_drop, top_k_slider, threshold_slider, cols_slider]
        search_outputs = [gallery, status_text, results_state, paths_state, row_ids_state]
        search_btn.click(fn=search, inputs=search_inputs, outputs=search_outputs)
        query_box.submit(fn=search, inputs=search_inputs, outputs=search_outputs)

        cols_slider.change(fn=redisplay, inputs=[results_state, cols_slider], outputs=[gallery])

        gallery.select(
            fn=on_image_select,
            inputs=[paths_state, row_ids_state],
            outputs=[detail_md, selected_path_state, open_btn],
        )
        open_btn.click(fn=open_selected, inputs=[selected_path_state], outputs=[viewer_status])

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _load_resources()
    demo = build_ui()
    demo.launch(inbrowser=True)
