"""슈퍼로봇대전 OGs 액셀 역할 교체 — 제자리 ISO 구간 패치 리소스 생성.

D2DHD_kr/iso_quickpatch/build_range_pack.py 와 같은 방식.
기준 ISO(srwogs-v1.4.3s1)와 CURRENT ISO 크기가 완전히 동일하므로
(4,518,150,144B) 절대 오프셋 구간만 담으면 된다.

MERGE_GAP 이내로 떨어진 변경은 하나로 합쳐 런타임 복사 횟수를 줄인다.
"""
from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

import numpy as np

MAGIC = b"OGSAXLRNG"
VERSION = 1
MERGE_GAP = 64
CHUNK = 16 * 1024 * 1024

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "OGS_ISO_ranges.bin"

SOURCE = ROOT / "baseline" / "srwogs-v1.4.3s1.iso"
TARGET = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
TITLE = "슈퍼로봇대전 OGs 액셀 역할 교체 패치"


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb", buffering=0) as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest().upper()


def find_ranges(source: Path, target: Path):
    if source.stat().st_size != target.stat().st_size:
        raise ValueError(f"크기 불일치: {source.stat().st_size} / {target.stat().st_size}")
    size = source.stat().st_size
    parts = []
    off = 0
    with source.open("rb", buffering=0) as a, target.open("rb", buffering=0) as b:
        while off < size:
            old = a.read(min(CHUNK, size - off))
            new = b.read(len(old))
            d = np.flatnonzero(
                np.frombuffer(old, dtype=np.uint8) != np.frombuffer(new, dtype=np.uint8)
            )
            if d.size:
                parts.append(d.astype(np.int64) + off)
            off += len(old)
    if not parts:
        return []
    pos = np.concatenate(parts)
    cuts = np.flatnonzero(np.diff(pos) > MERGE_GAP + 1)
    starts = np.r_[0, cuts + 1]
    ends = np.r_[cuts, len(pos) - 1]
    return [(int(pos[s]), int(pos[e] - pos[s] + 1)) for s, e in zip(starts, ends)]


def main() -> None:
    src_hash = file_hash(SOURCE)
    dst_hash = file_hash(TARGET)
    print(f"기준본 {SOURCE.name}\n      {SOURCE.stat().st_size:,}B  {src_hash}")
    print(f"패치본 {TARGET.name}\n      {TARGET.stat().st_size:,}B  {dst_hash}")

    expected_src = "9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C"
    expected_dst = "53B780A2FFE3DD1BFE8FA5106E879F9BCF4585578AD94D5105FA65A0C39267D9"
    if src_hash != expected_src:
        raise ValueError("기준 ISO 해시가 핸드오프 문서와 다릅니다")
    if dst_hash != expected_dst:
        raise ValueError("CURRENT ISO 해시가 핸드오프 문서와 다릅니다")

    ranges = find_ranges(SOURCE, TARGET)
    payload = sum(n for _, n in ranges)
    print(f"\n변경 구간 {len(ranges):,}개 / 페이로드 {payload:,}B "
          f"({100*payload/SOURCE.stat().st_size:.2f}%)")

    tmp = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    title = TITLE.encode("utf-8")
    with tmp.open("wb", buffering=1 << 20) as out:
        out.write(MAGIC)
        out.write(struct.pack("<I", VERSION))
        out.write(struct.pack("<H", len(title)))
        out.write(title)
        out.write(struct.pack("<Q", SOURCE.stat().st_size))
        out.write(bytes.fromhex(src_hash))
        out.write(bytes.fromhex(dst_hash))
        out.write(struct.pack("<I", len(ranges)))
        with TARGET.open("rb", buffering=0) as t:
            for off, n in ranges:
                t.seek(off)
                data = t.read(n)
                if len(data) != n:
                    raise IOError(f"짧은 읽기 @{off}")
                out.write(struct.pack("<QI", off, n))
                out.write(data)
        out.flush()
        os.fsync(out.fileno())
    tmp.replace(OUTPUT)
    print(f"\n생성: {OUTPUT.name}  {OUTPUT.stat().st_size:,}B")
    print(f"SHA256 {file_hash(OUTPUT)}")


if __name__ == "__main__":
    main()
