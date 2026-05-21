import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _validate_upload(upload: UploadFile) -> tuple[str, str]:
    if upload.filename is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Missing filename"
        )

    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension {ext!r}. Allowed: .pdf, .docx",
        )

    mime = upload.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type {mime!r}. Allowed: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    if ALLOWED_MIME_TYPES[mime] != ext:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="File extension does not match content type",
        )

    return ext, mime


def save_course_file(course_id: int, upload: UploadFile) -> tuple[Path, int, str, str]:
    """Validate and persist `upload` under UPLOAD_DIR/<course_id>/. Returns (path, size, mime, original_filename)."""
    ext, mime = _validate_upload(upload)

    data = upload.file.read()
    upload.file.close()

    size = len(data)
    if size > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_BYTES} bytes",
        )

    base_dir = Path(settings.UPLOAD_DIR) / str(course_id)
    base_dir.mkdir(parents=True, exist_ok=True)

    target = base_dir / f"{uuid.uuid4().hex}{ext}"
    target.write_bytes(data)

    return target, size, mime, upload.filename


def delete_stored_file(stored_path: str) -> None:
    path = Path(stored_path)
    if path.exists():
        path.unlink()
    md_sibling = path.with_suffix(path.suffix + ".md")
    if md_sibling.exists():
        md_sibling.unlink()
