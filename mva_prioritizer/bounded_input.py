"""Read a small input file through a descriptor that is checked before it is read.

The regular-file decision is made on the open descriptor, so a path swapped for
a symlink, FIFO, or directory between check and open is still rejected. The
size limit is enforced on the descriptor's fstat and again on the bytes read.
Duplicate JSON object keys are rejected instead of resolved last-wins.
"""
from __future__ import annotations

import errno
import json
import os
import stat
from pathlib import Path


class InputRejected(ValueError):
    """The input is not a regular file within limits, or is not strict JSON."""


def read_regular_file(path: Path, max_bytes: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise InputRejected("input must be a regular file") from None
        raise
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise InputRejected("input must be a regular file")
        if status.st_size > max_bytes:
            raise InputRejected("input exceeds size limit")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            raw = handle.read(max_bytes + 1)
    finally:
        if descriptor != -1:
            os.close(descriptor)
    if len(raw) > max_bytes:
        raise InputRejected("input exceeds size limit")
    return raw


def _reject_duplicate_keys(pairs: list) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise InputRejected("duplicate object key")
        result[key] = value
    return result


def load_strict_json(path: Path, max_bytes: int) -> object:
    raw = read_regular_file(path, max_bytes)
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, RecursionError, ValueError) as exc:
        raise InputRejected("input is not strict JSON") from exc
