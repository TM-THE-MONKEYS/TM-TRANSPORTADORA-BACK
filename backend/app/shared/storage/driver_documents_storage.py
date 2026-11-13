"""Facade for driver document blobs (local disk or Supabase Storage)."""
from __future__ import annotations

import uuid
from typing import Literal

from app.core.config.settings import get_settings
from app.shared.storage import local_files, supabase_files
from app.shared.storage.errors import StorageObjectNotFoundError

StorageBackendName = Literal["local", "supabase"]


def _looks_like_elevated_key(key: str) -> bool:
    """Aceita JWT legacy service_role (eyJ…) ou Secret key nova (sb_secret_…)."""
    k = key.strip()
    if not k:
        return False
    if k.startswith("sb_secret_"):
        return True
    # Legacy service_role JWT
    return k.startswith("eyJ") and len(k) > 50


def effective_storage_backend() -> StorageBackendName:
    settings = get_settings()
    mode = settings.storage_backend
    if mode == "local":
        return "local"
    if mode == "supabase":
        return "supabase"
    url = (settings.supabase_url or "").strip()
    key = settings.supabase_elevated_key()
    if url and _looks_like_elevated_key(key):
        return "supabase"
    return "local"


async def save_driver_document_bytes(
    tenant_id: uuid.UUID,
    driver_id: uuid.UUID,
    filename: str,
    content: bytes,
    content_type: str,
) -> str:
    rel = local_files.driver_document_relative_path(tenant_id, driver_id, filename)
    if effective_storage_backend() == "local":
        return local_files.save_driver_document_bytes(
            tenant_id, driver_id, filename, content
        )
    bucket = get_settings().supabase_storage_bucket
    await supabase_files.upload_object(bucket, rel, content, content_type)
    return rel.replace("\\", "/")


async def read_driver_document_bytes(storage_path: str) -> bytes:
    if effective_storage_backend() == "local":
        path = local_files.resolve_storage_path(storage_path)
        if not path.is_file():
            raise StorageObjectNotFoundError(storage_path)
        return path.read_bytes()
    bucket = get_settings().supabase_storage_bucket
    return await supabase_files.download_object(bucket, storage_path)


async def delete_driver_document(storage_path: str) -> None:
    if effective_storage_backend() == "local":
        local_files.delete_storage_file(storage_path)
        return
    bucket = get_settings().supabase_storage_bucket
    await supabase_files.delete_object(bucket, storage_path)
