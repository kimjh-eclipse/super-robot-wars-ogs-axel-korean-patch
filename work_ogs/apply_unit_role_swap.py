# -*- coding: utf-8 -*-
"""기체 교환을 **양방향**으로 마무리한다 — 적 소울게인 슬롯에 안쥬르그를 넣는다.

지금까지는 단방향이었다. 아군 안쥬르그 슬롯에 소울게인을 복사해 플레이어는
소울게인을 타지만, 적 쪽은 여전히 소울게인이라 "라미아 얼굴로 소울게인" 이었다.

유닛 마스터(SHARED/IM entry3 `Unit`, 데이터 0x11F8A4, 스트라이드 0x64) 실측:

```text
Unit[0x48]  안쥬르그  HP 6200  무장 0x8AE~0x8B2  (적)
Unit[0x49]  안쥬르그  HP 6200  무장 0x8B3~0x8B7  (적)
Unit[0x1A1] 안쥬르그  HP 6200  무장 0xD97~0xD9B  (아군)
Unit[0xCE]  소울게인  HP 150000 무장 0xA5C~0xA62 (적·보스)
Unit[0x136] 소울게인  HP 6800  무장 0xD86~0xD8C  (아군)
```

무장 ID 대역이 아군끼리(0xD8x/0xD9x) 적끼리(0x8Bx/0xA5x) 붙어 있어 편이 갈린다.
`+0x46` 이 기체 uid(안쥬르그 0x2B / 소울게인 0x63), `+0x0C` 가 internal id.

교환:
  Unit[0x136] ← 안쥬르그(0x1A1 원본)   아군 자리. 전체 복사.
  Unit[0xCE]  ← 안쥬르그(0x48 원본)    적 보스 자리.
                **HP(+0x00)와 +0x02 플래그는 원래 값을 남긴다** —
                전체를 덮으면 15만 HP 보스가 6200 이 되어 밸런스가 무너진다.

원본 안쥬르그 레코드는 이미 소울게인으로 덮여 있으므로 **기준 ISO에서 읽는다.**
SHARED 와 IM 양쪽에 써야 한다(PTbl 때와 같다).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

UNIT_DATA = 0x11F8A4          # SHARED/IM entry3 상대
STRIDE = 0x64
TARGETS = {"shared": 0x5DA000, "im": 0x83F000}

UID_ANGELG, UID_SOULGAIN = 0x2B, 0x63
IID_ANGELG, IID_SOULGAIN = 0xD3, 0x14A

# (목적지 슬롯, 원본 안쥬르그 슬롯, HP·플래그 보존 여부)
SWAPS = [
    (0x136, 0x1A1, False),
    (0x0CE, 0x048, True),
]


def unit_off(base: int, idx: int) -> int:
    return base + UNIT_DATA + idx * STRIDE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--backup", type=Path, default=Path("runtime/unit_swap_backup.bin"))
    ap.add_argument("--manifest", type=Path, default=Path("runtime/unit_swap.json"))
    args = ap.parse_args()

    if args.restore:
        rec = json.loads(args.manifest.read_text(encoding="utf-8"))
        blob = args.backup.read_bytes()
        with args.iso.open("r+b") as fh:
            for r in rec["ranges"]:
                fh.seek(r["off"])
                fh.write(blob[r["pos"]:r["pos"] + STRIDE])
        print(f"복원 {len(rec['ranges'])}건: {args.iso}")
        return

    plan = []
    with args.baseline.open("rb") as bh, args.iso.open("rb") as th:
        for name, base in TARGETS.items():
            for dst, src, keep_hp in SWAPS:
                bh.seek(unit_off(base, src))
                source = bytearray(bh.read(STRIDE))
                th.seek(unit_off(base, dst))
                cur = th.read(STRIDE)
                # 가드: 원본은 안쥬르그, 목적지는 소울게인이어야 한다
                if struct.unpack_from("<H", source, 0x46)[0] != UID_ANGELG:
                    raise SystemExit(f"{name} 0x{src:X}: 원본이 안쥬르그가 아니다")
                if struct.unpack_from("<H", source, 0x0C)[0] != IID_ANGELG:
                    raise SystemExit(f"{name} 0x{src:X}: internal id 불일치")
                if struct.unpack_from("<H", cur, 0x46)[0] != UID_SOULGAIN:
                    raise SystemExit(f"{name} 0x{dst:X}: 목적지가 소울게인이 아니다")
                if keep_hp:
                    source[0x00:0x04] = cur[0x00:0x04]   # HP + 플래그 보존
                plan.append((name, unit_off(base, dst), bytes(source), dst, src,
                             struct.unpack_from("<H", cur, 0)[0],
                             struct.unpack_from("<H", source, 0)[0]))

    for name, off, _data, dst, src, oldhp, newhp in plan:
        print(f"  {name:6} Unit[0x{dst:X}] ← 안쥬르그(0x{src:X})  "
              f"HP {oldhp} → {newhp}  @0x{off:X}")
    if not args.apply:
        print("(--apply 없음: 파일 미수정)")
        return

    backup = bytearray()
    meta = []
    with args.iso.open("r+b") as fh:
        for _name, off, data, *_ in plan:
            fh.seek(off)
            meta.append({"off": off, "pos": len(backup)})
            backup += fh.read(STRIDE)
        for _name, off, data, *_ in plan:
            fh.seek(off)
            fh.write(data)
    args.backup.write_bytes(bytes(backup))
    args.manifest.write_text(json.dumps({
        "kind": "ogs-unit-role-swap-reverse",
        "iso": str(args.iso.resolve()),
        "swaps": [{"dst": f"0x{d:X}", "src": f"0x{s:X}", "keep_hp": k}
                  for d, s, k in SWAPS],
        "ranges": meta,
        "backup_sha256": hashlib.sha256(bytes(backup)).hexdigest().upper(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"기록 완료: {args.iso}")
    print(f"백업: {args.backup} / manifest: {args.manifest}")


if __name__ == "__main__":
    main()
