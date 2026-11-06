import pytest

from rag.context import title, with_context


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("mudevops05_act1 (1).docx", "mudevops05 actividad 1"),
        ("mudevopsact03.docx", "mudevops actividad 3"),
        ("act3mod.docx", "actividad 3mod"),
        ("tema5 (2).pdf", "tema5"),
        ("537764.vtt", "537764"),
    ],
)
def test_title(source, expected):
    assert title(source) == expected


def test_with_context_adds_subject_kind_and_location():
    payload = {
        "text": "Criterio | Peso",
        "subject": "SecDevOps",
        "material_type": "docx",
        "source": "act3mod.docx",
        "location": "tabla 1",
    }
    assert with_context(payload) == (
        "SecDevOps · enunciado de actividad · actividad 3mod · tabla 1\nCriterio | Peso"
    )
