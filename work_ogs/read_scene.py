# -*- coding: utf-8 -*-
"""장면 하나를 처음부터 끝까지 순서대로 출력한다 — 전수 대조용.

`build_dialogue_workbench.py` 는 태그가 붙은 줄 주변만 발췌해서, 태그가 없는
줄(성별 전제·관계 전제)이 통째로 빠진다. 실제로 `엑셀렌：…쭉쭉～빵빵이라고` 같은
줄은 어떤 태그에도 안 걸렸다. 그래서 이 도구는 **거르지 않고 전부** 낸다.

역할 인물이 나오는 줄에만 `*` 를 붙여 눈에 띄게 하되, 판단은 앞뒤를 읽고 한다.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from ogs_korean_codec import decode

MAP_ISO_OFF = 0xC10800
HANGUL = re.compile(r"[가-힣]")
ROLE = ("라미아", "러브레스", "안쥬르그", "알마", "소울게인",
        "Ｗ１７", "ＳＭＳＣ", "ＥＧ－Ｘ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--scene", type=int)
    ap.add_argument("--start", type=lambda v: int(v, 0))
    ap.add_argument("--end", type=lambda v: int(v, 0))
    ap.add_argument("--scenes", type=Path, default=Path("runtime/scenes.json"))
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.scene is not None:
        sc = json.loads(args.scenes.read_text(encoding="utf-8"))[args.scene]
        a, b = sc["start"], sc["end"] + 0x200
    else:
        a, b = args.start, args.end

    with args.iso.open("rb") as fh:
        fh.seek(MAP_ISO_OFF + a)
        data = fh.read(b - a)

    rows, pos = [], a
    for raw in data.split(b"\x00"):
        off = pos
        pos += len(raw) + 1
        if len(raw) < 4:
            continue
        try:
            text = decode(raw)
        except Exception:
            continue
        if not HANGUL.search(text):
            continue
        rows.append((off, len(raw), text))

    sel = rows[args.skip:]
    if args.limit:
        sel = sel[:args.limit]
    for off, ln, text in sel:
        s = text.replace("액셀렌", "")
        mark = "*" if ("액셀" in s or any(w in text for w in ROLE)) else " "
        print(f"{mark}0x{off:07X}[{ln:3}] {text.replace('@', ' / ')}")
    print(f"--- {len(rows)}줄 중 {args.skip}~{args.skip + len(sel)} ---")


if __name__ == "__main__":
    main()
