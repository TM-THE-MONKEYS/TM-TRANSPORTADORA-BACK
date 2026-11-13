"""Supabase Storage REST client (no supabase-py)."""
from __future__ import annotations

from urllib.parse import quote

import httpx
import structlog

from app.core.config.settings import get_settings
from app.shared.http_client import create_http_client
from app.shared.storage.errors import StorageBackendError, StorageObjectNotFoundError

log = structlog.get_logger(__name__)


def _base_url() -> str:
    return get_settings().supabase_url.rstrip("/")


def _object_url(bucket: str, storage_path: str) -> str:
    encoded = quote(storage_path.replace("\\", "/"), safe="/")
    return f"{_base_url()}/storage/v1/object/{bucket}/{encoded}"


def _auth_headers(content_type: str | None = None) -> dict[str, str]:
    """Auth Storage: Secret key nova vai em `apikey`; JWT legacy também em Bearer."""
    key = get_settings().supabase_elevated_key()
    headers = {"apikey": key}
    # JWT legacy service_role ainda usa Authorization: Bearer
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    else:
        # Compat: várias rotas Storage ainda aceitam Bearer com sb_secret_
        headers["Authorization"] = f"Bearer {key}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _map_response_error(
    operation: str,
    storage_path: str,
    response: httpx.Response,
) -> StorageBackendError:
    return StorageBackendError(
        f"Supabase Storage {operation} failed",
        operation=operation,
        status_code=response.status_code,
        storage_path=storage_path,
    )


async def upload_object(
    bucket: str,
    storage_path: str,
    content: bytes,
    content_type: str,
) -> None:
    url = _object_url(bucket, storage_path)
    headers = _auth_headers(content_type)
    headers["x-upsert"] = "false"
    try:
        async with create_http_client() as client:
            response = await client.post(url, headers=headers, content=content)
    except httpx.HTTPError as exc:
        log.error(
            "supabase_storage_upload_failed",
            operation="upload",
            storage_path=storage_path,
            bucket=bucket,
            error_type=type(exc).__name__,
        )
        raise StorageBackendError(
            "Falha de rede ao enviar arquivo para o storage",
            operation="upload",
            storage_path=storage_path,
        ) from exc

    if response.status_code in (200, 201):
        return
    log.error(
        "supabase_storage_upload_rejected",
        operation="upload",
        storage_path=storage_path,
        bucket=bucket,
        http_status=response.status_code,
    )
    raise _map_response_error("upload", storage_path, response)


async def download_object(bucket: str, storage_path: str) -> bytes:
    url = _object_url(bucket, storage_path)
    headers = _auth_headers()
    try:
        async with create_http_client() as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        log.error(
            "supabase_storage_download_failed",
            operation="download",
            storage_path=storage_path,
            bucket=bucket,
            error_type=type(exc).__name__,
        )
        raise StorageBackendError(
            "Falha de rede ao baixar arquivo do storage",
            operation="download",
            storage_path=storage_path,
        ) from exc

    if response.status_code == 404:
        raise StorageObjectNotFoundError(storage_path)
    if response.status_code == 200:
        return response.content

    log.error(
        "supabase_storage_download_rejected",
        operation="download",
        storage_path=storage_path,
        bucket=bucket,
        http_status=response.status_code,
    )
    raise _map_response_error("download", storage_path, response)


async def delete_object(bucket: str, storage_path: str) -> None:
    url = _object_url(bucket, storage_path)
    headers = _auth_headers()
    try:
        async with create_http_client() as client:
            response = await client.delete(url, headers=headers)
    except httpx.HTTPError as exc:
        log.error(
            "supabase_storage_delete_failed",
            operation="delete",
            storage_path=storage_path,
            bucket=bucket,
            error_type=type(exc).__name__,
        )
        raise StorageBackendError(
            "Falha de rede ao remover arquivo do storage",
            operation="delete",
            storage_path=storage_path,
        ) from exc

    if response.status_code in (200, 204, 404):
        return

    log.error(
        "supabase_storage_delete_rejected",
        operation="delete",
        storage_path=storage_path,
        bucket=bucket,
        http_status=response.status_code,
    )
    raise _map_response_error("delete", storage_path, response)
