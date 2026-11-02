FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 EMBED_CACHE_DIR=/models

COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --uid 1000 --create-home app && mkdir /models && chown app /models
USER app
# Los modelos van dentro de la imagen para no depender de la red al arrancar.
RUN python -c "from rag.embeddings import warm_up; warm_up()"

EXPOSE 8000
# La misma imagen sirve para la API (por defecto) y para la ingesta: python -m rag.ingest
CMD ["uvicorn", "rag.api:app", "--host", "0.0.0.0", "--port", "8000"]
