"""
Upload validation: MIME type, extension, size, and filename safety.

Nothing here trusts a client-supplied filename or path — see
services/storage_service.build_safe_storage_path for how the actual
storage key is generated server-side instead.
"""
import re
import uuid

from fastapi import HTTPException, UploadFile, status

ALLOWED_INVENTORY_EXTENSIONS = {".csv", ".xlsx", ".xls"}
ALLOWED_INVENTORY_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}

# Browsers are inconsistent about the Content-Type they attach to a raw
# .html file input — Chrome sends "text/html", others fall back to
# "application/octet-stream" or leave it blank. The extension plus the
# real Jinja2/HTML parsing in template_engine.py are what actually gate
# acceptance; this MIME allow-list is deliberately permissive so a
# legitimate upload never gets rejected on a browser quirk.
ALLOWED_PLANTILLA_EXTENSIONS = {".html", ".htm"}
ALLOWED_PLANTILLA_MIME_TYPES = {"text/html", "application/octet-stream", ""}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB, matches the frontend's own copy ("máx. 10 MB")

_SAFE_TOKEN = re.compile(r"[^A-Za-z0-9_.-]")


def _extension_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def validate_upload(file: UploadFile, allowed_extensions: set[str], allowed_mime_types: set[str]) -> None:
    ext = _extension_of(file.filename or "")
    if ext not in allowed_extensions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de archivo no permitido.")
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de archivo no permitido.")


def validate_size(size_bytes: int, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    if size_bytes > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo supera el tamaño máximo permitido.")
    if size_bytes <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")


def safe_filename_component(original_filename: str) -> str:
    """Never used as the actual storage path — only kept, sanitized, as a
    human-readable suffix. The real path is always `generate_object_key`
    in storage_service.py, which is 100% server-generated."""
    base = original_filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return _SAFE_TOKEN.sub("_", base)[:80] or uuid.uuid4().hex
