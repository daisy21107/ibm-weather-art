"""Lightweight intent & slot inference wrapper for the MobileBERT + ONNX
model that ships with the project. This version resolves the model path
**relative to the file location**, so you can launch the program from any
folder and it will still find `UI/onnx/…`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

# ----------------------------------------------------------------------
# ▸ Helper functions ----------------------------------------------------
# ----------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lower-case and strip non-alphanumerics (very loose)."""
    return re.sub(r"[^a-z0-9\s'\-]", " ", text.lower()).strip()


def _jload(path: Path):
    """Load UTF-8 JSON from *path* and return the parsed object."""
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _align(word_ids, tag_ids, id2tag, allowed):
    """Word-piece → token-level tag collapse as in the original script."""
    bucket = {}
    for idx, wid in enumerate(word_ids):
        if wid is None:
            continue
        tag = id2tag.get(tag_ids[idx], "O")
        if tag not in allowed and tag != "O":
            tag = "O"
        bucket.setdefault(wid, []).append(tag)

    out = []
    for tags in bucket.values():
        out.append(next((t for t in tags if t.startswith("B-")),
                        next((t for t in tags if t.startswith("I-")), "O")))
    return out


def _fix_bio(seq: List[str]) -> List[str]:
    for i, tag in enumerate(seq):
        if tag.startswith("I-") and (
            i == 0 or seq[i - 1] == "O" or seq[i - 1][2:] != tag[2:]
        ):
            seq[i] = "B-" + tag[2:]
    return seq


# ----------------------------------------------------------------------
# ▸ Main ONNX inference function ---------------------------------------
# ----------------------------------------------------------------------

def infer_onnx(
    sentence: str,
    model_dir: str | Path | None = None,
    *,
    backbone: str = "google/mobilebert-uncased",
    onnx_path: str | Path | None = None,
    threshold: float = 0.9,
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Infer *sentence* and return `(intents, [(word, slot_tag), …])`.

    Parameters
    ----------
    sentence : str
        Raw user utterance.
    model_dir : str | Path | None, optional
        Folder containing `tag2id.json`, `intent2id.json`,
        `intent_slot_map.json` and the ONNX checkpoint.  Defaults to
        ``<this_file>/onnx``.
    backbone : str, optional
        HF model name used **only** for tokenisation. default:
        ``google/mobilebert-uncased``.
    onnx_path : str | Path | None, optional
        Explicit path to the ONNX file. If *None*, resolves to
        ``model_dir / 'joint_fp32_rmd.onnx'``.
    threshold : float, optional
        Confidence cut-off for intent filtering.
    """

    # -------- Resolve paths relative to this script ------------------
    base_dir = Path(__file__).resolve().parent  # <project>/UI

    if model_dir is None:
        model_dir = base_dir / "onnx"
    else:
        model_dir = Path(model_dir)
        if not model_dir.is_absolute():
            model_dir = (base_dir / model_dir).resolve()

    if onnx_path is None:
        onnx_path = model_dir / "joint_fp32_rmd.onnx"
    else:
        onnx_path = Path(onnx_path)
        if not onnx_path.is_absolute():
            onnx_path = (base_dir / onnx_path).resolve()

    # -------- Load label maps ----------------------------------------
    tag2id = _jload(model_dir / "tag2id.json")
    intent2id = _jload(model_dir / "intent2id.json")
    intent_slot = _jload(model_dir / "intent_slot_map.json")

    id2tag = {int(v): k for k, v in tag2id.items()}
    id2intent = {int(v): k for k, v in intent2id.items()}

    # -------- Tokenise ------------------------------------------------
    tokenizer = AutoTokenizer.from_pretrained(backbone)

    words = _normalize(sentence).split()
    enc = tokenizer(
        words,
        is_split_into_words=True,
        return_tensors="np",
        padding=True,
        truncation=True,
        max_length=128,
    )
    ort_inputs = {k: enc[k].astype("int64") for k in ["input_ids", "attention_mask"]}
    word_ids = tokenizer(words, is_split_into_words=True).word_ids()

    # -------- Run ONNX session ---------------------------------------
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    tag_log, int_log = session.run(None, ort_inputs)

    # -------- Intent post-processing ---------------------------------
    prob = 1 / (1 + np.exp(-int_log.squeeze()))
    top_k = 2
    top_indices = prob.argsort()[-top_k:][::-1]
    idx = [i for i in top_indices if prob[i] >= threshold]

    if not idx:
        idx = [int(prob.argmax())]

    raw_pred = [id2intent[i] for i in idx]
    intents = list({it for r in raw_pred for it in r.split("&")})

    # single-intent enforcement
    if "reminder_add" in intents:
        intents = ["reminder_add"]
    elif "reminder_cancel" in intents:
        intents = ["reminder_cancel"]

    # -------- Slot post-processing -----------------------------------
    allowed_tags = {id2tag[i] for it in intents for i in intent_slot.get(it, [])}
    tag_ids = tag_log[0].argmax(-1).tolist()

    slot_tags = _align(word_ids, tag_ids, id2tag, allowed_tags)
    slot_tags = _fix_bio(slot_tags)

    custom_slot_dict = {
        "tonight": "B-time",
        "tomorrow": "B-time",
        "today": "B-time"
    }
    for i, (w, t) in enumerate(zip(words, slot_tags)):
        if w in custom_slot_dict and t == "O":
            slot_tags[i] = custom_slot_dict[w]
    return intents, list(zip(words, slot_tags))


# ----------------------------------------------------------------------
# ▸ Simple CLI for quick testing --------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("🔹 ONNX model ready! Press Ctrl-C to exit.")
    try:
        while True:
            utter = input("🗣 Enter a sentence: ").strip()
            if not utter:
                continue
            intents, slots = infer_onnx(utter)

            print("🎯 Detected intents:", intents)
            print("📌 Slot annotations:")
            for w, t in slots:
                print(f"  {w:<15}→ {t}")
    except KeyboardInterrupt:
        print("\n👋 Bye-bye!")