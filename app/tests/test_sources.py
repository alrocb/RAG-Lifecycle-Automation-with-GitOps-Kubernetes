import sys

from qdrant_client import QdrantClient

from rag.ingest import __main__ as ingest_cli
from rag.ingest import indexer
from rag.ingest.sources import download_bucket


class FakeS3:
    """Imita lo que usa download_bucket del cliente de boto3."""

    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def get_paginator(self, _):
        objects = self.objects

        class Paginator:
            def paginate(self, Bucket):
                return [{"Contents": [{"Key": key} for key in objects]}]

        return Paginator()

    def download_file(self, bucket, key, filename):
        with open(filename, "wb") as f:
            f.write(self.objects[key])


def test_download_bucket_keeps_subject_folders(tmp_path):
    s3 = FakeS3({"devops/clase.vtt": b"WEBVTT", "kubernetes/tema1.pdf": b"%PDF", "carpeta/": b""})
    assert download_bucket("materiales", tmp_path, client=s3) == 2
    assert (tmp_path / "devops" / "clase.vtt").read_bytes() == b"WEBVTT"
    assert (tmp_path / "kubernetes" / "tema1.pdf").exists()


def test_if_missing_skips_download_when_index_exists(fake_models, monkeypatch, tmp_path):
    client = QdrantClient(":memory:")
    indexer.reindex(client, [{"text": "x", "subject": "s", "material_type": "vtt",
                              "source": "a.vtt", "location": "00:00:00"}], "materials")
    monkeypatch.setattr(ingest_cli, "QdrantClient", lambda **_: client)
    downloads = []
    monkeypatch.setattr(ingest_cli, "download_bucket", lambda *a: downloads.append(a) or 0)
    monkeypatch.setattr(sys, "argv", ["ingest", "--if-missing", "--s3-bucket", "b", "--data-dir", str(tmp_path)])
    ingest_cli.main()
    assert downloads == []
