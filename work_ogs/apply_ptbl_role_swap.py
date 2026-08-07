# -*- coding: utf-8 -*-
"""PTbl 양방향 역할 교환 — 라미아 ↔ 액셀.

근거: HANDOFF_EVENT_AND_PILOT_SWAP_2026-08-02.md §5-A-13, §5-H

  PTbl 은 raw키 → Plot 인덱스 해석 테이블이고, Plot 이 인물 마스터다
  (이름·초상화·능력치·지형적응). 리졸버 `0x1A2900` 이 모든 표시 경로의 병목이므로
  **PTbl 6엔트리만 서로 바꾸면 게임 전체의 참조가 한 번에 뒤바뀐다** —
  이벤트 초상화, 상태창, 그리고 맵에 적으로 등장하는 액셀까지.

  기준 ISO 확인(PTbl 역참조 전수):
    초상화 0x7E(라미아) → Plot 12, 242, 243, 381   ← raw키 0x3F4, 0x4A4, 0x4A5, 0x521
    초상화 0x14(액셀)   → Plot 53, 54              ← raw키 0x416, 0x417
    Plot +0x4C 대표키쌍: 라미아 (0x03D4, 0x04A4) / 액셀 (0x03F6, 0x0416)
    ⇒ 주 대응은 0x4A4 ↔ 0x416. Plot 12 는 라미아의 ???(미공개) 변형이라
      +0x4C 상위가 0xFFFF 이고 액셀에는 대응이 없다.

  MAP.BIN 의 raw키를 직접 고치는 방식과는 **양립하지 않는다**. 그쪽을 먼저 원복할 것.

모든 쓰기는 3중 가드를 통과할 때만 수행한다:
  (1) PTbl/Plot 매직, (2) 현재 인덱스 == before, (3) before/after Plot 의 초상화가 기대값.
"""
from __future__ import annotations
import argparse
import json
import struct
from pathlib import Path

PT_MAGIC = 0x13A478
PT_DATA = PT_MAGIC + 0x0C
PL_MAGIC = 0x13B484
PL_DATA = PL_MAGIC + 0x0C
PL_STRIDE = 0x94
POR_OFF = 0x48

LAMIA_POR = 0x7E
AXEL_POR = 0x14

# raw키 → (원래 Plot, 교환 후 Plot, 원래 초상화, 교환 후 초상화)
SWAPS = {
    0x3F4: (12, 53, LAMIA_POR, AXEL_POR),    # 라미아 ??? → 액셀
    0x4A4: (242, 53, LAMIA_POR, AXEL_POR),   # 라미아 A  → 액셀 A
    0x4A5: (243, 54, LAMIA_POR, AXEL_POR),   # 라미아 B  → 액셀 B
    0x521: (381, 54, LAMIA_POR, AXEL_POR),   # 라미아 C  → 액셀 B
    0x416: (53, 242, AXEL_POR, LAMIA_POR),   # 액셀 A    → 라미아 A
    0x417: (54, 243, AXEL_POR, LAMIA_POR),   # 액셀 B    → 라미아 B
}

TARGETS = {"shared": 0x5DA000, "im": 0x83F000}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--manifest", type=Path,
                    default=Path("runtime/ptbl_role_swap.json"))
    args = ap.parse_args()

    fh = args.iso.open("r+b" if args.apply else "rb")
    report = {}
    ok = True

    for name, base in TARGETS.items():
        def rd(pos, n):
            fh.seek(base + pos); return fh.read(n)

        if rd(PT_MAGIC, 4) != b"PTbl" or rd(PL_MAGIC, 4) != b"Plot":
            raise SystemExit(f"{name}: PTbl/Plot 매직 불일치")

        applied, skipped = [], []
        for raw, (old, new, por_old, por_new) in SWAPS.items():
            frm, to = (new, old) if args.restore else (old, new)
            exp_from = por_new if args.restore else por_old
            exp_to = por_old if args.restore else por_new
            off = PT_DATA + raw * 2
            cur = struct.unpack("<H", rd(off, 2))[0]
            if cur != frm:
                skipped.append({"raw": f"0x{raw:X}",
                                "reason": f"현재 인덱스 {cur} != {frm}"})
                ok = False
                continue
            pf = struct.unpack("<H", rd(PL_DATA + frm * PL_STRIDE + POR_OFF, 2))[0]
            pt = struct.unpack("<H", rd(PL_DATA + to * PL_STRIDE + POR_OFF, 2))[0]
            if pf != exp_from or pt != exp_to:
                skipped.append({"raw": f"0x{raw:X}",
                                "reason": f"초상화 불일치 {frm}=0x{pf:X} {to}=0x{pt:X}"})
                ok = False
                continue
            if args.apply:
                fh.seek(base + off); fh.write(struct.pack("<H", to))
            applied.append({"raw": f"0x{raw:X}", "offset": f"0x{off:X}",
                            "before": frm, "after": to,
                            "portrait_before": f"0x{pf:02X}",
                            "portrait_after": f"0x{pt:02X}"})

        report[name] = {"applied": applied, "skipped": skipped}
        verb = "복원" if args.restore else "교환"
        print(f"[{name}] {verb} {len(applied)}건 / 건너뜀 {len(skipped)}건")
        for a in applied:
            print(f"  OK   PTbl[{a['raw']}] @{a['offset']}: Plot {a['before']}"
                  f"(초상화 {a['portrait_before']}) -> {a['after']}"
                  f"({a['portrait_after']})")
        for s in skipped:
            print(f"  SKIP {s['raw']}: {s['reason']}")

    fh.close()
    if not args.apply:
        print("(--apply 없음: 파일 미수정)")
        return
    if not ok:
        print("경고: 건너뛴 규칙이 있음 — SHARED/IM 상태가 어긋났을 수 있음")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({
        "kind": "ogs-ptbl-role-swap-bidirectional",
        "iso": str(args.iso.resolve()),
        "restore": args.restore,
        "targets": {k: f"0x{v:X}" for k, v in TARGETS.items()},
        "report": report,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"manifest: {args.manifest}")


if __name__ == "__main__":
    main()
