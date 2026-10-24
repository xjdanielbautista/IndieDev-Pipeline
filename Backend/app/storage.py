import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO


def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def safe_storage_path(storage_key: str, upload_dir: str | None = None) -> Path:
    root = Path(upload_dir or os.getenv("LOCAL_UPLOAD_DIR", "./uploads")).resolve()
    destination = (root / storage_key.lstrip("/")).resolve()
    if root != destination and root not in destination.parents:
        raise ValueError("storage_key no está dentro del directorio permitido")
    return destination


def save_local(storage_key: str, file: BinaryIO) -> None:
    destination = safe_storage_path(storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    file.seek(0)
    with destination.open("wb") as output:
        while chunk := file.read(1024 * 1024):
            output.write(chunk)


def local_file(storage_key: str) -> Path:
    destination = safe_storage_path(storage_key)
    if not destination.is_file():
        return None
    return destination


def _s3_client():
    import boto3
    from botocore.config import Config

    endpoint_url = os.getenv("S3_ENDPOINT_URL")
    region_name = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    client_options = {
        "region_name": region_name,
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID") or None,
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY") or None,
    }
    if endpoint_url:
        client_options["endpoint_url"] = endpoint_url
        client_options["config"] = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )
    return boto3.client("s3", **client_options)


def save_s3(storage_key: str, file: BinaryIO, content_type: str | None) -> None:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("Falta configurar S3_BUCKET")

    file.seek(0)
    extra_args = {"ContentType": content_type} if content_type else None
    _s3_client().upload_fileobj(
        file,
        bucket,
        storage_key,
        ExtraArgs=extra_args,
    )


def s3_download_url(storage_key: str) -> dict:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("Falta configurar S3_BUCKET")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    url = _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": storage_key},
        ExpiresIn=600,
    )
    return {"url": url, "expires_at": expires_at.isoformat()}


def _firebase_bucket():
    import firebase_admin
    from firebase_admin import credentials, storage

    bucket_name = os.getenv("FIREBASE_BUCKET")
    credentials_path = os.getenv("FIREBASE_CREDENTIALS")
    if not bucket_name:
        raise RuntimeError("Falta configurar FIREBASE_BUCKET")

    if not firebase_admin._apps:
        options = {"credential": credentials.ApplicationDefault()}
        if credentials_path:
            options["credential"] = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(options["credential"], {"storageBucket": bucket_name})
    return storage.bucket(bucket_name)


def save_firebase(storage_key: str, file: BinaryIO, content_type: str | None) -> None:
    file.seek(0)
    blob = _firebase_bucket().blob(storage_key)
    blob.upload_from_file(file, content_type=content_type)


def firebase_download_url(storage_key: str) -> dict:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    blob = _firebase_bucket().blob(storage_key)
    if not blob.exists():
        return None
    url = blob.generate_signed_url(expiration=timedelta(minutes=10), method="GET", version="v4")
    return {"url": url, "expires_at": expires_at.isoformat()}
