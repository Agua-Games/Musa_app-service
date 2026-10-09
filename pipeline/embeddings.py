"""Local multilingual embeddings via ONNX (ADR 0013) — CPU, zero cost, offline
after the first model download.

Model: intfloat/multilingual-e5-small (384 dims, ONNX, ~470 MB in the
HF cache — outside any repo). E5 conventions are honored: texts are embedded as
"passage: ...", queries as "query: ...", outputs are L2-normalized so cosine
similarity = dot product.

This module is shared by the index builder (pipeline) and the MCP semantic
search (query time) — it must import cleanly without torch.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_REPO = "intfloat/multilingual-e5-small"
DIMENSIONS = 384


@lru_cache(maxsize=1)
def _session_and_tokenizer():
    from huggingface_hub import hf_hub_download
    import onnxruntime as ort
    from tokenizers import Tokenizer

    # onnx/model.onnx is the safe pick: the qint8 variant needs AVX512-VNNI and
    # there is no generic quantized build in this repo.
    model_path = hf_hub_download(MODEL_REPO, "onnx/model.onnx")
    tokenizer_path = hf_hub_download(MODEL_REPO, "tokenizer.json")
    session = ort.InferenceSession(
        str(Path(model_path)), providers=["CPUExecutionProvider"]
    )
    tokenizer = Tokenizer.from_file(str(Path(tokenizer_path)))
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding()  # batch needs uniform sequence length
    return session, tokenizer


def embed(texts: list[str], *, kind: str = "passage") -> np.ndarray:
    """Embed texts as (n, 384) L2-normalized float32. kind: 'passage' | 'query'."""
    prefix = "query: " if kind == "query" else "passage: "
    session, tokenizer = _session_and_tokenizer()
    encodings = tokenizer.encode_batch([prefix + t for t in texts])
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids)  # e5 uses a single segment
    outputs = session.run(
        None, {"input_ids": input_ids, "attention_mask": attention,
               "token_type_ids": token_type_ids}
    )[0]  # token embeddings (n, seq, 384)
    mask = attention[..., None].astype(np.float32)
    pooled = (outputs * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return (pooled / np.clip(norms, 1e-9, None)).astype(np.float32)


def item_text(card: dict) -> str:
    """The canonical text of a card for embedding: title, author, description, tags."""
    parts = [card.get("titulo") or "", card.get("autor") or "", card.get("descricao") or ""]
    tags = card.get("tags") or []
    if tags:
        parts.append(", ".join(str(t) for t in tags))
    return " — ".join(p for p in parts if p)
