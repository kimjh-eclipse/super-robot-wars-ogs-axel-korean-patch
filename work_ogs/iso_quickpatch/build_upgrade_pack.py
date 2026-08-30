"""stage35 핫픽스 매니페스트에서 업그레이드 구간 팩 생성.

v20260830 적용본(53B780A2…)을 이미 갖고 있는 사용자가 기준 ISO 를 다시
준비하지 않고 핫픽스본(08615F30…)으로 올릴 수 있도록, 매니페스트에 기록된
변경 구간(old/new 바이트)만으로 OGS_ISO_ranges_upgrade.bin 을 만든다.
팩 포맷은 build_range_pack.py 와 동일("OGSAXLRNG").
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

MAGIC = b"OGSAXLRNG"
VERSION = 1

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = ROOT / "runtime" / "stage35_vysaga_hotfix_manifest.json"
OUTPUT = HERE / "OGS_ISO_ranges_upgrade.bin"
TITLE = "슈퍼로봇대전 OGs 액셀 역할 교체 패치 (v20260830→핫픽스 업그레이드)"


def main() -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    src_hash = m["before_sha256"].upper()
    dst_hash = m["after_sha256"].upper()
    iso_size = int(m["iso_size"])

    ranges = []
    for ch in m["changes"]:
        if ch["kind"] == "ptbl":
            off = int(ch["absolute_offset"], 16)
            new = bytes.fromhex(ch["new_hex"])
            old = bytes.fromhex(ch["old_hex"])
        else:  # scenario_text
            off = int(ch["absolute_offset"], 16)
            new = bytes.fromhex(ch["new_hex"])
            old = bytes.fromhex(ch["old_hex"])
        if len(new) != len(old):
            raise ValueError(f"old/new 길이 불일치 @0x{off:X}")
        ranges.append((off, new))
    ranges.sort()

    payload = sum(len(d) for _, d in ranges)
    title = TITLE.encode("utf-8")
    with OUTPUT.open("wb") as out:
        out.write(MAGIC)
        out.write(struct.pack("<I", VERSION))
        out.write(struct.pack("<H", len(title)))
        out.write(title)
        out.write(struct.pack("<Q", iso_size))
        out.write(bytes.fromhex(src_hash))
        out.write(bytes.fromhex(dst_hash))
        out.write(struct.pack("<I", len(ranges)))
        for off, data in ranges:
            out.write(struct.pack("<QI", off, len(data)))
            out.write(data)

    print(f"src {src_hash}")
    print(f"dst {dst_hash}")
    print(f"구간 {len(ranges)}개 / 페이로드 {payload}B")
    print(f"생성: {OUTPUT.name}  {OUTPUT.stat().st_size:,}B")


if __name__ == "__main__":
    main()
