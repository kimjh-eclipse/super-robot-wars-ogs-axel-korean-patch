# -*- coding: utf-8 -*-
"""Build the v20260831 -> v20260904 quick-patcher upgrade pack."""
from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

from build_range_pack import find_ranges


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "runtime" / "SRWOGS_v20260831_SOURCE.iso"
TARGET = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
OUTPUT = HERE / "OGS_ISO_ranges_upgrade.bin"
SOURCE_SHA256 = "08615F303D301AC9935A7C71379D8AE4BD5B2F9E0C2B328397D103FD0352B930"
TARGET_SHA256 = "831A646BCDE363B92A1E8CD2C5CACE786102A61833A5757BB155B527CF35B9CC"
MAGIC = b"OGSAXLRNG"
VERSION = 1
TITLE = "슈퍼로봇대전 OGs 액셀 역할 교체 패치 (v20260831→v20260904 업그레이드)"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb", buffering=0) as source:
        for chunk in iter(lambda: source.read(16 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> None:
    source_hash = digest(SOURCE)
    target_hash = digest(TARGET)
    if source_hash != SOURCE_SHA256:
        raise SystemExit(f"v20260831 source guard failed: {source_hash}")
    if target_hash != TARGET_SHA256:
        raise SystemExit(f"CURRENT target guard failed: {target_hash}")
    if SOURCE.stat().st_size != TARGET.stat().st_size:
        raise SystemExit("ISO size mismatch")

    ranges = find_ranges(SOURCE, TARGET)
    title = TITLE.encode("utf-8")
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    with temporary.open("wb") as out, TARGET.open("rb", buffering=0) as target:
        out.write(MAGIC)
        out.write(struct.pack("<I", VERSION))
        out.write(struct.pack("<H", len(title)))
        out.write(title)
        out.write(struct.pack("<Q", TARGET.stat().st_size))
        out.write(bytes.fromhex(source_hash))
        out.write(bytes.fromhex(target_hash))
        out.write(struct.pack("<I", len(ranges)))
        for offset, length in ranges:
            target.seek(offset)
            data = target.read(length)
            if len(data) != length:
                raise IOError(f"short read at {offset:#x}")
            out.write(struct.pack("<QI", offset, length))
            out.write(data)
        out.flush()
        os.fsync(out.fileno())
    temporary.replace(OUTPUT)
    payload = sum(length for _, length in ranges)
    print(f"ranges={len(ranges)} payload={payload} size={OUTPUT.stat().st_size}")
    print(f"sha256={digest(OUTPUT)}")


if __name__ == "__main__":
    main()
