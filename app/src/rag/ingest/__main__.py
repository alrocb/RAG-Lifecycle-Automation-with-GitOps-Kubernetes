"""Reindexa la base de conocimiento: python -m rag.ingest [--data-dir DIR] [--s3-bucket B] [--if-missing]"""

import argparse
import logging
from pathlib import Path

from qdrant_client import QdrantClient

from rag.config import settings
from rag.ingest.anonymize import load_names
from rag.ingest.indexer import current_collection, load_documents, reindex
from rag.ingest.sources import download_bucket

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rag.ingest")
logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos de PDFs mal formados que sí se leen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=settings.data_dir)
    parser.add_argument("--s3-bucket", default=settings.materials_bucket,
                        help="descarga antes los materiales de este bucket en --data-dir")
    parser.add_argument("--if-missing", action="store_true",
                        help="no hace nada si ya existe el índice (primera carga de un clúster nuevo)")
    args = parser.parse_args()

    client = QdrantClient(url=settings.qdrant_url)
    if args.if_missing and current_collection(client, settings.collection_alias):
        log.info("El índice '%s' ya existe: no se reindexa", settings.collection_alias)
        return

    if args.s3_bucket:
        count = download_bucket(args.s3_bucket, Path(args.data_dir))
        log.info("%d ficheros descargados de s3://%s", count, args.s3_bucket)

    payloads = load_documents(Path(args.data_dir), load_names(settings.names_file))
    log.info("%d fragmentos leídos de %s", len(payloads), args.data_dir)
    name = reindex(client, payloads, settings.collection_alias)
    log.info("Alias '%s' apunta ahora a '%s'", settings.collection_alias, name)


if __name__ == "__main__":
    main()
