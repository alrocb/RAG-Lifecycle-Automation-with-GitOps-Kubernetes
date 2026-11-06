import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from pptx import Presentation
from pypdf import PdfReader


@dataclass
class Section:
    text: str
    location: str  # minuto, página, diapositiva o apartado; se usa para citar


# Teams/Zoom ponen quién habla al principio de cada línea: "IVAN SANZ PRIETO: Muy bien..."
# Son datos personales y no aportan al contenido. Se exigen 2-6 palabras en mayúscula inicial
# para no confundirlo con "Por ejemplo: ..." o "Nota: ...".
_UPPER = "A-ZÁÉÍÓÚÑÜÀÈÌÒÙÇ"
SPEAKER = re.compile(rf"^(?:[{_UPPER}][\w'.-]*\s){{1,5}}[{_UPPER}][\w'.-]*:\s*")


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
        # Por línea: en un mismo bloque pueden hablar dos personas.
        texts.append(" ".join(SPEAKER.sub("", line) for line in lines[timing + 1 :]))
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


def parse_docx(path: Path) -> list[Section]:
    """Agrupa los párrafos bajo su título; el título sirve de ubicación para citar."""
    document = Document(path)
    sections, heading, texts = [], "inicio", []
    for paragraph in document.paragraphs:
        style = paragraph.style.name.lower() if paragraph.style is not None else ""
        if style.startswith(("heading", "título", "title")) and paragraph.text.strip():
            if texts:
                sections.append(Section("\n".join(texts), heading))
            heading, texts = paragraph.text.strip(), []
        texts.append(paragraph.text)
    if texts:
        sections.append(Section("\n".join(texts), heading))
    # Las rúbricas y criterios de las actividades suelen estar en tablas.
    for i, table in enumerate(document.tables, start=1):
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        sections.append(Section("\n".join(rows), f"tabla {i}"))
    return sections


PARSERS = {".vtt": parse_vtt, ".pdf": parse_pdf, ".pptx": parse_pptx, ".docx": parse_docx}
