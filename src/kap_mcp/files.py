from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

from .errors import FILE_EXISTS, UNSAFE_PATH, UNSUPPORTED_DOCUMENT, KapError


_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"PK\x03\x04", "application/zip", ".zip"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/vnd.ms-excel", ".xls"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
)


@dataclass(frozen=True, slots=True)
class VerifiedFile:
    content: bytes
    mime_type: str
    extension: str
    sha256: str
    wrapper_bytes_removed: int

    def as_content(self) -> str:
        return base64.b64encode(self.content).decode("ascii")


def verify_file(content: bytes, content_type: str | None = None, *, max_bytes: int = 25_000_000) -> VerifiedFile:
    if not content:
        raise KapError(UNSUPPORTED_DOCUMENT, "KAP boş dosya döndürdü.")
    if len(content) > max_bytes:
        raise KapError(UNSUPPORTED_DOCUMENT, "Dosya izin verilen boyut sınırını aşıyor.", context={"size_bytes": len(content), "max_bytes": max_bytes})
    candidates: list[tuple[int, bytes, str, str]] = []
    for signature, mime, extension in _SIGNATURES:
        offset = content.find(signature, 0, min(len(content), 4096))
        if offset >= 0:
            candidates.append((offset, signature, mime, extension))
    if not candidates:
        raise KapError(UNSUPPORTED_DOCUMENT, "Dosyanın gerçek imzası tanınmadı.", context={"content_type": content_type})
    offset, _, mime, extension = min(candidates, key=lambda item: item[0])
    # Only Java ObjectOutputStream-wrapped data may have a prefix.
    if offset and not content.startswith(b"\xac\xed\x00\x05"):
        raise KapError(UNSUPPORTED_DOCUMENT, "Dosya imzasından önce doğrulanamayan veri var.", context={"signature_offset": offset})
    clean = content[offset:]
    if not any(clean.startswith(signature) and actual_mime == mime for signature, actual_mime, _ in _SIGNATURES):
        raise KapError(UNSUPPORTED_DOCUMENT, "Temizlenen dosya imza doğrulamasını geçemedi.")
    return VerifiedFile(clean, mime, extension, hashlib.sha256(clean).hexdigest(), offset)


class SafeFileStore:
    def __init__(self, allowed_root: str | Path | None = None) -> None:
        configured = allowed_root or os.getenv("KAP_MCP_DOWNLOAD_DIR") or (Path.home() / "Downloads" / "kap-mcp")
        self.allowed_root = Path(configured).expanduser().resolve()

    def _safe_destination(self, directory: str | None, name: str) -> Path:
        if Path(name).name != name or name in {"", ".", ".."}:
            raise KapError(UNSAFE_PATH, "Çıktı adı yalnızca bir dosya adı olmalıdır.")
        root = self.allowed_root
        target_dir = Path(directory).expanduser() if directory else root
        target_dir = target_dir.resolve(strict=False)
        if not target_dir.is_relative_to(root):
            raise KapError(UNSAFE_PATH, "Çıktı dizini izin verilen kökün dışında.", context={"allowed_root": str(root)})
        current = root
        relative = target_dir.relative_to(root)
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise KapError(UNSAFE_PATH, "Sembolik bağlantı üzerinden dizin kaçışı engellendi.")
        return target_dir / name

    def save(self, verified: VerifiedFile, *, directory: str | None, name: str, overwrite: bool = False) -> Path:
        destination = self._safe_destination(directory, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not overwrite:
            raise KapError(FILE_EXISTS, "Hedef dosya zaten var.", context={"path": str(destination)})
        flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if overwrite else os.O_EXCL)
        try:
            descriptor = os.open(destination, flags, 0o600)
        except FileExistsError as exc:
            raise KapError(FILE_EXISTS, "Hedef dosya zaten var.", context={"path": str(destination)}) from exc
        with os.fdopen(descriptor, "wb") as output:
            output.write(verified.content)
        return destination.resolve()


def mime_for_name(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"
