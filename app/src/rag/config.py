from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (QDRANT_URL, LLM_BASE_URL, ...)."""

    qdrant_url: str = "http://localhost:6333"
    collection_alias: str = "materials"

    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Vacío desactiva la reordenación.
    rerank_model: str = "BAAI/bge-reranker-v2-m3-int8"
    # Fragmentos con puntuación del reranker por debajo se descartan (-3 ≈ 5 % de relevancia).
    rerank_min_score: float = -3.0
    embed_cache_dir: str | None = None
    # Modelo de spaCy para detectar nombres de persona al indexar. Vacío lo desactiva.
    ner_model: str = "es_core_news_md"

    # Cualquier API compatible con OpenAI: el mock-llm en local o un proveedor externo.
    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "mock"

    # Si está vacía no se exige clave (solo para desarrollo local).
    api_key: str = ""
    candidates: int = 10  # fragmentos que pasan de la búsqueda híbrida al reranker
    rerank_max_chars: int = 400  # texto de cada candidato que ve el reranker
    top_k: int = 5  # fragmentos que llegan al LLM
    max_history: int = 6  # mensajes previos de la conversación que se envían al LLM

    data_dir: str = "data"
    names_file: str | None = None


settings = Settings()
