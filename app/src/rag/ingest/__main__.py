"""Reindexa la base de conocimiento: python -m rag.ingest [--data-dir DIR]"""

import argparse
import logging
from pathlib import Path

from qdrant_client import QdrantClient

from rag.config import settings
from rag.ingest.anonymize import load_names
from rag.ingest.indexer import load_documents, reindex

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rag.ingest")
logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos de PDFs mal formados que sí se leen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=settings.data_dir)
    args = parser.parse_args()

    payloads = load_documents(Path(args.data_dir), load_names(settings.names_file))
    log.info("%d fragmentos leídos de %s", len(payloads), args.data_dir)
    client = QdrantClient(url=settings.qdrant_url)
    name = reindex(client, payloads, settings.collection_alias)
    log.info("Alias '%s' apunta ahora a '%s'", settings.collection_alias, name)


if __name__ == "__main__":
    main()
