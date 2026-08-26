from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class PathSecurityError(ValueError):
    """Raised when a path crosses the private workspace boundary."""


@dataclass(frozen=True)
class RootPair:
    public_root: Path
    private_root: Path


@dataclass(frozen=True)
class FileDigest:
    byte_count: int
    sha256: str
    md5: str


def validate_root_pair(public_root: Path, private_root: Path) -> RootPair:
    public_input = Path(public_root)
    private_input = Path(private_root)
    for candidate in (public_input, private_input):
        descriptor = _open_directory_nofollow(candidate)
        os.close(descriptor)
    public = public_input.resolve(strict=True)
    private = private_input.resolve(strict=True)
    if public == private or public in private.parents or private in public.parents:
        raise PathSecurityError("root_overlap")
    return RootPair(public_root=public, private_root=private)


def validate_directory_root(root: Path) -> Path:
    candidate = Path(root)
    descriptor = _open_directory_nofollow(candidate)
    os.close(descriptor)
    return candidate.resolve(strict=True)


def read_regular_input(private_root: Path, relative_path: str, max_bytes: int) -> bytes:
    parts = validate_relative_path(relative_path)
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
        raise PathSecurityError("invalid_size_limit")

    directory_fd = _open_directory_nofollow(Path(private_root))
    try:
        for part in parts[:-1]:
            child_fd = _open_child_directory(directory_fd, part)
            os.close(directory_fd)
            directory_fd = child_fd

        file_stat = _stat_child(directory_fd, parts[-1])
        if stat.S_ISLNK(file_stat.st_mode):
            raise PathSecurityError("symlink_component")
        if not stat.S_ISREG(file_stat.st_mode):
            raise PathSecurityError("not_regular")
        if file_stat.st_size > max_bytes:
            raise PathSecurityError("size_limit")

        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            file_fd = os.open(parts[-1], flags, dir_fd=directory_fd)
        except OSError as exc:
            raise _mapped_open_error(exc) from None
        try:
            opened_stat = os.fstat(file_fd)
            if not stat.S_ISREG(opened_stat.st_mode):
                raise PathSecurityError("not_regular")
            if (opened_stat.st_dev, opened_stat.st_ino) != (file_stat.st_dev, file_stat.st_ino):
                raise PathSecurityError("path_changed")
            with os.fdopen(file_fd, "rb", closefd=False) as handle:
                content = handle.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise PathSecurityError("size_limit")
            return content
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)


def hash_regular_input(
    private_root: Path,
    relative_path: str,
    *,
    max_bytes: int,
    chunk_bytes: int = 1_048_576,
) -> FileDigest:
    parts = validate_relative_path(relative_path)
    if (
        not isinstance(max_bytes, int)
        or isinstance(max_bytes, bool)
        or max_bytes < 0
        or not isinstance(chunk_bytes, int)
        or isinstance(chunk_bytes, bool)
        or chunk_bytes <= 0
        or chunk_bytes > 16_777_216
    ):
        raise PathSecurityError("invalid_size_limit")

    directory_fd = _open_directory_nofollow(Path(private_root))
    try:
        for part in parts[:-1]:
            child_fd = _open_child_directory(directory_fd, part)
            os.close(directory_fd)
            directory_fd = child_fd

        file_stat = _stat_child(directory_fd, parts[-1])
        if stat.S_ISLNK(file_stat.st_mode):
            raise PathSecurityError("symlink_component")
        if not stat.S_ISREG(file_stat.st_mode):
            raise PathSecurityError("not_regular")
        if file_stat.st_size > max_bytes:
            raise PathSecurityError("size_limit")

        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            file_fd = os.open(parts[-1], flags, dir_fd=directory_fd)
        except OSError as exc:
            raise _mapped_open_error(exc) from None
        try:
            opened_stat = os.fstat(file_fd)
            if not stat.S_ISREG(opened_stat.st_mode):
                raise PathSecurityError("not_regular")
            if (opened_stat.st_dev, opened_stat.st_ino) != (file_stat.st_dev, file_stat.st_ino):
                raise PathSecurityError("path_changed")
            sha256_digest = hashlib.sha256()
            md5_digest = hashlib.md5()
            byte_count = 0
            while True:
                chunk = os.read(file_fd, chunk_bytes)
                if not chunk:
                    break
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise PathSecurityError("size_limit")
                sha256_digest.update(chunk)
                md5_digest.update(chunk)
            final_stat = os.fstat(file_fd)
            if (
                final_stat.st_size != opened_stat.st_size
                or final_stat.st_mtime_ns != opened_stat.st_mtime_ns
                or final_stat.st_ctime_ns != opened_stat.st_ctime_ns
            ):
                raise PathSecurityError("path_changed")
            return FileDigest(
                byte_count=byte_count,
                sha256=sha256_digest.hexdigest(),
                md5=md5_digest.hexdigest(),
            )
        finally:
            os.close(file_fd)
    finally:
        os.close(directory_fd)


def validate_relative_path(relative_path: str) -> tuple[str, ...]:
    if not isinstance(relative_path, str):
        raise PathSecurityError("invalid_relative_path")
    if (
        not relative_path
        or relative_path in {".", ".."}
        or relative_path.startswith("/")
        or relative_path.endswith("/")
        or "//" in relative_path
        or "\\" in relative_path
        or any(part in {"", ".", ".."} for part in relative_path.split("/"))
        or len(relative_path.encode("utf-8")) > 4096
        or any(ord(character) < 32 or ord(character) == 127 for character in relative_path)
    ):
        raise PathSecurityError("invalid_relative_path")
    parts = PurePosixPath(relative_path).parts
    if not parts or any(part in {"", ".", ".."} or len(part.encode("utf-8")) > 255 for part in parts):
        raise PathSecurityError("invalid_relative_path")
    return parts


def _open_directory_nofollow(path: Path) -> int:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_absolute():
        raise PathSecurityError("invalid_root")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise _mapped_open_error(exc) from None
    try:
        for part in absolute.parts[1:]:
            child_fd = _open_child_directory(descriptor, part)
            os.close(descriptor)
            descriptor = child_fd
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_child_directory(parent_fd: int, name: str) -> int:
    child_stat = _stat_child(parent_fd, name)
    if stat.S_ISLNK(child_stat.st_mode):
        raise PathSecurityError("symlink_component")
    if not stat.S_ISDIR(child_stat.st_mode):
        raise PathSecurityError("not_directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        child_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise _mapped_open_error(exc) from None
    opened_stat = os.fstat(child_fd)
    if (opened_stat.st_dev, opened_stat.st_ino) != (child_stat.st_dev, child_stat.st_ino):
        os.close(child_fd)
        raise PathSecurityError("path_changed")
    return child_fd


def _stat_child(parent_fd: int, name: str) -> os.stat_result:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise _mapped_open_error(exc) from None


def _mapped_open_error(exc: OSError) -> PathSecurityError:
    if exc.errno == errno.ELOOP:
        return PathSecurityError("symlink_component")
    return PathSecurityError("input_unavailable")
