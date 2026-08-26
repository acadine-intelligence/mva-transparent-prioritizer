from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.source_scan import scan_public_source_tree


def main() -> int:
    try:
        result = scan_public_source_tree(ROOT)
    except Exception:
        print('{"error":"privacy_blocked","state":"failed_closed"}', file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "byte_count": result.byte_count,
                "external_actions": result.external_actions,
                "file_count": result.file_count,
                "state": result.state,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
