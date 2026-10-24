# -*- coding: utf-8 -*-
"""적 라미아·안쥬르그 능력치를 원본 액셀·소울게인 기준으로 맞춘다 (2026-10-24 사용자 지시).

지시:
  - 무기 등급별 공격력 = 원본 액셀(소울게인) 같은 등급 무기 공격력 - 400
  - 회피·명중은 원본 액셀과 똑같이
  - 액셀의 사격 -> 라미아의 격투, 액셀의 격투 -> 라미아의 사격

대상(역할 교체 후 적 라미아가 타는 안쥬르그 슬롯)과 기준(원본 ISO의 같은 슬롯 = 원본 액셀 소울게인):
  Unit[0xCE]  무장 0x8AE~0x8B2   <- 원본 Unit[0xCE]  무장 0xA5C~0xA60
  Unit[0x136] 무장 0x8B3~0x8B7   <- 원본 Unit[0x136] 무장 0xD86~0xD8A
  Plot 242/243 (raw 0x416/0x417, 적 라미아) <- 원본 Plot 53/54 (액셀)

필드(기준 ISO 전수 분포로 판정):
  Unit +0x53 운동성(전함 50~60, 고기동기 140~150)
  Weap +0x08 u16 공격력, +0x0A 명중 보정
  Plot +0x65 격투, +0x66 사격, +0x67 명중, +0x68 회피
무기 등급 = 각 기체의 일반 무장 5개를 공격력 순으로 정렬한 순위.
SHARED·IM 두 사본 모두 쓰며, 쓰기 전 현재 값이 기대값과 같은지 확인한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_K.iso"
BASE = ROOT / "baseline" / "srwogs-v1.4.3s1.iso"
MANIFEST = ROOT / "runtime" / "enemy_lamia_stats_20261024.json"

TARGETS = {"shared": 0x5DA000, "im": 0x83F000}
UD, US = 0x11F8A4, 0x64
WT = 0x129F70 + 0x0C
WD, WS = 0x12BF7C + 0x0C, 0x24
PL, PS = 0x13B484 + 0x0C, 0x94

MOB = 0x53
DELTA = 400  # 원본 액셀 같은 등급 공격력에서 뺄 값 (--delta)
POW, HIT = 0x08, 0x0A
MELEE, SHOOT, ACC, EVA = 0x65, 0x66, 0x67, 0x68

UNITS = [  # (대상 슬롯, 대상 무장 ID, 기준 슬롯, 기준 무장 ID)
    (0xCE, range(0x8AE, 0x8B3), 0xCE, range(0xA5C, 0xA61)),
    (0x136, range(0x8B3, 0x8B8), 0x136, range(0xD86, 0xD8B)),
]
PILOTS = [(242, 53), (243, 54)]  # (라미아 Plot, 원본 액셀 Plot)


def rd(f, off, n):
    f.seek(off)
    return f.read(n)


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def plan(cur, base):
    edits = []  # (iso_off, before, after, label)
    for name, sec in TARGETS.items():
        def widx(f, wid):
            return u16(rd(f, sec + WT + wid * 2, 2), 0)

        for dst, dws, src, sws in UNITS:
            uo = sec + UD + dst * US
            mob_new = rd(base, sec + UD + src * US + MOB, 1)
            edits.append((uo + MOB, rd(cur, uo + MOB, 1), mob_new,
                          f"{name} Unit[0x{dst:X}] 운동성"))
            mine = sorted(((u16(rd(cur, sec + WD + widx(cur, w) * WS, WS), POW), w) for w in dws))
            ref = sorted(((u16(rd(base, sec + WD + widx(base, w) * WS, WS), POW),
                           rd(base, sec + WD + widx(base, w) * WS + HIT, 1)) for w in sws))
            for (pow_old, w), (pow_ref, hit_ref) in zip(mine, ref):
                wo = sec + WD + widx(cur, w) * WS
                edits.append((wo + POW, rd(cur, wo + POW, 2), struct.pack("<H", pow_ref - DELTA),
                              f"{name} 무장0x{w:X} 공격력 {pow_old}->{pow_ref - DELTA} (기준 {pow_ref})"))
                edits.append((wo + HIT, rd(cur, wo + HIT, 1), hit_ref,
                              f"{name} 무장0x{w:X} 명중보정"))
        for lam, axl in PILOTS:
            lo, ao = sec + PL + lam * PS, sec + PL + axl * PS
            a = rd(base, ao, PS)
            for fld, val, lab in ((MELEE, a[SHOOT], "격투<-액셀 사격"), (SHOOT, a[MELEE], "사격<-액셀 격투"),
                                  (ACC, a[ACC], "명중"), (EVA, a[EVA], "회피")):
                edits.append((lo + fld, rd(cur, lo + fld, 1), bytes([val]),
                              f"{name} Plot{lam} {lab}"))
    return edits


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(1 << 24):
            h.update(b)
    return h.hexdigest().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--expect", help="적용 전 ISO SHA256")
    ap.add_argument("--delta", type=int, default=400)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    args = ap.parse_args()
    global DELTA
    DELTA = args.delta
    with ISO.open("rb") as cur, BASE.open("rb") as base:
        for name, sec in TARGETS.items():
            if rd(cur, sec + 0x11F898, 4) != b"Unit" or rd(cur, sec + 0x13B484, 4) != b"Plot":
                raise SystemExit(f"{name}: 테이블 매직 불일치")
        for dst, *_ in UNITS:  # 대상이 안쥬르그(uid 0x2B)인지
            for sec in TARGETS.values():
                if u16(rd(cur, sec + UD + dst * US, US), 0x46) != 0x2B:
                    raise SystemExit(f"Unit[0x{dst:X}] 이 안쥬르그가 아니다")
        edits = plan(cur, base)
        # SHARED/IM 동일성: 같은 상대 위치의 before 가 같아야 한다
        half = len(edits) // 2
        for e1, e2 in zip(edits[:half], edits[half:]):
            if e1[1] != e2[1] or e1[2] != e2[2]:
                raise SystemExit(f"SHARED/IM 불일치: {e1[3]} / {e2[3]}")
    for off, b, a, lab in edits[:half]:
        show = (lambda x: u16(x, 0)) if len(a) == 2 else (lambda x: x[0])
        print(f"  {lab}: {show(b)} -> {show(a)}")
    changed = [e for e in edits if e[1] != e[2]]
    print(f"변경 {len(changed)}건 (SHARED+IM)")
    if not args.apply:
        return
    before = sha(ISO)
    if args.expect and before != args.expect.upper():
        raise SystemExit(f"ISO 해시 불일치: {before}")
    with ISO.open("r+b") as f:
        for off, b, a, _ in changed:
            f.seek(off)
            if f.read(len(b)) != b:
                raise SystemExit(f"쓰기 직전 값 불일치 0x{off:X}")
            f.seek(off)
            f.write(a)
    after = sha(ISO)
    args.manifest.write_text(json.dumps({
        "kind": "enemy-lamia-stats-from-original-axel",
        "before_sha256": before, "after_sha256": after,
        "edits": [{"iso_off": off, "before": b.hex(), "after": a.hex(), "label": lab}
                  for off, b, a, lab in changed],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("before", before)
    print("after ", after)


if __name__ == "__main__":
    main()
