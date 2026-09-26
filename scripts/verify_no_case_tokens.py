"""Case-derived token gate for the public tree.

The regex gate in mva_prioritizer.source_scan catches coordinates, genotypes,
HPO terms, proband ids, secrets and machine paths. It cannot know which gene
symbols came out of the private prioritization run, because that list is
itself private. This gate closes that gap: a denylist of tokens is built
locally from the private artifacts (runtime/privacy/denied-tokens.txt, which
is gitignored and never leaves the host), and every tracked or unignored file
is refused if it contains one of them as a whole word.

The review of commit 1783250 found eleven case-derived gene symbols in a
tracked Jev request file, copied from an ignored aggregate report. Every scan
in place at the time passed. This gate would have failed closed.

Usage: python3 scripts/verify_no_case_tokens.py [--denylist PATH]
Exit 0 clear, 2 blocked or the denylist is missing. A missing denylist is a
failure on purpose: the gate must not silently pass on a host that never
built the list.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DENYLIST = ROOT / "runtime" / "privacy" / "denied-tokens.txt"


def load_denylist(path: Path) -> list[str]:
    tokens = [t.strip() for t in path.read_text(encoding="utf-8").splitlines()]
    return sorted({t for t in tokens if t and not t.startswith("#")})


def tracked_and_unignored(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, check=True, capture_output=True,
    ).stdout
    return sorted(p.decode("utf-8") for p in out.split(b"\0") if p)


def history_blobs(root: Path) -> list[tuple[str, str]]:
    """Every (blob sha, path) reachable from any ref, deduplicated by sha."""
    listing = subprocess.run(
        ["git", "rev-list", "--all", "--objects"], cwd=root, check=True, capture_output=True,
    ).stdout.decode("utf-8", "replace").splitlines()
    candidates = [line.split(None, 1) for line in listing]
    candidates = [(sha, path) for sha, *rest in candidates for path in rest[:1]]
    types = subprocess.run(
        ["git", "cat-file", "--batch-check"], cwd=root, check=True,
        input="\n".join(sha for sha, _ in candidates).encode(), capture_output=True,
    ).stdout.decode().splitlines()
    is_blob = {line.split()[0] for line in types if len(line.split()) >= 2 and line.split()[1] == "blob"}
    seen: set[str] = set()
    out = []
    for sha, path in candidates:
        if sha in is_blob and sha not in seen:
            seen.add(sha)
            out.append((sha, path))
    return out


def blob_bytes(root: Path, sha: str) -> bytes:
    return subprocess.run(["git", "cat-file", "-p", sha], cwd=root, check=True, capture_output=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--denylist", type=Path, default=DEFAULT_DENYLIST)
    ap.add_argument("--root", type=Path, default=ROOT, help="tree to scan (default: this checkout)")
    ap.add_argument("--history", action="store_true",
                    help="scan every blob reachable from any ref instead of the working tree; "
                         "run this before the repository is made public")
    args = ap.parse_args()
    root = args.root.resolve()
    if not args.denylist.is_file():
        print('{"state":"failed_closed","error":"denylist_missing"}', file=sys.stderr)
        return 2
    tokens = load_denylist(args.denylist)
    if not tokens:
        print('{"state":"failed_closed","error":"denylist_empty"}', file=sys.stderr)
        return 2
    rx = re.compile(rb"(?<![A-Za-z0-9_])(?:" + b"|".join(re.escape(t.encode()) for t in tokens) + rb")(?![A-Za-z0-9_])")
    hits = 0
    if args.history:
        blobs = history_blobs(root)
        for sha, path in blobs:
            if rx.search(blob_bytes(root, sha)):
                hits += 1
                # Report the blob and path, never the token.
                print(f"blocked: {sha[:12]} {path}", file=sys.stderr)
        if hits:
            print('{"state":"failed_closed","error":"case_token_in_history","blobs":%d,"scanned":%d}' % (hits, len(blobs)), file=sys.stderr)
            return 2
        print('{"state":"clear","scope":"history","blobs":%d,"denied_tokens":%d}' % (len(blobs), len(tokens)))
        return 0
    for rel in tracked_and_unignored(root):
        p = root / rel
        if not p.is_file():
            continue
        if rx.search(p.read_bytes()):
            hits += 1
            # Report the file, never the token.
            print(f"blocked: {rel}", file=sys.stderr)
    if hits:
        print('{"state":"failed_closed","error":"case_token_present","files":%d}' % hits, file=sys.stderr)
        return 2
    print('{"state":"clear","denied_tokens":%d}' % len(tokens))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
