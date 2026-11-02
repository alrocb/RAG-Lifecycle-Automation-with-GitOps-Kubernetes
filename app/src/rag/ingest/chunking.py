def split(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Trocea por caracteres con solapamiento para no cortar ideas entre fragmentos."""
    text = " ".join(text.split())
    if not text:
        return []
    step = size - overlap
    return [text[i : i + size] for i in range(0, max(len(text) - overlap, 1), step)]
