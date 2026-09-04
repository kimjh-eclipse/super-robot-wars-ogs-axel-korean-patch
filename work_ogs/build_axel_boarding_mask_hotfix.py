# -*- coding: utf-8 -*-
"""Restore allied boarding masks for the role-swapped Axel Plot records."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
MANIFEST = ROOT / "runtime" / "axel_boarding_mask_manifest.json"
EXPECTED_SHA256 = "A2D12C98637B3A0342AF5432C4967AC3E1C5A09042A1525F39A8543147B2FBD1"

ARCHIVES = {"SHARED": 0x5DA000, "IM": 0x83F000}
PLOT_DATA = 0x13B490
PLOT_STRIDE = 0x94
MASK_OFF = 0x12
AXEL_PLOTS = (53, 54)
OLD_MASK = 0x0000
NEW_MASK = 0x0201


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> None:
    before = digest(ISO)
    if before != EXPECTED_SHA256:
        raise SystemExit(f"CURRENT ISO guard failed: {before}")

    changes = []
    with ISO.open("r+b") as f:
        for archive, base in ARCHIVES.items():
            for plot in AXEL_PLOTS:
                off = base + PLOT_DATA + plot * PLOT_STRIDE + MASK_OFF
                f.seek(off)
                old = f.read(2)
                if old != struct.pack("<H", OLD_MASK):
                    raise SystemExit(
                        f"{archive} Plot[{plot}] +0x12 guard failed: {old.hex()}"
                    )
                f.seek(off)
                f.write(struct.pack("<H", NEW_MASK))
                changes.append({
                    "archive": archive,
                    "plot": plot,
                    "offset": f"0x{off:X}",
                    "before": f"0x{OLD_MASK:04X}",
                    "after": f"0x{NEW_MASK:04X}",
                })

    after = digest(ISO)
    MANIFEST.write_text(json.dumps({
        "kind": "axel-role-swap-boarding-mask",
        "sha256_before": before,
        "sha256_after": after,
        "reason": "pilot master attr 0x21 dispatches to Plot +0x12; allied raw keys resolve to Plot 53",
        "changes": changes,
        "untouched": "Plot +0x1E/+0x20/+0x22, dialogue, battle voices",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(changes, ensure_ascii=False, indent=2))
    print(after)


if __name__ == "__main__":
    main()
