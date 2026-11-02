"""Anonimización de nombres propios (RF2), en tres capas:

1. Etiquetas de voz de VTT: <v Nombre Apellido>texto</v>
2. Nombres de persona detectados por el modelo de spaCy (NER), sin necesidad de conocerlos.
   El modelo confunde algunas herramientas con personas (Helm, Jenkins, Grafana...), así que
   se respetan los términos de terminos_tecnicos.txt.
3. Lista opcional de nombres (NAMES_FILE) para lo que el modelo no detecte.
"""

import re
from functools import lru_cache
from pathlib import Path

from rag.config import settings

PLACEHOLDER = "[PERSONA]"
VOICE_TAG = re.compile(r"</?v(?:\s[^>]*)?>")
TECH_TERMS = {
    line.strip().lower()
    for line in (Path(__file__).parent / "terminos_tecnicos.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
}


@lru_cache
def _nlp():
    import spacy  # solo hace falta en la ingesta

    # Solo se usa el reconocimiento de entidades; el resto del pipeline se excluye por velocidad.
    return spacy.load(settings.ner_model, exclude=["parser", "lemmatizer", "morphologizer"])


def load_names(path: str | None) -> list[str]:
    """Lista de nombres a anonimizar, uno por línea. El fichero no se versiona."""
    if not path:
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def anonymize(text: str, names: list[str]) -> str:
    text = VOICE_TAG.sub("", text)
    if settings.ner_model:
        people = [
            e for e in _nlp()(text).ents if e.label_ == "PER" and e.text.lower() not in TECH_TERMS
        ]
        for entity in reversed(people):  # de atrás adelante para no desplazar las posiciones
            text = text[: entity.start_char] + PLACEHOLDER + text[entity.end_char :]
    if names:
        # Los nombres más largos primero para que "Ana López" gane a "Ana".
        alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        text = re.sub(rf"\b(?:{alternatives})\b", PLACEHOLDER, text, flags=re.IGNORECASE)
    return text
