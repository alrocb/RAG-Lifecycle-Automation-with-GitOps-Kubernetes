from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pypdf import PdfReader


@dataclass
class Section:
    text: str
    location: str  # minuto, página o diapositiva; se usa para citar


def _seconds(timestamp: str) -> float:
    parts = timestamp.split(":")
    return sum(float(p) * 60**i for i, p in enumerate(reversed(parts)))


def parse_vtt(path: Path, window: int = 60) -> list[Section]:
    """Agrupa las líneas de la transcripción en bloques de ~`window` segundos."""
    sections, texts, start = [], [], None
    content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    for block in content.split("\n\n"):
        lines = block.strip().splitlines()
        timing = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing is None:
            continue
        begin = lines[timing].split("-->")[0].strip()
        if start is None:
            start = begin
        texts.append(" ".join(lines[timing + 1 :]))
        if _seconds(begin) - _seconds(start) >= window:
            sections.append(Section(" ".join(texts), start.split(".")[0]))
            texts, start = [], None
    if texts:
        sections.append(Section(" ".join(texts), start.split(".")[0]))
    return sections


def parse_pdf(path: Path) -> list[Section]:
    return [
        Section(page.extract_text() or "", f"p. {i}")
        for i, page in enumerate(PdfReader(path).pages, start=1)
    ]


def parse_pptx(path: Path) -> list[Section]:
    sections = []
    for i, slide in enumerate(Presentation(path).slides, start=1):
        texts = [shape.text_frame.text for shape in slide.shapes if shape.has_text_frame]
        sections.append(Section("\n".join(texts), f"diapositiva {i}"))
    return sections


PARSERS = {".vtt": parse_vtt, ".pdf": parse_pdf, ".pptx": parse_pptx}
