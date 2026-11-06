"""Cabecera de contexto que acompaña a cada fragmento al indexarlo y al reordenarlo.

Un fragmento suelto ("Criterio | Peso | ...") no dice de qué asignatura ni de qué actividad es.
Anteponerle esos datos permite que "rúbrica de la actividad 3 de SecDevOps" lo encuentre.
"""

import re
from pathlib import Path

KINDS = {
    "vtt": "transcripción de clase",
    "pdf": "temario",
    "pptx": "diapositivas",
    "docx": "enunciado de actividad",
}


def title(source: str) -> str:
    """'mudevops05_act1 (1).docx' -> 'mudevops05 actividad 1'"""
    name = re.sub(r"\s*\(\d+\)$", "", Path(source).stem).replace("_", " ")
    name = re.sub(r"act(?:ividad)?[\s-]*0?(\d)(?!\d)", r" actividad \1", name, flags=re.IGNORECASE)
    return " ".join(name.split())


def with_context(payload: dict) -> str:
    kind = KINDS.get(payload["material_type"], payload["material_type"])
    header = f"{payload['subject']} · {kind} · {title(payload['source'])} · {payload['location']}"
    return f"{header}\n{payload['text']}"
