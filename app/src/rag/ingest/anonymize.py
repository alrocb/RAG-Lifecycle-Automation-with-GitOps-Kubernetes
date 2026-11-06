"""Anonimización de nombres propios (RF2), en tres capas:

1. Etiquetas de voz de VTT: <v Nombre Apellido>texto</v>
2. Nombres de persona detectados por spaCy (NER), sin necesidad de conocerlos. En transcripciones
   automáticas spaCy marca como persona muchas palabras que no lo son ("Kubernetes Engine",
   inicios de frase...), así que solo cuentan las entidades que contienen un nombre de pila
   de nombres_de_pila.txt y que no son herramientas de terminos_tecnicos.txt.
   Además se sustituye cualquier palabra en mayúscula que sea un nombre de pila, porque spaCy
   no detecta todos ("a ver Alberto, ...").
3. Lista opcional de nombres (NAMES_FILE) para lo que el modelo no detecte.
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from rag.config import settings

PLACEHOLDER = "[PERSONA]"
VOICE_TAG = re.compile(r"</?v(?:\s[^>]*)?>")
# Nombre seguido de hasta 2 apellidos o iniciales: "Jesús F. Rodríguez-Aragón", "Ana Pérez Martínez".
CAPITALIZED = re.compile(r"\b[A-ZÁÉÍÓÚÑÜ]\w+(?:\s+(?:[A-ZÁÉÍÓÚÑÜ][\w-]+|[A-ZÁÉÍÓÚÑÜ]\.)){0,2}")


def _normalize(word: str) -> str:
    """Minúsculas y sin tildes: 'Iván' -> 'ivan'."""
    decomposed = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _word_list(filename: str) -> set[str]:
    lines = (Path(__file__).parent / filename).read_text(encoding="utf-8").splitlines()
    return {_normalize(line.strip()) for line in lines if line.strip() and not line.startswith("#")}


GIVEN_NAMES = _word_list("nombres_de_pila.txt")
TECH_TERMS = _word_list("terminos_tecnicos.txt")


@lru_cache
def _nlp():
    import spacy  # solo hace falta en la ingesta

    # Solo se usa el reconocimiento de entidades; el resto del pipeline se excluye por velocidad.
    return spacy.load(settings.ner_model, exclude=["parser", "lemmatizer", "morphologizer"])


def is_person(entity: str) -> bool:
    # "alguna" y no "la primera": spaCy a veces arrastra la palabra anterior ("Ayer Juan García").
    has_given_name = any(_normalize(word) in GIVEN_NAMES for word in entity.split())
    return has_given_name and _normalize(entity) not in TECH_TERMS


def _replace_name_and_surnames(match: re.Match) -> str:
    """'Hola Jesús F. Rodríguez' -> 'Hola [PERSONA]': desde el nombre de pila hasta el final."""
    words = match.group().split()
    for i, word in enumerate(words):
        if is_person(word):
            return " ".join([*words[:i], PLACEHOLDER])
    return match.group()


def load_names(path: str | None) -> list[str]:
    """Lista de nombres a anonimizar, uno por línea. El fichero no se versiona."""
    if not path:
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def anonymize(text: str, names: list[str]) -> str:
    text = VOICE_TAG.sub("", text)
    if settings.ner_model:
        people = [e for e in _nlp()(text).ents if e.label_ == "PER" and is_person(e.text)]
        for entity in reversed(people):  # de atrás adelante para no desplazar las posiciones
            text = text[: entity.start_char] + PLACEHOLDER + text[entity.end_char :]
    text = CAPITALIZED.sub(_replace_name_and_surnames, text)
    if names:
        # Los nombres más largos primero para que "Ana López" gane a "Ana".
        alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        text = re.sub(rf"\b(?:{alternatives})\b", PLACEHOLDER, text, flags=re.IGNORECASE)
    return text
