from __future__ import annotations

import hashlib
import json
import os
import platform
import plistlib
import socket
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .paths import (
    hash_regular_input,
    read_regular_input,
    validate_relative_path,
    validate_root_pair,
)
from .reference_bundle import ReferenceArtifact, ReferenceBundle, load_reference_bundle, verify_reference_bundle

MIN_FREE_BYTES = 100_000_000_000
MIN_MEMORY_BYTES = 7_500_000_000
CHECK_COUNT = 10
TOOL_VERSIONS = {
    "bcftools": "1.24",
    "bgzip": "1.24",
    "exomiser-cli": "15.1.0",
    "java": "21.0.12",
    "python": "3.11.16",
    "tabix": "1.24",
    "vep": "116.1",
}
TOOL_PATHS = {
    "python": "toolchain/{bundle}/runtime/python/bin/python3.11",
    "bcftools": "toolchain/{bundle}/runtime/bcftools/bin/bcftools",
    "bgzip": "toolchain/{bundle}/runtime/htslib/bin/bgzip",
    "tabix": "toolchain/{bundle}/runtime/htslib/bin/tabix",
    "java": "references/{bundle}/installed/openjdk-macos-aarch64/jdk-21.0.12.1+1/Contents/Home/bin/java",
    "exomiser-cli": "references/{bundle}/installed/exomiser-cli/exomiser-cli-15.1.0/exomiser-cli-15.1.0.jar",
    "vep": "references/{bundle}/installed/ensembl-vep-source/ensembl-vep-97c24b205f4ba8b44ccc75b839512a1d59104019/vep",
}
SUPPORT_VERSIONS = {
    "perl5-runtime": "Bio::DB::HTS 3.02",
    "vep-htslib": "1.13",
}
SUPPORT_PATHS = {
    "perl5-runtime": "toolchain/{bundle}/runtime/perl5",
    "vep-htslib": "toolchain/{bundle}/runtime/vep-htslib-1.13",
}
INSTALL_RECEIPT_FIELDS = {
    "artifact_name",
    "bundle_version",
    "byte_count",
    "directory_count",
    "file_count",
    "schema_version",
    "source_sha256",
    "state",
}
TOOLCHAIN_FIELDS = {"architecture", "bundle_version", "schema_version", "supports", "tools"}
TOOL_FIELDS = {"byte_count", "name", "relative_path", "sha256", "version"}
SUPPORT_FIELDS = {
    "byte_count",
    "directory_count",
    "file_count",
    "name",
    "relative_path",
    "tree_sha256",
    "version",
}


class _DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class SystemState:
    architecture: str
    encrypted_mount: bool
    free_bytes: int
    memory_bytes: int
    network_blocked: bool
    download_transport_closed: bool
    proxy_environment_clear: bool


@dataclass(frozen=True)
class EnvironmentHealth:
    state: str
    check_count: int
    artifact_count: int
    installed_count: int
    support_count: int
    tool_count: int


SystemProbe = Callable[[Path], SystemState]


def verify_environment(
    public_root: Path,
    private_root: Path,
    *,
    system_probe: Optional[SystemProbe] = None,
) -> EnvironmentHealth:
    roots = validate_root_pair(Path(public_root), Path(private_root))
    manifest_relative = "config/reference-bundle.json"
    manifest_path = roots.public_root / manifest_relative
    bundle = load_reference_bundle(manifest_path)
    if bundle.status != "verified" or bundle.bootstrap_count != 0:
        raise ValueError("unresolved_reference_digest")

    reference_result = verify_reference_bundle(roots.private_root, bundle)
    state = (system_probe or _probe_macos_environment)(roots.private_root)
    if (
        state.architecture != "arm64"
        or not state.encrypted_mount
        or state.free_bytes < MIN_FREE_BYTES
        or state.memory_bytes < MIN_MEMORY_BYTES
        or not state.network_blocked
        or not state.download_transport_closed
        or not state.proxy_environment_clear
    ):
        raise ValueError("environment_not_ready")

    installations = _verify_installations(roots.private_root, bundle)
    toolchain = _verify_toolchain(roots.private_root, bundle, state.architecture)
    manifest_digest = hash_regular_input(
        roots.public_root,
        manifest_relative,
        max_bytes=1_048_576,
    )
    payload = {
        "architecture": state.architecture,
        "artifact_count": reference_result.artifact_count,
        "bundle_version": bundle.bundle_version,
        "check_count": CHECK_COUNT,
        "download_transport_closed": True,
        "encrypted_mount": True,
        "installation_fingerprint": _canonical_sha256(installations),
        "installed_count": len(installations),
        "network_blocked": True,
        "proxy_environment_clear": True,
        "reference_byte_count": reference_result.byte_count,
        "reference_manifest_sha256": manifest_digest.sha256,
        "schema_version": 1,
        "state": "ready",
        "support_count": len(toolchain["supports"]),
        "tool_count": len(toolchain["tools"]),
        "toolchain_fingerprint": _canonical_sha256(toolchain),
    }
    content = _canonical_json(payload)
    receipt_relative = f"health/{bundle.bundle_version}/environment-v1.json"
    receipt_path = roots.private_root / receipt_relative
    _ensure_private_directories(roots.private_root, "health", bundle.bundle_version)
    if os.path.lexists(receipt_path):
        existing = read_regular_input(
            roots.private_root,
            receipt_relative,
            max_bytes=131_072,
        )
        if existing != content:
            raise ValueError("stale_environment_receipt")
    else:
        _write_new_private_file(receipt_path, content)

    return EnvironmentHealth(
        state="ready",
        check_count=CHECK_COUNT,
        artifact_count=reference_result.artifact_count,
        installed_count=len(installations),
        support_count=len(toolchain["supports"]),
        tool_count=len(toolchain["tools"]),
    )


def _verify_installations(private_root: Path, bundle: ReferenceBundle) -> list[dict[str, Any]]:
    installed_root = private_root / "references" / bundle.bundle_version / "installed"
    metadata = installed_root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError("stale_reference_installation")
    entries = {entry.name for entry in os.scandir(installed_root)}
    expected = {artifact.name for artifact in bundle.artifacts}
    if entries != expected:
        raise ValueError("stale_reference_installation")

    results = []
    for artifact in sorted(bundle.artifacts, key=lambda item: item.name):
        results.append(_verify_installation(private_root, bundle, artifact))
    return results


def _verify_installation(
    private_root: Path,
    bundle: ReferenceBundle,
    artifact: ReferenceArtifact,
) -> dict[str, Any]:
    target_relative = f"references/{bundle.bundle_version}/installed/{artifact.name}"
    target = private_root / target_relative
    metadata = target.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_mode & 0o222:
        raise ValueError("stale_reference_installation")

    receipt_relative = f"{target_relative}/.installation-receipt.json"
    receipt = _load_json_bytes(
        read_regular_input(private_root, receipt_relative, max_bytes=65_536),
        error="stale_reference_installation",
    )
    if not isinstance(receipt, dict) or set(receipt) != INSTALL_RECEIPT_FIELDS:
        raise ValueError("stale_reference_installation")
    if (
        receipt["schema_version"] != 1
        or receipt["artifact_name"] != artifact.name
        or receipt["bundle_version"] != bundle.bundle_version
        or receipt["state"] != "installed"
        or receipt["source_sha256"] != artifact.expected_sha256
        or not _nonnegative_integer(receipt["byte_count"])
        or not _nonnegative_integer(receipt["directory_count"])
        or not _nonnegative_integer(receipt["file_count"])
    ):
        raise ValueError("stale_reference_installation")

    file_count = 0
    directory_count = 0
    byte_count = 0
    tree = hashlib.sha256()
    for current, directory_names, file_names in os.walk(target, topdown=True, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current_path = Path(current)
        if current_path != target:
            current_metadata = current_path.lstat()
            if not stat.S_ISDIR(current_metadata.st_mode) or current_metadata.st_mode & 0o222:
                raise ValueError("stale_reference_installation")
            directory_count += 1
        for name in directory_names:
            child = current_path / name
            child_metadata = child.lstat()
            if (
                not stat.S_ISDIR(child_metadata.st_mode)
                or stat.S_ISLNK(child_metadata.st_mode)
                or child_metadata.st_mode & 0o222
            ):
                raise ValueError("stale_reference_installation")
        for name in file_names:
            if current_path == target and name == ".installation-receipt.json":
                continue
            child = current_path / name
            child_metadata = child.lstat()
            if (
                not stat.S_ISREG(child_metadata.st_mode)
                or stat.S_ISLNK(child_metadata.st_mode)
                or child_metadata.st_mode & 0o222
            ):
                raise ValueError("stale_reference_installation")
            relative = child.relative_to(private_root).as_posix()
            measured = hash_regular_input(
                private_root,
                relative,
                max_bytes=child_metadata.st_size,
            )
            local_name = child.relative_to(target).as_posix().encode("utf-8")
            tree.update(len(local_name).to_bytes(4, "big"))
            tree.update(local_name)
            tree.update(b"x" if child_metadata.st_mode & 0o111 else b"-")
            tree.update(measured.byte_count.to_bytes(8, "big"))
            tree.update(bytes.fromhex(measured.sha256))
            file_count += 1
            byte_count += measured.byte_count

    if (
        file_count != receipt["file_count"]
        or directory_count != receipt["directory_count"]
        or byte_count != receipt["byte_count"]
    ):
        raise ValueError("stale_reference_installation")
    return {
        "artifact_name": artifact.name,
        "byte_count": byte_count,
        "directory_count": directory_count,
        "file_count": file_count,
        "source_sha256": artifact.expected_sha256,
        "tree_sha256": tree.hexdigest(),
    }


def _verify_toolchain(
    private_root: Path,
    bundle: ReferenceBundle,
    architecture: str,
) -> dict[str, list[dict[str, Any]]]:
    receipt_relative = f"toolchain/{bundle.bundle_version}/toolchain-receipt.json"
    receipt = _load_json_bytes(
        read_regular_input(private_root, receipt_relative, max_bytes=131_072),
        error="stale_toolchain",
    )
    if not isinstance(receipt, dict) or set(receipt) != TOOLCHAIN_FIELDS:
        raise ValueError("stale_toolchain")
    tools = receipt["tools"]
    supports = receipt["supports"]
    if (
        receipt["schema_version"] != 2
        or receipt["bundle_version"] != bundle.bundle_version
        or receipt["architecture"] != architecture
        or not isinstance(tools, list)
        or len(tools) != len(TOOL_VERSIONS)
        or not isinstance(supports, list)
        or len(supports) != len(SUPPORT_VERSIONS)
    ):
        raise ValueError("stale_toolchain")

    results = []
    seen = set()
    for value in tools:
        if not isinstance(value, dict) or set(value) != TOOL_FIELDS:
            raise ValueError("stale_toolchain")
        name = value["name"]
        if name in seen or name not in TOOL_VERSIONS:
            raise ValueError("stale_toolchain")
        seen.add(name)
        expected_relative = TOOL_PATHS[name].format(bundle=bundle.bundle_version)
        if value["version"] != TOOL_VERSIONS[name] or value["relative_path"] != expected_relative:
            raise ValueError("stale_toolchain")
        validate_relative_path(value["relative_path"])
        if (
            not _nonnegative_integer(value["byte_count"])
            or value["byte_count"] <= 0
            or not _valid_sha256(value["sha256"])
        ):
            raise ValueError("stale_toolchain")
        tool_path = private_root / value["relative_path"]
        tool_metadata = tool_path.lstat()
        if (
            not stat.S_ISREG(tool_metadata.st_mode)
            or stat.S_ISLNK(tool_metadata.st_mode)
            or tool_metadata.st_mode & 0o222
        ):
            raise ValueError("stale_toolchain")
        measured = hash_regular_input(
            private_root,
            value["relative_path"],
            max_bytes=value["byte_count"],
        )
        if measured.byte_count != value["byte_count"] or measured.sha256 != value["sha256"]:
            raise ValueError("stale_toolchain")
        results.append(
            {
                "byte_count": measured.byte_count,
                "name": name,
                "sha256": measured.sha256,
                "version": value["version"],
            }
        )
    if seen != set(TOOL_VERSIONS):
        raise ValueError("stale_toolchain")

    support_results = []
    seen_supports = set()
    for value in supports:
        if not isinstance(value, dict) or set(value) != SUPPORT_FIELDS:
            raise ValueError("stale_toolchain")
        name = value["name"]
        if name in seen_supports or name not in SUPPORT_VERSIONS:
            raise ValueError("stale_toolchain")
        seen_supports.add(name)
        expected_relative = SUPPORT_PATHS[name].format(bundle=bundle.bundle_version)
        if value["version"] != SUPPORT_VERSIONS[name] or value["relative_path"] != expected_relative:
            raise ValueError("stale_toolchain")
        if (
            not _nonnegative_integer(value["byte_count"])
            or value["byte_count"] <= 0
            or not _nonnegative_integer(value["directory_count"])
            or not _nonnegative_integer(value["file_count"])
            or value["file_count"] <= 0
            or not _valid_sha256(value["tree_sha256"])
        ):
            raise ValueError("stale_toolchain")
        measured = _measure_immutable_tree(private_root, expected_relative)
        if any(
            measured[field] != value[field]
            for field in ("byte_count", "directory_count", "file_count", "tree_sha256")
        ):
            raise ValueError("stale_toolchain")
        support_results.append(
            {
                "byte_count": measured["byte_count"],
                "directory_count": measured["directory_count"],
                "file_count": measured["file_count"],
                "name": name,
                "tree_sha256": measured["tree_sha256"],
                "version": value["version"],
            }
        )
    if seen_supports != set(SUPPORT_VERSIONS):
        raise ValueError("stale_toolchain")
    return {
        "supports": sorted(support_results, key=lambda item: item["name"]),
        "tools": sorted(results, key=lambda item: item["name"]),
    }


def _measure_immutable_tree(private_root: Path, relative_path: str) -> dict[str, Any]:
    validate_relative_path(relative_path)
    target = private_root / relative_path
    metadata = target.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_mode & 0o222
    ):
        raise ValueError("stale_toolchain")
    file_count = 0
    directory_count = 0
    byte_count = 0
    tree = hashlib.sha256()
    for current, directory_names, file_names in os.walk(target, topdown=True, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if (
            not stat.S_ISDIR(current_metadata.st_mode)
            or stat.S_ISLNK(current_metadata.st_mode)
            or current_metadata.st_mode & 0o222
        ):
            raise ValueError("stale_toolchain")
        if current_path != target:
            local = current_path.relative_to(target).as_posix().encode("utf-8")
            tree.update(b"D")
            tree.update(len(local).to_bytes(4, "big"))
            tree.update(local)
            directory_count += 1
        for name in directory_names:
            child = current_path / name
            child_metadata = child.lstat()
            if (
                not stat.S_ISDIR(child_metadata.st_mode)
                or stat.S_ISLNK(child_metadata.st_mode)
                or child_metadata.st_mode & 0o222
            ):
                raise ValueError("stale_toolchain")
        for name in file_names:
            child = current_path / name
            child_metadata = child.lstat()
            if (
                not stat.S_ISREG(child_metadata.st_mode)
                or stat.S_ISLNK(child_metadata.st_mode)
                or child_metadata.st_mode & 0o222
            ):
                raise ValueError("stale_toolchain")
            measured = hash_regular_input(
                private_root,
                child.relative_to(private_root).as_posix(),
                max_bytes=max(child_metadata.st_size, 1),
            )
            local = child.relative_to(target).as_posix().encode("utf-8")
            tree.update(b"F")
            tree.update(len(local).to_bytes(4, "big"))
            tree.update(local)
            tree.update(b"x" if child_metadata.st_mode & 0o111 else b"-")
            tree.update(measured.byte_count.to_bytes(8, "big"))
            tree.update(bytes.fromhex(measured.sha256))
            file_count += 1
            byte_count += measured.byte_count
    return {
        "byte_count": byte_count,
        "directory_count": directory_count,
        "file_count": file_count,
        "tree_sha256": tree.hexdigest(),
    }


def _probe_macos_environment(private_root: Path) -> SystemState:
    resolved = Path(private_root).resolve(strict=True)
    mount = resolved
    while mount != mount.parent and not os.path.ismount(mount):
        mount = mount.parent
    encrypted = False
    if platform.system() == "Darwin":
        try:
            completed = subprocess.run(
                ["/usr/bin/hdiutil", "info", "-plist"],
                check=True,
                capture_output=True,
                timeout=30,
                env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            )
            info = plistlib.loads(completed.stdout)
            matches = [
                image
                for image in info.get("images", [])
                if any(
                    entity.get("mount-point") == str(mount)
                    for entity in image.get("system-entities", [])
                )
            ]
            encrypted = len(matches) == 1 and matches[0].get("image-encrypted") is True
        except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, ValueError):
            encrypted = False
    filesystem = os.statvfs(resolved)
    free_bytes = filesystem.f_bavail * filesystem.f_frsize
    try:
        memory = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            timeout=10,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        )
        memory_bytes = int(memory.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        memory_bytes = 0
    proxy_clear = not any(
        os.environ.get(name)
        for name in (
            "ALL_PROXY",
            "HTTPS_PROXY",
            "HTTP_PROXY",
            "all_proxy",
            "https_proxy",
            "http_proxy",
        )
    )
    return SystemState(
        architecture=platform.machine(),
        encrypted_mount=encrypted,
        free_bytes=free_bytes,
        memory_bytes=memory_bytes,
        network_blocked=not _can_connect("www.python.org", 443),
        download_transport_closed=not _can_connect("127.0.0.1", 18181),
        proxy_environment_clear=proxy_clear,
    )


def _can_connect(host: str, port: int) -> bool:
    try:
        connection = socket.create_connection((host, port), timeout=3)
    except OSError:
        return False
    connection.close()
    return True


def _ensure_private_directories(root: Path, *parts: str) -> Path:
    current = Path(root)
    for part in parts:
        validate_relative_path(part)
        candidate = current / part
        try:
            candidate.mkdir(mode=0o700)
        except FileExistsError:
            metadata = candidate.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                raise ValueError("invalid_health_directory") from None
        current = candidate
    return current


def _write_new_private_file(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        raise ValueError("health_receipt_write_failed") from None
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)


def _load_json_bytes(content: bytes, *, error: str) -> Any:
    try:
        return json.loads(content, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise ValueError(error) from None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError(key)
        value[key] = item
    return value


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
