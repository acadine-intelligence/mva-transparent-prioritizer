from __future__ import annotations

import json
import os
import posixpath
import shutil
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO

from .paths import hash_regular_input, validate_directory_root
from .reference_bundle import ReferenceArtifact, ReferenceBundle

COPY_CHUNK_BYTES = 1_048_576
MAX_ARCHIVE_MEMBERS = 2_000_000
MAX_EXPANDED_BYTES = 400_000_000_000
ARCHIVE_KINDS = {"archive", "data-zip", "source-tar"}
PLAIN_KINDS = {"reference-gzip", "tabix-index", "vcf-gzip"}


@dataclass(frozen=True)
class ReferenceInstallation:
    state: str
    file_count: int
    directory_count: int
    byte_count: int


@dataclass
class _Inventory:
    files: int
    directories: set[str]
    bytes: int
    members: int


def install_reference_artifact(
    private_root: Path,
    bundle: ReferenceBundle,
    artifact_name: str,
) -> ReferenceInstallation:
    private = validate_directory_root(Path(private_root))
    artifact = next(
        (candidate for candidate in bundle.artifacts if candidate.name == artifact_name),
        None,
    )
    if artifact is None:
        raise ValueError("unknown_reference_artifact")
    if artifact.expected_sha256 is None:
        raise ValueError("unresolved_reference_digest")

    relative_source = (
        f"references/{bundle.bundle_version}/downloads/verified/{artifact.filename}"
    )
    measured = hash_regular_input(
        private,
        relative_source,
        max_bytes=artifact.expected_bytes,
    )
    if (
        measured.byte_count != artifact.expected_bytes
        or measured.sha256 != artifact.expected_sha256
    ):
        raise ValueError("stale_reference_bundle")

    bundle_root = _ensure_directories(private, "references", bundle.bundle_version)
    installed_root = _ensure_directories(bundle_root, "installed")
    staging_root = _ensure_directories(bundle_root, ".installation-staging")
    target = installed_root / artifact.name
    if os.path.lexists(target):
        raise ValueError("existing_reference_installation")

    staging = Path(
        tempfile.mkdtemp(
            prefix=f"{artifact.name}.",
            dir=staging_root,
        )
    )
    staging.chmod(0o700)
    source_path = private / relative_source
    try:
        if artifact.install_kind in ARCHIVE_KINDS:
            inventory = _extract_archive(source_path, staging, artifact)
        elif artifact.install_kind in PLAIN_KINDS:
            inventory = _copy_plain_asset(source_path, staging, artifact)
        else:
            raise ValueError("unsupported_install_kind")

        receipt = {
            "artifact_name": artifact.name,
            "bundle_version": bundle.bundle_version,
            "byte_count": inventory.bytes,
            "directory_count": len(inventory.directories),
            "file_count": inventory.files,
            "schema_version": 1,
            "source_sha256": measured.sha256,
            "state": "installed",
        }
        receipt_path = staging / ".installation-receipt.json"
        _write_new_file(
            receipt_path,
            (
                json.dumps(
                    receipt,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8"),
            executable=False,
        )
        _freeze_tree(staging)
        staging_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            staging_descriptor = os.open(staging, staging_flags)
        except OSError:
            raise ValueError("reference_installation_failed") from None
        try:
            opened = os.fstat(staging_descriptor)
            before = staging.lstat()
            if (
                not stat.S_ISDIR(opened.st_mode)
                or stat.S_ISLNK(before.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            ):
                raise ValueError("reference_installation_failed")
            try:
                os.rename(staging, target)
            except FileExistsError:
                raise ValueError("existing_reference_installation") from None
            except OSError as exc:
                raise ValueError("reference_installation_failed") from exc
            os.fchmod(staging_descriptor, 0o500)
            os.fsync(staging_descriptor)
        finally:
            os.close(staging_descriptor)
    except Exception:
        if staging.exists():
            _thaw_tree(staging)
            shutil.rmtree(staging)
        raise

    return ReferenceInstallation(
        state="installed",
        file_count=inventory.files,
        directory_count=len(inventory.directories),
        byte_count=inventory.bytes,
    )


def _extract_archive(
    source_path: Path,
    destination: Path,
    artifact: ReferenceArtifact,
) -> _Inventory:
    if artifact.filename.endswith(".zip"):
        return _extract_zip(source_path, destination, artifact)
    if artifact.filename.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
        return _extract_tar(source_path, destination, artifact)
    raise ValueError("unsupported_archive_format")


def _extract_tar(
    source_path: Path,
    destination: Path,
    artifact: ReferenceArtifact,
) -> _Inventory:
    inventory = _Inventory(files=0, directories=set(), bytes=0, members=0)
    with _open_regular_nofollow(source_path) as source:
        try:
            archive = tarfile.open(fileobj=source, mode="r:*")
        except (tarfile.TarError, OSError):
            raise ValueError("invalid_reference_archive") from None
        with archive:
            members: dict[str, tarfile.TarInfo] = {}
            for member in archive:
                inventory.members += 1
                _check_inventory_limits(inventory, artifact)
                if not member.isfile() and not member.isdir() and not member.issym():
                    raise ValueError("unsafe_archive_member")
                parts = _safe_member_parts(member.name, is_directory=member.isdir())
                normalized = "/".join(parts)
                if normalized in members:
                    raise ValueError("unsafe_archive_member")
                if member.isfile() and member.size < 0:
                    raise ValueError("unsafe_archive_member")
                members[normalized] = member

            _validate_tar_namespace(members)
            link_order, link_targets = _plan_tar_links(members)

            for normalized, member in members.items():
                parts = tuple(normalized.split("/"))
                if member.isdir():
                    _ensure_member_directory(destination, parts, inventory.directories)

            for normalized, member in members.items():
                if not member.isfile():
                    continue
                parts = tuple(normalized.split("/"))
                inventory.bytes += member.size
                _check_inventory_limits(inventory, artifact)
                parent = _ensure_member_directory(
                    destination,
                    parts[:-1],
                    inventory.directories,
                )
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError("invalid_reference_archive")
                _stream_new_file(
                    parent / parts[-1],
                    extracted,
                    member.size,
                    executable=bool(member.mode & 0o111),
                )
                inventory.files += 1

            for link_path in link_order:
                _materialize_tar_link(
                    destination,
                    link_path,
                    link_targets[link_path],
                    inventory,
                    artifact,
                )
    return inventory


def _validate_tar_namespace(members: dict[str, tarfile.TarInfo]) -> None:
    for normalized in members:
        parts = normalized.split("/")
        for index in range(1, len(parts)):
            ancestor = "/".join(parts[:index])
            member = members.get(ancestor)
            if member is not None and not member.isdir():
                raise ValueError("unsafe_archive_member")


def _plan_tar_links(
    members: dict[str, tarfile.TarInfo],
) -> tuple[list[str], dict[str, str]]:
    plans: dict[str, set[str]] = {}
    targets: dict[str, str] = {}
    link_paths = sorted(
        normalized for normalized, member in members.items() if member.issym()
    )
    for link_path in link_paths:
        member = members[link_path]
        initial_target = _normalize_tar_link_target(link_path, member.linkname)
        target, dependencies = _resolve_tar_target(initial_target, members)
        target_member = members[target]
        if member.linkname.endswith("/") and not target_member.isdir():
            raise ValueError("unsafe_archive_member")
        if target_member.isdir():
            prefix = f"{target}/"
            dependencies.update(
                candidate
                for candidate in link_paths
                if candidate.startswith(prefix)
            )
        if link_path in dependencies:
            raise ValueError("unsafe_archive_member")
        plans[link_path] = dependencies
        targets[link_path] = target

    order: list[str] = []
    states: dict[str, int] = {}

    def visit(link_path: str) -> None:
        state = states.get(link_path, 0)
        if state == 1:
            raise ValueError("unsafe_archive_member")
        if state == 2:
            return
        states[link_path] = 1
        for dependency in sorted(plans[link_path]):
            if dependency not in plans:
                raise ValueError("unsafe_archive_member")
            visit(dependency)
        states[link_path] = 2
        order.append(link_path)

    for link_path in link_paths:
        visit(link_path)
    return order, targets


def _normalize_tar_link_target(link_path: str, linkname: str) -> str:
    if (
        not isinstance(linkname, str)
        or not linkname
        or linkname.startswith("/")
        or "//" in linkname
        or any(part == "." for part in linkname.split("/"))
        or "\\" in linkname
        or "\x00" in linkname
        or len(linkname.encode("utf-8")) > 4096
        or any(ord(character) < 32 or ord(character) == 127 for character in linkname)
    ):
        raise ValueError("unsafe_archive_member")
    normalized = posixpath.normpath(
        posixpath.join(posixpath.dirname(link_path), linkname)
    )
    if normalized in {"", ".", ".."} or normalized.startswith("../") or normalized.startswith("/"):
        raise ValueError("unsafe_archive_member")
    parts = _safe_member_parts(normalized, is_directory=False)
    return "/".join(parts)


def _resolve_tar_target(
    initial_target: str,
    members: dict[str, tarfile.TarInfo],
) -> tuple[str, set[str]]:
    current = initial_target
    dependencies: set[str] = set()
    active: set[str] = set()
    while True:
        parts = current.split("/")
        replaced = False
        for index in range(len(parts)):
            candidate = "/".join(parts[: index + 1])
            member = members.get(candidate)
            if member is None:
                raise ValueError("unsafe_archive_member")
            if member.issym():
                if candidate in active:
                    raise ValueError("unsafe_archive_member")
                active.add(candidate)
                dependencies.add(candidate)
                replacement = _normalize_tar_link_target(candidate, member.linkname)
                suffix = parts[index + 1 :]
                combined = posixpath.join(replacement, *suffix) if suffix else replacement
                current = "/".join(_safe_member_parts(combined, is_directory=False))
                replaced = True
                break
            if index < len(parts) - 1 and not member.isdir():
                raise ValueError("unsafe_archive_member")
            if index == len(parts) - 1 and not member.isfile() and not member.isdir():
                raise ValueError("unsafe_archive_member")
        if replaced:
            continue
        final = members.get(current)
        if final is None or (not final.isfile() and not final.isdir()):
            raise ValueError("unsafe_archive_member")
        return current, dependencies


def _materialize_tar_link(
    destination: Path,
    link_path: str,
    target_path: str,
    inventory: _Inventory,
    artifact: ReferenceArtifact,
) -> None:
    source = destination.joinpath(*target_path.split("/"))
    target = destination.joinpath(*link_path.split("/"))
    if os.path.lexists(target):
        raise ValueError("unsafe_archive_member")
    _copy_materialized_node(
        source,
        target,
        destination,
        inventory,
        artifact,
    )


def _copy_materialized_node(
    source: Path,
    target: Path,
    destination_root: Path,
    inventory: _Inventory,
    artifact: ReferenceArtifact,
) -> None:
    metadata = source.lstat()
    if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
        try:
            target.mkdir(mode=0o700)
        except OSError:
            raise ValueError("unsafe_archive_member") from None
        inventory.members += 1
        inventory.directories.add(target.relative_to(destination_root).as_posix())
        _check_inventory_limits(inventory, artifact)
        try:
            children = sorted(os.scandir(source), key=lambda entry: entry.name)
        except OSError:
            raise ValueError("unsafe_archive_member") from None
        for child in children:
            _copy_materialized_node(
                Path(child.path),
                target / child.name,
                destination_root,
                inventory,
                artifact,
            )
        return
    if stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
        inventory.members += 1
        inventory.bytes += metadata.st_size
        _check_inventory_limits(inventory, artifact)
        with _open_regular_nofollow(source) as opened:
            _stream_new_file(
                target,
                opened,
                metadata.st_size,
                executable=bool(metadata.st_mode & 0o111),
            )
        inventory.files += 1
        return
    raise ValueError("unsafe_archive_member")


def _extract_zip(
    source_path: Path,
    destination: Path,
    artifact: ReferenceArtifact,
) -> _Inventory:
    inventory = _Inventory(files=0, directories=set(), bytes=0, members=0)
    seen: set[str] = set()
    with _open_regular_nofollow(source_path) as source:
        try:
            archive = zipfile.ZipFile(source, mode="r")
        except (zipfile.BadZipFile, OSError):
            raise ValueError("invalid_reference_archive") from None
        with archive:
            for member in archive.infolist():
                inventory.members += 1
                _check_inventory_limits(inventory, artifact)
                unix_mode = (member.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(unix_mode)
                if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise ValueError("unsafe_archive_member")
                is_directory = member.is_dir() or file_type == stat.S_IFDIR
                parts = _safe_member_parts(member.filename, is_directory=is_directory)
                normalized = "/".join(parts)
                if normalized in seen:
                    raise ValueError("unsafe_archive_member")
                seen.add(normalized)
                if is_directory:
                    _ensure_member_directory(destination, parts, inventory.directories)
                    continue
                inventory.bytes += member.file_size
                _check_inventory_limits(inventory, artifact)
                if member.compress_size > 0 and member.file_size > member.compress_size * 10_000:
                    raise ValueError("archive_expansion_limit")
                parent = _ensure_member_directory(
                    destination,
                    parts[:-1],
                    inventory.directories,
                )
                try:
                    extracted = archive.open(member, mode="r")
                except (RuntimeError, zipfile.BadZipFile):
                    raise ValueError("invalid_reference_archive") from None
                with extracted:
                    _stream_new_file(
                        parent / parts[-1],
                        extracted,
                        member.file_size,
                        executable=bool(unix_mode & 0o111),
                    )
                inventory.files += 1
    return inventory


def _copy_plain_asset(
    source_path: Path,
    destination: Path,
    artifact: ReferenceArtifact,
) -> _Inventory:
    with _open_regular_nofollow(source_path) as source:
        _stream_new_file(
            destination / artifact.filename,
            source,
            artifact.expected_bytes,
            executable=False,
        )
    return _Inventory(
        files=1,
        directories=set(),
        bytes=artifact.expected_bytes,
        members=1,
    )


def _safe_member_parts(name: str, *, is_directory: bool) -> tuple[str, ...]:
    if not isinstance(name, str):
        raise ValueError("unsafe_archive_member")
    normalized = name[:-1] if is_directory and name.endswith("/") else name
    if (
        not normalized
        or normalized.startswith("/")
        or normalized.endswith("/")
        or "//" in normalized
        or any(part == "." for part in normalized.split("/"))
        or "\\" in normalized
        or "\x00" in normalized
        or len(normalized.encode("utf-8")) > 4096
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ValueError("unsafe_archive_member")
    parts = PurePosixPath(normalized).parts
    if (
        not parts
        or any(
            part in {"", ".", ".."} or len(part.encode("utf-8")) > 255
            for part in parts
        )
    ):
        raise ValueError("unsafe_archive_member")
    return parts


def _ensure_member_directory(
    root: Path,
    parts: tuple[str, ...],
    inventory: set[str],
) -> Path:
    current = root
    relative_parts: list[str] = []
    for part in parts:
        relative_parts.append(part)
        candidate = current / part
        try:
            candidate.mkdir(mode=0o700)
        except FileExistsError:
            metadata = candidate.lstat()
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("unsafe_archive_member") from None
        inventory.add("/".join(relative_parts))
        current = candidate
    return current


def _stream_new_file(
    path: Path,
    source: IO[bytes],
    expected_bytes: int,
    *,
    executable: bool,
) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o700 if executable else 0o600)
    except OSError:
        raise ValueError("unsafe_archive_member") from None
    written = 0
    try:
        while written < expected_bytes:
            chunk = source.read(min(COPY_CHUNK_BYTES, expected_bytes - written))
            if not chunk:
                raise ValueError("invalid_reference_archive")
            view = memoryview(chunk)
            while view:
                count = os.write(descriptor, view)
                view = view[count:]
            written += len(chunk)
        if source.read(1):
            raise ValueError("invalid_reference_archive")
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o500 if executable else 0o400)
    finally:
        os.close(descriptor)


def _write_new_file(path: Path, content: bytes, *, executable: bool) -> None:
    with io_bytes(content) as source:
        _stream_new_file(
            path,
            source,
            len(content),
            executable=executable,
        )


def io_bytes(content: bytes) -> IO[bytes]:
    from io import BytesIO

    return BytesIO(content)


def _open_regular_nofollow(path: Path) -> IO[bytes]:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("stale_reference_bundle")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ValueError("stale_reference_bundle") from None
    opened = os.fstat(descriptor)
    if (
        not stat.S_ISREG(opened.st_mode)
        or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)
    ):
        os.close(descriptor)
        raise ValueError("stale_reference_bundle")
    return os.fdopen(descriptor, "rb")


def _check_inventory_limits(
    inventory: _Inventory,
    artifact: ReferenceArtifact,
) -> None:
    expanded_limit = min(
        MAX_EXPANDED_BYTES,
        max(1_073_741_824, artifact.expected_bytes * 40),
    )
    if inventory.members > MAX_ARCHIVE_MEMBERS or inventory.bytes > expanded_limit:
        raise ValueError("archive_expansion_limit")


def _ensure_directories(root: Path, *parts: str) -> Path:
    current = Path(root)
    for part in parts:
        if not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise ValueError("invalid_private_directory")
        candidate = current / part
        try:
            candidate.mkdir(mode=0o700)
        except FileExistsError:
            metadata = candidate.lstat()
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("invalid_private_directory") from None
        current = candidate
    return current


def _freeze_tree(root: Path) -> None:
    directories: list[Path] = []
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories.append(current_path)
        for name in directory_names:
            candidate = current_path / name
            metadata = candidate.lstat()
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("unsafe_archive_member")
        for name in file_names:
            candidate = current_path / name
            metadata = candidate.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("unsafe_archive_member")
            candidate.chmod(0o500 if metadata.st_mode & 0o111 else 0o400)
    for directory in reversed(directories):
        if directory != root:
            directory.chmod(0o500)


def _thaw_tree(root: Path) -> None:
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        current_path.chmod(0o700)
        for name in directory_names:
            candidate = current_path / name
            metadata = candidate.lstat()
            if stat.S_ISDIR(metadata.st_mode):
                candidate.chmod(0o700)
        for name in file_names:
            candidate = current_path / name
            metadata = candidate.lstat()
            if stat.S_ISREG(metadata.st_mode):
                candidate.chmod(0o600)
