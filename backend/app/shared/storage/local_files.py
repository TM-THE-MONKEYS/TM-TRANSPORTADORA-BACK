"""Local filesystem storage for uploads."""
from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config.settings import get_settings

ALLOWED_DRIVER_DOCUMENT_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
})

_EXTENSION_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def normalize_driver_document_content_type(content_type: str, filename: str) -> str:
    """Accept browser octet-stream when extension is a known image/PDF."""
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in ALLOWED_DRIVER_DOCUMENT_TYPES:
        return ct
    ext = Path(filename).suffix.lower()
    inferred = _EXTENSION_MIME.get(ext)
    if inferred:
        return inferred
    return ct


def upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def driver_document_relative_path(tenant_id: uuid.UUID, driver_id: uuid.UUID, filename: str) -> str:
    safe_name = Path(filename).name.replace("..", "").strip() or "document"
    return f"{tenant_id}/{driver_id}/{uuid.uuid4()}_{safe_name}"


def save_driver_document_bytes(
    tenant_id: uuid.UUID,
    driver_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> str:
    rel = driver_document_relative_path(tenant_id, driver_id, filename)
    dest = upload_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return rel.replace("\\", "/")


def resolve_storage_path(storage_path: str) -> Path:
    root = upload_root().resolve()
    full = (root / storage_path).resolve()
    if not str(full).startswith(str(root)):
        raise ValueError("Invalid storage path")
    return full


def delete_storage_file(storage_path: str) -> None:
    path = resolve_storage_path(storage_path)
    if path.is_file():
        path.unlink()
