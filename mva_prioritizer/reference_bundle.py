from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from .paths import PathSecurityError, hash_regular_input, validate_directory_root


SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
MD5_PATTERN = re.compile(r"[0-9a-f]{32}")
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._+-]{0,63}")
FILENAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,254}")
BUNDLE_VERSION_PATTERN = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\.[1-9][0-9]*")
ALLOWED_SOURCE_HOSTS = {
    "cpan.metacpan.org",
    "ftp.ensembl.org",
    "ftp.ncbi.nlm.nih.gov",
    "g-879a9f.f5dc97.75bc.dn.glob.us",
    "github.com",
    "www.python.org",
}
ALLOWED_REDIRECT_HOSTS = ALLOWED_SOURCE_HOSTS | {
    "codeload.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
TOP_FIELDS = {
    "artifacts",
    "assembly",
    "bundle_version",
    "fastq_included",
    "network_during_private_run",
    "private_runtime",
    "protected_data_allowed_on_public_compute",
    "schema_version",
    "status",
}
ARTIFACT_FIELDS = {
    "expected_bytes",
    "expected_sha256",
    "filename",
    "install_kind",
    "name",
    "role",
    "source_checksum",
    "source_url",
    "version",
}
SOURCE_CHECKSUM_FIELDS = {"algorithm", "value"}
ALLOWED_ROLES = {"index", "reference_data", "runtime_archive", "tool_source"}
ALLOWED_INSTALL_KINDS = {
    "archive",
    "data-zip",
    "reference-gzip",
    "source-tar",
    "tabix-index",
    "vcf-gzip",
}
ALLOWED_STATUSES = {"acquiring", "declared", "verified"}


class _DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceArtifact:
    name: str
    role: str
    version: str
    source_url: str
    filename: str
    expected_bytes: int
    expected_sha256: Optional[str]
    source_checksum_algorithm: str
    source_checksum_value: Optional[str]
    install_kind: str


@dataclass(frozen=True)
class ReferenceBundle:
    bundle_version: str
    assembly: str
    status: str
    artifacts: tuple[ReferenceArtifact, ...]

    @property
    def pinned_count(self) -> int:
        return sum(artifact.expected_sha256 is not None for artifact in self.artifacts)

    @property
    def bootstrap_count(self) -> int:
        return len(self.artifacts) - self.pinned_count


@dataclass(frozen=True)
class ReferenceBundleVerification:
    state: str
    artifact_count: int
    byte_count: int


@dataclass(frozen=True)
class ReferenceAcquisition:
    state: str
    verified_count: int
    pin_required_count: int
    byte_count: int
    measured_sha256: str


ReferenceFetcher = Callable[[str, Path, int], None]


def load_reference_bundle(path: Path) -> ReferenceBundle:
    candidate = Path(path)
    metadata = candidate.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1_048_576:
        raise ValueError("invalid_reference_bundle")
    try:
        value = json.loads(candidate.read_bytes(), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise ValueError("invalid_reference_bundle") from None
    if not isinstance(value, dict) or set(value) != TOP_FIELDS:
        raise ValueError("invalid_reference_bundle")
    if (
        value["schema_version"] != 2
        or value["assembly"] != "GRCh38"
        or value["status"] not in ALLOWED_STATUSES
        or not isinstance(value["bundle_version"], str)
        or BUNDLE_VERSION_PATTERN.fullmatch(value["bundle_version"]) is None
        or value["private_runtime"] != "m1-encrypted-workspace"
        or value["network_during_private_run"] is not False
        or value["protected_data_allowed_on_public_compute"] is not False
        or value["fastq_included"] is not False
        or not isinstance(value["artifacts"], list)
        or not value["artifacts"]
    ):
        raise ValueError("invalid_reference_bundle")

    artifacts: list[ReferenceArtifact] = []
    names: set[str] = set()
    filenames: set[str] = set()
    for item in value["artifacts"]:
        artifact = _parse_artifact(item)
        if artifact.name in names or artifact.filename in filenames:
            raise ValueError("invalid_reference_bundle")
        names.add(artifact.name)
        filenames.add(artifact.filename)
        artifacts.append(artifact)
    if value["status"] == "verified" and any(
        artifact.expected_sha256 is None for artifact in artifacts
    ):
        raise ValueError("invalid_reference_bundle")
    return ReferenceBundle(
        bundle_version=value["bundle_version"],
        assembly=value["assembly"],
        status=value["status"],
        artifacts=tuple(artifacts),
    )


def verify_reference_bundle(
    private_root: Path,
    bundle: ReferenceBundle,
) -> ReferenceBundleVerification:
    private = validate_directory_root(Path(private_root))
    if bundle.bootstrap_count:
        raise ValueError("unresolved_reference_digest")
    byte_count = 0
    for artifact in bundle.artifacts:
        relative_path = (
            f"references/{bundle.bundle_version}/downloads/verified/{artifact.filename}"
        )
        try:
            measured = hash_regular_input(
                private,
                relative_path,
                max_bytes=artifact.expected_bytes,
            )
        except PathSecurityError as exc:
            if str(exc) in {"input_unavailable", "path_changed", "size_limit"}:
                raise ValueError("stale_reference_bundle") from None
            raise
        if (
            measured.byte_count != artifact.expected_bytes
            or measured.sha256 != artifact.expected_sha256
        ):
            raise ValueError("stale_reference_bundle")
        byte_count += measured.byte_count
    return ReferenceBundleVerification(
        state="verified",
        artifact_count=len(bundle.artifacts),
        byte_count=byte_count,
    )


def acquire_reference_artifact(
    private_root: Path,
    bundle: ReferenceBundle,
    artifact_name: str,
    *,
    fetcher: Optional[ReferenceFetcher] = None,
) -> ReferenceAcquisition:
    private = validate_directory_root(Path(private_root))
    artifact = next(
        (candidate for candidate in bundle.artifacts if candidate.name == artifact_name),
        None,
    )
    if artifact is None:
        raise ValueError("unknown_reference_artifact")
    bundle_root = _ensure_private_directories(
        private,
        "references",
        bundle.bundle_version,
    )
    downloads = _ensure_private_directories(bundle_root, "downloads")
    quarantine = _ensure_private_directories(downloads, "quarantine")
    verified_directory = _ensure_private_directories(downloads, "verified")
    receipts = _ensure_private_directories(bundle_root, "receipts")
    candidate_path = quarantine / f"{artifact.filename}.part"
    verified_path = verified_directory / artifact.filename

    if verified_path.exists():
        relative = verified_path.relative_to(private).as_posix()
        measured = hash_regular_input(
            private,
            relative,
            max_bytes=artifact.expected_bytes,
        )
        if (
            artifact.expected_sha256 is None
            or measured.byte_count != artifact.expected_bytes
            or measured.sha256 != artifact.expected_sha256
        ):
            raise ValueError("stale_reference_bundle")
        return ReferenceAcquisition(
            state="verified",
            verified_count=1,
            pin_required_count=0,
            byte_count=measured.byte_count,
            measured_sha256=measured.sha256,
        )

    start_byte = 0
    if candidate_path.exists():
        metadata = candidate_path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("unsafe_download_candidate")
        start_byte = metadata.st_size
        if start_byte > artifact.expected_bytes:
            raise ValueError("stale_reference_bundle")
    if start_byte < artifact.expected_bytes:
        if fetcher is None:
            _download_https(
                artifact.source_url,
                candidate_path,
                start_byte,
                artifact.expected_bytes,
            )
        else:
            fetcher(artifact.source_url, candidate_path, start_byte)
    _freeze_download_candidate(candidate_path)
    relative_candidate = candidate_path.relative_to(private).as_posix()
    measured = hash_regular_input(
        private,
        relative_candidate,
        max_bytes=artifact.expected_bytes,
    )
    if measured.byte_count != artifact.expected_bytes:
        raise ValueError("incomplete_reference_download")
    if (
        artifact.source_checksum_algorithm == "md5"
        and measured.md5 != artifact.source_checksum_value
    ):
        raise ValueError("source_checksum_mismatch")

    if artifact.expected_sha256 is None:
        state = "pin_required"
        verified_count = 0
        pin_required_count = 1
    elif measured.sha256 != artifact.expected_sha256:
        raise ValueError("reference_digest_mismatch")
    else:
        os.replace(candidate_path, verified_path)
        state = "verified"
        verified_count = 1
        pin_required_count = 0

    receipt = {
        "artifact_name": artifact.name,
        "bundle_version": bundle.bundle_version,
        "byte_count": measured.byte_count,
        "filename": artifact.filename,
        "measured_sha256": measured.sha256,
        "schema_version": 1,
        "state": state,
    }
    receipt_path = receipts / f"{artifact.name}.json"
    temporary_receipt = receipts / f".{artifact.name}.json.tmp"
    _write_acquisition_receipt(
        receipts,
        temporary_receipt.name,
        receipt_path.name,
        (
            json.dumps(receipt, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        ).encode("utf-8"),
    )
    return ReferenceAcquisition(
        state=state,
        verified_count=verified_count,
        pin_required_count=pin_required_count,
        byte_count=measured.byte_count,
        measured_sha256=measured.sha256,
    )


def _write_acquisition_receipt(
    directory: Path,
    temporary_name: str,
    receipt_name: str,
    content: bytes,
) -> None:
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_descriptor = os.open(directory, directory_flags)
    except OSError:
        raise ValueError("unsafe_reference_receipt") from None
    receipt_descriptor: Optional[int] = None
    created = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        receipt_descriptor = os.open(
            temporary_name,
            flags,
            0o600,
            dir_fd=directory_descriptor,
        )
        created = True
        view = memoryview(content)
        while view:
            written = os.write(receipt_descriptor, view)
            view = view[written:]
        os.fchmod(receipt_descriptor, 0o400)
        os.fsync(receipt_descriptor)
        os.replace(
            temporary_name,
            receipt_name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        created = False
        os.fsync(directory_descriptor)
    except OSError:
        raise ValueError("unsafe_reference_receipt") from None
    finally:
        if receipt_descriptor is not None:
            os.close(receipt_descriptor)
        if created:
            try:
                os.unlink(temporary_name, dir_fd=directory_descriptor)
            except OSError:
                pass
        os.close(directory_descriptor)


def _freeze_download_candidate(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ValueError("unsafe_download_candidate") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("unsafe_download_candidate")
        os.fchmod(descriptor, 0o400)
        os.fsync(descriptor)
    except OSError:
        raise ValueError("unsafe_download_candidate") from None
    finally:
        os.close(descriptor)


def _ensure_private_directories(root: Path, *parts: str) -> Path:
    current = Path(root)
    for part in parts:
        if not _valid_token(part):
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


def _download_https(
    source_url: str,
    destination: Path,
    start_byte: int,
    expected_bytes: int,
) -> None:
    headers = {
        "Accept-Encoding": "identity",
        "User-Agent": "mva-transparent-prioritizer/1",
    }
    if start_byte:
        headers["Range"] = f"bytes={start_byte}-"
    request = Request(source_url, headers=headers, method="GET")
    with urlopen(request, timeout=120) as response:
        status = getattr(response, "status", None)
        if (start_byte == 0 and status != 200) or (start_byte > 0 and status != 206):
            raise ValueError("reference_download_protocol_error")
        final_url = response.geturl()
        parsed_final = urlsplit(final_url)
        if parsed_final.scheme != "https" or parsed_final.hostname not in ALLOWED_REDIRECT_HOSTS:
            raise ValueError("reference_download_redirect_rejected")
        content_encoding = response.headers.get("Content-Encoding")
        if content_encoding not in {None, "identity"}:
            raise ValueError("reference_download_protocol_error")
        remaining = expected_bytes - start_byte
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                raise ValueError("reference_download_protocol_error") from None
            if declared_length != remaining:
                raise ValueError("reference_download_protocol_error")
        if start_byte:
            content_range = response.headers.get("Content-Range")
            if content_range is None or not content_range.startswith(
                f"bytes {start_byte}-"
            ):
                raise ValueError("reference_download_protocol_error")

        flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        if start_byte:
            flags |= os.O_APPEND
        else:
            flags |= os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(destination, flags, 0o600)
        except OSError:
            raise ValueError("unsafe_download_candidate") from None
        downloaded = start_byte
        try:
            while True:
                chunk = response.read(4_194_304)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > expected_bytes:
                    raise ValueError("reference_download_protocol_error")
                view = memoryview(chunk)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    if downloaded != expected_bytes:
        raise ValueError("incomplete_reference_download")


def _parse_artifact(value: Any) -> ReferenceArtifact:
    if not isinstance(value, dict) or set(value) != ARTIFACT_FIELDS:
        raise ValueError("invalid_reference_bundle")
    checksum = value["source_checksum"]
    if not isinstance(checksum, dict) or set(checksum) != SOURCE_CHECKSUM_FIELDS:
        raise ValueError("invalid_reference_bundle")
    expected_sha256 = value["expected_sha256"]
    if expected_sha256 is not None and not _valid_sha256(expected_sha256):
        raise ValueError("invalid_reference_bundle")
    algorithm = checksum["algorithm"]
    checksum_value = checksum["value"]
    if not _valid_source_checksum(algorithm, checksum_value):
        raise ValueError("invalid_reference_bundle")
    if algorithm == "sha256" and checksum_value != expected_sha256:
        raise ValueError("invalid_reference_bundle")
    if (
        not _valid_token(value["name"])
        or value["role"] not in ALLOWED_ROLES
        or not _valid_version(value["version"])
        or not _valid_source_url(value["source_url"], value["filename"])
        or not isinstance(value["filename"], str)
        or FILENAME_PATTERN.fullmatch(value["filename"]) is None
        or not _is_integer(value["expected_bytes"])
        or value["expected_bytes"] <= 0
        or value["install_kind"] not in ALLOWED_INSTALL_KINDS
    ):
        raise ValueError("invalid_reference_bundle")
    return ReferenceArtifact(
        name=value["name"],
        role=value["role"],
        version=value["version"],
        source_url=value["source_url"],
        filename=value["filename"],
        expected_bytes=value["expected_bytes"],
        expected_sha256=expected_sha256,
        source_checksum_algorithm=algorithm,
        source_checksum_value=checksum_value,
        install_kind=value["install_kind"],
    )


def _valid_source_url(value: Any, filename: Any) -> bool:
    if not isinstance(value, str) or not isinstance(filename, str):
        return False
    parsed = urlsplit(value)
    decoded_path = unquote(parsed.path)
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_SOURCE_HOSTS
        and parsed.username is None
        and parsed.password is None
        and parsed.query == ""
        and parsed.fragment == ""
        and parsed.path.endswith("/" + filename)
        and "/latest/" not in decoded_path.lower()
        and not decoded_path.lower().endswith("/latest")
        and ".." not in decoded_path.split("/")
    )


def _valid_source_checksum(algorithm: Any, value: Any) -> bool:
    if algorithm == "none":
        return value is None
    if algorithm == "sha256":
        return _valid_sha256(value)
    if algorithm == "md5":
        return isinstance(value, str) and MD5_PATTERN.fullmatch(value) is not None
    return False


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _valid_token(value: Any) -> bool:
    return isinstance(value, str) and TOKEN_PATTERN.fullmatch(value) is not None


def _valid_version(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value.encode("utf-8")) <= 128
        and all(32 <= ord(character) <= 126 for character in value)
    )


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result
