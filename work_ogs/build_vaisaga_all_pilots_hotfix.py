# -*- coding: utf-8 -*-
"""Allow every pilot category to board the allied Vaisaga."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
MANIFEST = ROOT / "runtime" / "vaisaga_all_pilots_manifest.json"
EXPECTED_INPUT_SHA256 = "B83F2AC2BBC86BCC8E749E6BC99901192673E1431EE0DA8B008F9CD1F2A0A4DB"
ARCHIVES = {"SHARED": 0x5DA000, "IM": 0x83F000}
UNIT_DATA = 0x11F8A4
UNIT_STRIDE = 0x64
SLOT = 0x4E


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    before = sha256(ISO)
    if before != EXPECTED_INPUT_SHA256:
        raise SystemExit(f"unexpected input ISO SHA256: {before}")
    changes = []
    with ISO.open("rb") as source:
        for archive, base in ARCHIVES.items():
            record = base + UNIT_DATA + SLOT * UNIT_STRIDE
            source.seek(record)
            unit = source.read(UNIT_STRIDE)
            raw = struct.unpack_from("<H", unit, 0x10)[0]
            uid = struct.unpack_from("<H", unit, 0x46)[0]
            current = struct.unpack_from("<H", unit, 0x22)[0]
            if (raw, uid, current) != (0x42, 0x30, 0x0200):
                raise SystemExit(
                    f"{archive} guard failed: raw=0x{raw:X} uid=0x{uid:X} compat=0x{current:X}")
            changes.append((archive, record + 0x22, unit[0x22:0x24], b"\xff\xff"))
    with ISO.open("r+b") as target:
        for archive, offset, old, new in changes:
            target.seek(offset)
            if target.read(2) != old:
                raise SystemExit(f"write guard failed: {archive} 0x{offset:X}")
        for _, offset, _, new in changes:
            target.seek(offset)
            target.write(new)
    after = sha256(ISO)
    report = {
        "kind": "vaisaga-all-pilots-hotfix",
        "target": str(ISO),
        "before_sha256": before,
        "after_sha256": after,
        "changed_byte_count": 4,
        "changes": [
            {"archive": a, "offset": f"0x{o:X}", "old_hex": x.hex(), "new_hex": n.hex()}
            for a, o, x, n in changes
        ],
        "guards": {"unit_slot": "0x4E", "raw_id": "0x42", "uid": "0x30"},
    }
    MANIFEST.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
