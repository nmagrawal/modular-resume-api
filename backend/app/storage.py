from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "resume"


def save_resume(markdown: str, role: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}_{slugify(role)}.md"
    path = OUTPUT_DIR / filename
    path.write_text(markdown, encoding="utf-8")
    return path
