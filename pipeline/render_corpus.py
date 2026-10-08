"""Render the synthetic catalog-card corpus with perfect ground truth (M2.1).

Reads the Met seed cache (fetch_seed_metadata.py) and renders each record as a
JPEG "catalog card" photo — typed / modern / italic layouts, with rotation,
blur, brightness jitter and speckle noise — while writing the ground-truth
card.json next to it. Everything is deterministic (fixed seed), so the corpus
is reproducible and never enters git or the tenant bucket.

Usage:
    python render_corpus.py [--limit 450] [--seed 42]
"""

import argparse
import json
import math
import random
import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent
SEED_CACHE = ROOT / "corpus" / "seed" / "met-objects.json"
IMG_DIR = ROOT / "corpus" / "images"
GT_DIR = ROOT / "corpus" / "ground-truth"

WINDOWS_FONTS = Path("C:/Windows/Fonts")
CARD_W, CARD_H = 1000, 700

LABELS = [  # field -> label printed on the card (pt-BR, like a real ficha)
    ("titulo", "Título"),
    ("autor", "Autor"),
    ("data", "Data"),
    ("material", "Material"),
    ("dimensoes", "Dimensões"),
    ("descricao", "Descrição"),
]

DEPARTMENT_SLUGS = {
    "European Paintings": "european-paintings",
    "European Sculpture and Decorative Arts": "european-decorative-arts",
    "Egyptian Art": "egyptian-art",
    "Greek and Roman Art": "greek-roman-art",
    "Asian Art": "asian-art",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "sem-titulo"


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = WINDOWS_FONTS / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.truetype("DejaVuSans.ttf", size)  # matplotlib fallback


def wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int, draw) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_layout(card: dict, layout: str, rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (CARD_W, CARD_H), (252, 250, 244))
    draw = ImageDraw.Draw(img)
    if layout == "typed":  # typewriter ficha
        label_font, value_font = load_font("courbd.ttf", 30), load_font("cour.ttf", 30)
        y = 60
    elif layout == "modern":  # printed label, two weights
        label_font, value_font = load_font("arial.ttf", 24), load_font("georgia.ttf", 32)
        y = 50
    else:  # "italic" — closest we get to handwriting without a script font
        label_font, value_font = load_font("georgiai.ttf", 28), load_font("georgiai.ttf", 34)
        y = 56
    for field, label in LABELS:
        value = card.get(field)
        if not value:
            continue
        if layout == "typed":
            line = f"{label}: {value}"
            for part in wrap(line, value_font, CARD_W - 120, draw)[:3]:
                draw.text((60, y), part, font=value_font, fill=(25, 25, 30))
                y += 42
        else:
            draw.text((60, y), label.upper(), font=label_font, fill=(90, 90, 95))
            y += 30 if layout == "modern" else 34
            for part in wrap(value, value_font, CARD_W - 120, draw)[:3]:
                draw.text((80, y), part, font=value_font, fill=(20, 20, 25))
                y += 40 if layout == "modern" else 44
        y += 14
    draw.text((60, CARD_H - 52), f"Nº {card['asset_id']}", font=label_font, fill=(120, 120, 125))
    return img


def degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    angle = rng.uniform(-2.5, 2.5)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(235, 232, 224))
    if rng.random() < 0.6:
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.2, 1.1)))
    # brightness/contrast jitter
    factor = rng.uniform(0.85, 1.08)
    img = img.point(lambda p: max(0, min(255, int(p * factor))))
    # speckle noise
    px = img.load()
    for _ in range(rng.randint(300, 1500)):
        x, y = rng.randrange(CARD_W), rng.randrange(CARD_H)
        delta = rng.choice((-1, 1)) * rng.randint(15, 60)
        r, g, b = px[x, y]
        px[x, y] = tuple(max(0, min(255, c + delta)) for c in (r, g, b))
    return img


def ground_truth(obj: dict) -> dict:
    department = DEPARTMENT_SLUGS.get(obj["department"], slugify(obj["department"]))
    parts = [p for p in (obj["objectName"], obj["culture"], obj["period"]) if p]
    card = {
        "asset_id": f"met-{obj['objectID']}",
        "titulo": obj["title"].strip() or "Sem título",
        "colecao": department,
        "website_status": "published",
        "tier": "bronze",
    }
    if obj["artistDisplayName"].strip():
        card["autor"] = obj["artistDisplayName"].strip()
    if obj["objectDate"].strip():
        card["data"] = obj["objectDate"].strip()
    if obj["medium"].strip():
        card["material"] = obj["medium"].strip()
    if obj["dimensions"].strip():
        card["dimensoes"] = obj["dimensions"].strip()
    if parts:
        card["descricao"] = " — ".join(parts)
        card["tags"] = [slugify(p) for p in parts]
    return card


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=450)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not SEED_CACHE.exists():
        print(f"seed cache missing: {SEED_CACHE} — run fetch_seed_metadata.py first", file=sys.stderr)
        return 1
    objects = list(json.loads(SEED_CACHE.read_text(encoding="utf-8")).values())
    objects = [o for o in objects if o.get("title", "").strip()][: args.limit]
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    GT_DIR.mkdir(parents=True, exist_ok=True)

    layouts = ["typed", "modern", "italic"]
    for index, obj in enumerate(objects):
        rng = random.Random(args.seed * 100003 + index)  # deterministic per card
        card = ground_truth(obj)
        img = degrade(render_layout(card, layouts[index % 3], rng), rng)
        img.save(IMG_DIR / f"{card['asset_id']}.jpg", quality=rng.randint(70, 92))
        (GT_DIR / f"{card['asset_id']}.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if (index + 1) % 50 == 0:
            print(f"  {index + 1}/{len(objects)} rendered")

    print(f"CORPUS OK — {len(objects)} card(s): {IMG_DIR} + {GT_DIR} (local, gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
