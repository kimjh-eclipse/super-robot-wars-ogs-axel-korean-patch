"""두 ISO(이전 릴리즈 적용본 → CURRENT)의 실제 diff로 업그레이드 구간 팩 생성.

사용: python build_upgrade_pack_from_iso.py <src.iso> <dst.iso> <out.bin> "<title>"
팩 포맷은 build_range_pack.py 와 동일("OGSAXLRNG"). 크기 동일 필수.
"""
from __future__ import annotations
import hashlib, os, struct, sys
from pathlib import Path
import numpy as np

MAGIC = b"OGSAXLRNG"; VERSION = 1; MERGE_GAP = 64; CHUNK = 16 * 1024 * 1024

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb", buffering=0) as f:
        for b in iter(lambda: f.read(CHUNK), b""): h.update(b)
    return h.hexdigest().upper()

def find_ranges(a: Path, b: Path):
    size = a.stat().st_size
    if size != b.stat().st_size: raise ValueError("크기 불일치")
    parts = []; off = 0
    with a.open("rb", buffering=0) as fa, b.open("rb", buffering=0) as fb:
        while off < size:
            x = fa.read(min(CHUNK, size - off)); y = fb.read(len(x))
            d = np.flatnonzero(np.frombuffer(x, np.uint8) != np.frombuffer(y, np.uint8))
            if d.size: parts.append(d.astype(np.int64) + off)
            off += len(x)
    if not parts: return []
    pos = np.concatenate(parts)
    cuts = np.flatnonzero(np.diff(pos) > MERGE_GAP + 1)
    starts = np.r_[0, cuts + 1]; ends = np.r_[cuts, len(pos) - 1]
    return [(int(pos[s]), int(pos[e] - pos[s] + 1)) for s, e in zip(starts, ends)]

def main():
    src, dst, out, title = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
    sh, dh = file_hash(src), file_hash(dst)
    ranges = find_ranges(src, dst)
    payload = sum(n for _, n in ranges)
    t = title.encode("utf-8")
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("wb", buffering=1 << 20) as o, dst.open("rb", buffering=0) as fd:
        o.write(MAGIC); o.write(struct.pack("<I", VERSION)); o.write(struct.pack("<H", len(t))); o.write(t)
        o.write(struct.pack("<Q", src.stat().st_size)); o.write(bytes.fromhex(sh)); o.write(bytes.fromhex(dh))
        o.write(struct.pack("<I", len(ranges)))
        for off, n in ranges:
            fd.seek(off); data = fd.read(n)
            if len(data) != n: raise IOError("짧은 읽기")
            o.write(struct.pack("<QI", off, n)); o.write(data)
        o.flush(); os.fsync(o.fileno())
    tmp.replace(out)
    print(f"src {sh}\ndst {dh}\n구간 {len(ranges):,}개 / 페이로드 {payload:,}B\n생성: {out.name} {out.stat().st_size:,}B")

if __name__ == "__main__":
    main()
