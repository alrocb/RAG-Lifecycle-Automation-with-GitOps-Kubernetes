from pathlib import Path


def download_bucket(bucket: str, dest: Path, client=None) -> int:
    """Copia el bucket a dest conservando las carpetas (una por asignatura). Devuelve los ficheros.

    En el clúster las credenciales son las del rol de la máquina (IMDSv2): no hay secretos.
    """
    if client is None:
        import boto3  # solo hace falta en la ingesta

        client = boto3.client("s3")
    count = 0
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            target = dest / key
            target.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(target))
            count += 1
    return count
