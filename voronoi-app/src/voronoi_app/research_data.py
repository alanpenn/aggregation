"""Shared diagnostics paths and immutable filesystem publication."""
import ctypes
from hashlib import file_digest
import os
from pathlib import Path
import shutil
import sys
from tempfile import NamedTemporaryFile

ENV = "AGGREGATION_DATA_ROOT"


def data_root(local="diagnostics"):
    configured = os.environ.get(ENV)
    return Path(configured).expanduser().resolve() if configured else Path(local)


def data_path(relative="", *, local="diagnostics"):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Expected a path relative to the research-data root: {relative}")
    return data_root(local) / path


def logical_path(path):
    """Keep repository-relative archive member names portable across machines."""
    return Path("diagnostics") / Path(path).relative_to(data_root())


def unavailable(path):
    return (f"Research data unavailable at {path}. If using iCloud Drive, download the file or "
            f"choose Keep Downloaded in Finder, then retry. Check {ENV} if the path is unexpected.")


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def publish_exclusive(staging, target):
    if sys.platform == "darwin":
        # iCloud's File Provider denies hard links. macOS offers an atomic
        # same-volume rename that fails if the destination already exists.
        rename = ctypes.CDLL(None, use_errno=True).renamex_np
        rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        rename.restype = ctypes.c_int
        if rename(os.fsencode(staging), os.fsencode(target), 0x00000004):
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno), str(target))
    else:
        os.link(staging, target)


def copy_verified(source, target, expected=None):
    """Publish a verified regular file, preserving any conflicting destination."""
    source, target = Path(source), Path(target)
    if source.is_symlink() or any(p.is_symlink() for p in (target, *target.parents)):
        return "conflict"
    checksum = expected or sha256_file(source)
    if target.exists():
        return "identical" if target.is_file() and sha256_file(target) == checksum else "conflict"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except (NotADirectoryError, FileExistsError):
        return "conflict"
    if "com~apple~CloudDocs" in target.parts:
        # The File Provider can deny both hard links and exclusive renames.
        # Use exclusive creation and publish the checksum inventory separately.
        if sha256_file(source) != checksum:
            raise ValueError(f"Source checksum mismatch: {source}")
        try:
            with source.open("rb") as original, target.open("xb") as stream:
                shutil.copyfileobj(original, stream)
        except FileExistsError:
            return "identical" if target.is_file() and sha256_file(target) == checksum else "conflict"
        if sha256_file(target) != checksum:
            raise ValueError(f"Copied file checksum mismatch: {target}")
        return "copied"
    with NamedTemporaryFile(prefix=".incoming-", dir=target.parent, delete=False) as stream:
        staging = Path(stream.name)
        try:
            with source.open("rb") as original:
                shutil.copyfileobj(original, stream)
            stream.flush()
            if sha256_file(staging) != checksum:
                raise ValueError(f"Source checksum mismatch: {source}")
            try:
                publish_exclusive(staging, target)
            except FileExistsError:
                return "identical" if target.is_file() and sha256_file(target) == checksum else "conflict"
        finally:
            staging.unlink(missing_ok=True)
    return "copied"
