# -*- coding: utf-8 -*-
"""MAP.BIN 이벤트 대사 레코드를 초안 JSON 대로 교체한다.

근거: HANDOFF_EVENT_AND_PILOT_SWAP_2026-08-02.md §5-K

  이벤트 대사는 MAP.BIN 안에 NUL 구분 레코드로 들어 있다
  (`baseline/scenarios` 추출물과는 별개 계통 — 6화 대사는 0x5E23xxx~0x5E25xxx).
  레코드는 오프셋으로 참조되므로 **길이를 늘릴 수 없다.**
  새 문장은 원본 길이 이하여야 하고, 남는 자리는 NUL 로 채운다
  (엔진이 NUL 에서 멈추므로 짧아지는 건 안전하다).

가드: 쓰기 전 해당 위치의 바이트가 초안의 `orig` 를 인코딩한 것과 정확히 일치하고,
      바로 뒤가 NUL 인지 확인한다. 하나라도 어긋나면 전체를 중단한다.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from ogs_korean_codec import encode

MAP_ISO_OFF = 0xC10800


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--draft", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--backup", type=Path,
                    default=Path("runtime/scenario_text_backup.bin"))
    ap.add_argument("--manifest", type=Path,
                    default=Path("runtime/scenario_text.json"))
    args = ap.parse_args()

    if args.restore:
        rec = json.loads(args.manifest.read_text(encoding="utf-8"))
        blob = args.backup.read_bytes()
        with args.iso.open("r+b") as fh:
            for r in rec["ranges"]:
                fh.seek(MAP_ISO_OFF + r["off"])
                fh.write(blob[r["pos"]:r["pos"] + r["len"]])
        print(f"복원 {len(rec['ranges'])}건 완료: {args.iso}")
        return

    rows = json.loads(args.draft.read_text(encoding="utf-8"))
    plan, bad = [], []
    with args.iso.open("rb") as fh:
        for r in rows:
            off, olen = r["off"], r["orig_len"]
            want = encode(r["orig"])
            new = encode(r["new"])
            fh.seek(MAP_ISO_OFF + off)
            cur = fh.read(olen + 1)
            if len(want) != olen:
                bad.append((off, f"원본 인코딩 길이 {len(want)} != 기록된 {olen}"))
                continue
            if cur[:olen] != want:
                bad.append((off, "현재 바이트가 원본과 다름 (이미 수정됨?)"))
                continue
            if cur[olen:olen + 1] != b"\x00":
                bad.append((off, "레코드 끝이 NUL 이 아님"))
                continue
            if len(new) > olen:
                bad.append((off, f"새 문장 {len(new)}B > 상한 {olen}B"))
                continue
            plan.append({"off": off, "len": olen,
                         "data": new + b"\x00" * (olen - len(new)),
                         "orig": r["orig"], "new": r["new"],
                         "gain": olen - len(new)})

    print(f"검증 통과 {len(plan)}건 / 실패 {len(bad)}건")
    for off, why in bad:
        print(f"  ★ 0x{off:07X}: {why}")
    if bad:
        raise SystemExit("가드 실패 — 아무것도 쓰지 않음")
    for p in plan[:6]:
        print(f"  0x{p['off']:07X} (-{p['gain']:3}B) {p['new'].replace('@',' / ')[:64]}")
    print(f"  … 총 {len(plan)}건")

    if not args.apply:
        print("(--apply 없음: 파일 미수정)")
        return

    backup = bytearray()
    meta = []
    with args.iso.open("rb") as fh:
        for p in plan:
            fh.seek(MAP_ISO_OFF + p["off"])
            meta.append({"off": p["off"], "len": p["len"], "pos": len(backup)})
            backup += fh.read(p["len"])
    args.backup.parent.mkdir(parents=True, exist_ok=True)
    args.backup.write_bytes(bytes(backup))

    with args.iso.open("r+b") as fh:
        for p in plan:
            fh.seek(MAP_ISO_OFF + p["off"])
            fh.write(p["data"])
    print(f"기록 완료: {args.iso}")

    args.manifest.write_text(json.dumps({
        "kind": "ogs-scenario-text-role-swap",
        "iso": str(args.iso.resolve()),
        "map_iso_off": MAP_ISO_OFF,
        "count": len(plan),
        "ranges": meta,
        "backup_sha256": hashlib.sha256(bytes(backup)).hexdigest().upper(),
        "edits": [{"off": f"0x{p['off']:X}", "orig": p["orig"],
                   "new": p["new"]} for p in plan],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"백업: {args.backup} / manifest: {args.manifest}")


if __name__ == "__main__":
    main()
