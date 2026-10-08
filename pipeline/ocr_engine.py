"""OCR engine interface + docling implementation (ADR 0011).

The batch runner only knows ``OcrEngine.run(image_path) -> dict``. Swapping
engines (Folio-OCR, a VLM, a cloud API) means adding a class here — the rest of
the pipeline is engine-agnostic.

Output contract (per card):
    {
      "engine": str, "seconds": float,
      "text": str,                      # full raw text, reading order
      "blocks": [                       # layout blocks, when the engine has them
        {"text": str, "bbox": [l, t, r, b] | None, "confidence": float | None}
      ],
    }
"""

import time
from pathlib import Path


class DoclingEngine:
    """docling DocumentConverter on CPU (ADR 0011: pip, headless, no Docker)."""

    name = "docling"

    def __init__(self):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, ImageFormatOption

        # RapidOCR (onnxruntime) as the OCR backend: pure CPU, no extra torch
        # models, and pt/en recognition works out of the box.
        options = PdfPipelineOptions()
        options.ocr_options = RapidOcrOptions()
        self._converter = DocumentConverter(
            format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_options=options)}
        )

    def run(self, image_path: Path) -> dict:
        started = time.perf_counter()
        result = self._converter.convert(str(image_path))
        doc = result.document
        blocks = []
        for item in getattr(doc, "texts", []):
            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue
            bbox = None
            prov = getattr(item, "prov", None) or []
            if prov:
                box = getattr(prov[0], "bbox", None)
                if box is not None:
                    bbox = [box.l, box.t, box.r, box.b]
            blocks.append({"text": text, "bbox": bbox, "confidence": None})
        return {
            "engine": self.name,
            "seconds": round(time.perf_counter() - started, 3),
            "text": "\n".join(b["text"] for b in blocks),
            "blocks": blocks,
        }


def make_engine(name: str = "docling") -> DoclingEngine:
    if name != "docling":
        raise ValueError(f"unknown OCR engine {name!r} — alternatives land behind this interface")
    return DoclingEngine()
