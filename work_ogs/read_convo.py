# -*- coding: utf-8 -*-
"""대화 단위로 잘라, 라미아·액셀이 나오는 대화만 **통째로** 낸다.

장면 전체(4만 줄)를 한 줄씩 읽는 건 현실적이지 않고, 반대로 태그 붙은 줄만
발췌하면 `엑셀렌：…쭉쭉～빵빵이라고` 처럼 아무 표식도 없는 줄이 빠진다.
그래서 중간을 택한다 — **그 인물이 있는 대화는 처음부터 끝까지 읽는다.**

대화 경계는 화자가 없는 레코드(`：`·`（` 없는 줄 = 장소·상황 표기)로 잡는다.
전투 시작 전후로 삽입되는 정형 대사 뭉치(퇴각/격추)는 화자 라벨만 보면 되므로
`--skip-boiler` 로 접을 수 있다.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from ogs_korean_codec import decode

MAP_ISO_OFF = 0xC10800
HANGUL = re.compile(r"[가-힣]")
SPEAKER = re.compile(r"^([^：（(]{1,12})[：（]")
ROLE = ("라미아", "러브레스", "안쥬르그", "알마", "소울게인",
        "Ｗ１７", "ＳＭＳＣ", "ＥＧ－Ｘ")
# 모든 맵에 붙는 퇴각·격추 정형 뭉치 — 내용이 아니라 화자 라벨만 문제라 접는다.
BOILER = ("여기까진가", "꼴사납군", "꼴　사납군", "떨어지는…가", "탈출하겠",
          "탈출합니다", "탈출한다", "물러날", "여기까지")


def is_role(text: str) -> bool:
    return "액셀" in text.replace("액셀렌", "") or any(w in text for w in ROLE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--scene", type=int, required=True)
    ap.add_argument("--scenes", type=Path, default=Path("runtime/scenes.json"))
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    sc = json.loads(args.scenes.read_text(encoding="utf-8"))[args.scene]
    with args.iso.open("rb") as fh:
        fh.seek(MAP_ISO_OFF + sc["start"])
        data = fh.read(sc["end"] + 0x200 - sc["start"])

    rows, pos = [], sc["start"]
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

    # 화자 없는 줄에서 대화를 끊는다
    convos, cur = [], []
    for r in rows:
        if not SPEAKER.match(r[2]) and cur:
            convos.append(cur)
            cur = []
        cur.append(r)
    if cur:
        convos.append(cur)

    todo = [c for c in convos if any(is_role(t) for _, _, t in c)]
    boiler = [c for c in todo
              if all(any(b in t for b in BOILER) or not SPEAKER.match(t)
                     for _, _, t in c)]
    todo = [c for c in todo if c not in boiler]

    print(f"# 장면 {args.scene}: 대화 {len(convos)} / 역할 등장 "
          f"{len(todo) + len(boiler)} (정형 {len(boiler)})")
    sel = todo[args.skip:]
    if args.limit:
        sel = sel[:args.limit]
    for i, c in enumerate(sel, start=args.skip):
        print(f"\n===== 대화 {i}  0x{c[0][0]:07X}  {len(c)}줄 =====")
        for off, ln, text in c:
            mark = "*" if is_role(text) else " "
            print(f"{mark}0x{off:07X}[{ln:3}] {text.replace('@', ' / ')}")
    print(f"\n--- 역할 대화 {len(todo)}개 중 "
          f"{args.skip}~{args.skip + len(sel)} ---")


if __name__ == "__main__":
    main()
