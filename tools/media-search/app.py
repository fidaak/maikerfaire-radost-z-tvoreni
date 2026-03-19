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
import open_clip
import torch
from PIL import Image

from search import get_device, get_image_info, search_index, text_embedding

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).parent
DB_PATH = HERE / "photos.db"
FAISS_PATH = HERE / "photos.faiss"
MODEL_NAME = "ViT-L-14"
MAX_FETCH = 2000  # maximum candidates pulled from FAISS per query

PREDEFINED_KEYWORDS = [
    # maker / 3D printing
    "3D printer",
    "Voron 3D printer",
    "CoreXY 3D printer",
    "3D printing in progress",
    "3D printed object",
    "3D printing filament spool",
    "FDM print bed",
    "Klipper touchscreen",
    "printer enclosure",
    "failed 3D print",
    "support removal 3D print",
    "resin 3D printer",
    # electronics / making
    "soldering iron pcb",
    "electronics workbench",
    "multimeter wiring",
    "breadboard prototype",
    "drone motor ESC",
    "circuit board close-up",
    "raspberry pi computer",
    "stepper motor cable",
    "power supply wiring",
    # RC / LEGO / robotics
    "LEGO car build",
    "RC car remote control",
    "RC car chassis",
    "LEGO Technic mechanism",
    "robot arm",
    # compliant / flexible mechanisms
    "compliant mechanism",
    "flexible 3D print",
    "print-in-place hinge",
    "living hinge plastic",
    # henna / art
    "henna tattoo hand",
    "henna painting art",
    "body art decoration",
    "intricate pattern drawing",
    # maker event / exhibition
    "maker faire booth",
    "exhibition table display",
    "visitors at maker event",
    "project demonstration",
    "maker fair crowd",
    # workshop / tools
    "workshop workbench",
    "hand tools on table",
    "drill press workshop",
    "screwdriver assembly",
    "cable management",
    "hot glue gun craft",
    "laser cutter machine",
    # people / family
    "child playing with toy",
    "children building together",
    "father and child project",
    "family at table crafting",
    "person concentrating working",
    "teenager using computer",
    "group of people workshop",
    # scenes / settings
    "cluttered desk workshop",
    "tidy maker workspace",
    "garage workshop",
    "school classroom project",
    "outdoor maker activity",
    "living room project spread",
    # photography / context
    "close-up macro detail",
    "flat lay top view tools",
    "screen displaying code",
    "computer monitor CAD model",
    "blueprint technical drawing",
    "camera filming project",
    # everyday / context clues
    "birthday party celebration",
    "holiday family gathering",
    "renovation construction work",
    "garden outdoor activity",
    "kitchen table project",
    "backpack travel luggage",
    "whiteboard planning session",
    "notebook sketching ideas",
]

# ---------------------------------------------------------------------------
# Global resources (loaded once at startup)
# ---------------------------------------------------------------------------
_model = None
_tokenizer = None
_preprocess = None
_device = None
_index = None
_conn = None
_kw_embeddings: dict[str, np.ndarray] = {}


def _load_resources() -> None:
    global _model, _tokenizer, _preprocess, _device, _index, _conn, _kw_embeddings
    print("Device: ", end="", flush=True)
    _device = get_device()
    print(_device)
    print(f"Loading CLIP model {MODEL_NAME}...")
    _model, _, _preprocess = open_clip.create_model_and_transforms(
        MODEL_NAME, pretrained="openai", device=_device
    )
    _model.eval()
    _tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    print(f"Loading FAISS index from {FAISS_PATH}...")
    _index = faiss.read_index(str(FAISS_PATH))
    # check_same_thread=False: Gradio uses threads, SQLite is read-only here
    _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    total = _conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    print(f"Ready — {total} images indexed.")
    print("Pre-computing keyword embeddings...")
    for kw in PREDEFINED_KEYWORDS:
        vec = text_embedding(_model, _tokenizer, kw, _device)  # (1, D)
        _kw_embeddings[kw] = vec[0]  # (D,)
    print(f"Done — {len(_kw_embeddings)} keyword embeddings cached.")


# ---------------------------------------------------------------------------
# Image embedding (for per-click keyword scoring)
# ---------------------------------------------------------------------------
def _image_embedding(path: str) -> np.ndarray:
    """Encode a single image with CLIP; returns normalized (D,) float32 vector."""
    img_tensor = _preprocess(Image.open(path).convert("RGB")).unsqueeze(0).to(_device)
    with torch.no_grad(), torch.amp.autocast(device_type=_device.type):
        features = _model.encode_image(img_tensor)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().astype(np.float32)[0]


# ---------------------------------------------------------------------------
# Page rendering helper — opens PIL for one page slice only
# ---------------------------------------------------------------------------
def _render_page(
    all_results: list, page: int, cols: int, page_size: int
) -> tuple:
    """Returns (gallery_update, paths, row_ids, status_str, clamped_page)."""
    total = len(all_results)
    page_size = int(page_size)
    n_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, n_pages - 1))
    start = page * page_size
    chunk = all_results[start : start + page_size]

    gallery_items, paths, row_ids = [], [], []
    for item in chunk:
        p = Path(item["file_path"])
        if not p.exists():
            continue
        try:
            img = Image.open(p)
            img.thumbnail((800, 800))
            gallery_items.append((img, item["caption"]))
            paths.append(item["file_path"])
            row_ids.append(item["row_id"])
        except Exception:
            pass

    if total == 0:
        status = "Žádné výsledky."
    elif n_pages == 1:
        status = f"{total} výsledků"
    else:
        status = f"Strana {page + 1} / {n_pages}  ·  {total} výsledků"

    return gr.update(value=gallery_items, columns=int(cols)), paths, row_ids, status, page


# ---------------------------------------------------------------------------
# Search — fetches up to MAX_FETCH, stores all metadata in state
# ---------------------------------------------------------------------------
def search(query: str, source: str, threshold: float, cols: int, page_size: int):
    if not query.strip():
        return gr.update(), "Zadej dotaz.", [], 0, [], []

    vec = text_embedding(_model, _tokenizer, query.strip(), _device)
    ids, scores = search_index(_index, vec, MAX_FETCH)

    all_results = []
    for row_id, score in zip(ids, scores):
        if row_id < 0 or score < threshold:
            continue
        info = get_image_info(_conn, row_id)
        if not info:
            continue
        if source != "all" and info["source"] != source:
            continue
        p = Path(info["file_path"])
        if not p.exists():
            continue
        date = info["date_taken"][:10] if info["date_taken"] else "?"
        rank = len(all_results) + 1
        all_results.append({
            "file_path": str(p),
            "row_id": int(row_id),
            "score": float(score),
            "source": info["source"],
            "date_taken": info["date_taken"],
            "width": info.get("width"),
            "height": info.get("height"),
            "caption": f"#{rank} · {float(score):.3f} · {date} · {info['source']}",
        })

    if not all_results:
        msg = f"Žádné výsledky pro '{query}' (zkus jiný dotaz nebo snížit min. skóre)"
        return gr.update(value=[], columns=int(cols)), msg, [], 0, [], []

    gallery, paths, row_ids, status, page = _render_page(all_results, 0, cols, page_size)
    return gallery, status, all_results, page, paths, row_ids


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
def go_next(all_results: list, page: int, cols: int, page_size: int):
    return _render_page(all_results, page + 1, cols, page_size)


def go_prev(all_results: list, page: int, cols: int, page_size: int):
    return _render_page(all_results, page - 1, cols, page_size)


# ---------------------------------------------------------------------------
# Column resize — re-renders current page from disk
# ---------------------------------------------------------------------------
def redisplay(all_results: list, page: int, cols: int, page_size: int):
    gallery, paths, row_ids, status, pg = _render_page(all_results, page, cols, page_size)
    return gallery, paths, row_ids


# ---------------------------------------------------------------------------
# Image select — detail panel with metadata + keyword scores
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
        img_vec = _image_embedding(path)
        kw_scores = sorted(
            ((kw, float(np.dot(img_vec, kw_vec))) for kw, kw_vec in _kw_embeddings.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        score_rows = "\n".join(
            f"| {kw} | {score:.3f} | {'█' * max(0, int(score * 25))} |"
            for kw, score in kw_scores[:20]
        )
        kw_table = "| Fráze | Skóre | |\n|---|---|---|\n" + score_rows
    except Exception as e:
        kw_table = f"_Chyba při výpočtu skóre: {e}_"

    detail = (
        f"**`{p.name}`**  \n"
        f"`{path}`  \n"
        f"Datum: **{date}** · Zdroj: **{source}** · Rozměry: **{dims}**\n\n"
        "---\n\n"
        "### Top 20 nejlepších frází\n\n"
        + kw_table
    )
    return detail, path, gr.update(interactive=True)


# ---------------------------------------------------------------------------
# Open in native OS viewer
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

        all_results_state   = gr.State([])   # all metadata dicts, no PIL
        page_state          = gr.State(0)
        paths_state         = gr.State([])
        row_ids_state       = gr.State([])
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
            threshold_slider = gr.Slider(0.05, 0.40, value=0.15, step=0.01, label="Min. skóre", scale=2, min_width=120)
            page_size_slider = gr.Slider(10, 60, value=20, step=10, label="Na stránku", scale=2, min_width=120)
            cols_slider      = gr.Slider(2, 8, value=5, step=1, label="Sloupce", scale=1, min_width=100)

        # ── Status + pagination on one row ────────────────────────────────
        with gr.Row(variant="compact"):
            prev_btn    = gr.Button("← Zpět",  scale=0, min_width=80,  interactive=False)
            status_text = gr.Textbox(
                show_label=False, container=False,
                interactive=False, max_lines=1,
                placeholder="Status…", scale=4,
            )
            next_btn    = gr.Button("Další →", scale=0, min_width=80, interactive=False)
            viewer_status = gr.Textbox(
                show_label=False, container=False,
                interactive=False, max_lines=1,
                placeholder="Otevřený soubor…", scale=2,
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
        nav_inputs  = [all_results_state, page_state, cols_slider, page_size_slider]
        nav_outputs = [gallery, paths_state, row_ids_state, status_text, page_state]

        def _enable_nav(gallery_upd, paths, row_ids, status, page):
            """Wrap nav outputs with button enable/disable based on whether there are results."""
            has_results = bool(paths)
            return (
                gallery_upd, paths, row_ids, status, page,
                gr.update(interactive=has_results),
                gr.update(interactive=has_results),
            )

        search_inputs  = [query_box, source_drop, threshold_slider, cols_slider, page_size_slider]
        search_outputs = [gallery, status_text, all_results_state, page_state, paths_state, row_ids_state,
                          prev_btn, next_btn]

        def _search_with_nav(query, source, threshold, cols, page_size):
            gallery_upd, status, all_res, page, paths, row_ids = search(
                query, source, threshold, cols, page_size
            )
            has = bool(paths)
            return (gallery_upd, status, all_res, page, paths, row_ids,
                    gr.update(interactive=has), gr.update(interactive=has))

        def _go_next_with_nav(all_results, page, cols, page_size):
            g, p, r, s, pg = go_next(all_results, page, cols, page_size)
            has = bool(p)
            return g, p, r, s, pg, gr.update(interactive=has), gr.update(interactive=has)

        def _go_prev_with_nav(all_results, page, cols, page_size):
            g, p, r, s, pg = go_prev(all_results, page, cols, page_size)
            has = bool(p)
            return g, p, r, s, pg, gr.update(interactive=has), gr.update(interactive=has)

        search_btn.click(fn=_search_with_nav, inputs=search_inputs, outputs=search_outputs)
        query_box.submit(fn=_search_with_nav, inputs=search_inputs, outputs=search_outputs)

        prev_btn.click(fn=_go_prev_with_nav, inputs=nav_inputs,
                       outputs=[gallery, paths_state, row_ids_state, status_text, page_state, prev_btn, next_btn])
        next_btn.click(fn=_go_next_with_nav, inputs=nav_inputs,
                       outputs=[gallery, paths_state, row_ids_state, status_text, page_state, prev_btn, next_btn])

        cols_slider.change(
            fn=redisplay,
            inputs=[all_results_state, page_state, cols_slider, page_size_slider],
            outputs=[gallery, paths_state, row_ids_state],
        )

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
