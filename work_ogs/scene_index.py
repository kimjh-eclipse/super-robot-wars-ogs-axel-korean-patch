# -*- coding: utf-8 -*-
"""시나리오 대사 구간을 **장면 덩어리 단위**로 색인한다.

전수 대조를 위한 준비. 규칙 배치로 밀어넣지 않고 장면을 처음부터 끝까지 읽어
판단하려면, 먼저 어떤 장면이 몇 줄인지와 역할 인물이 나오는지를 알아야 한다.

레코드는 NUL 구분이고 장면 사이에는 큰 공백이 있어서, 간격 0x4000 이상이면
다른 장면으로 끊는다. 역할명이 한 번도 안 나오는 장면은 그 안의 `그녀/언니/여자`도
다른 인물을 가리키므로 읽을 대상에서 뺀다(근거를 남기려고 수치를 같이 출력한다).
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from ogs_korean_codec import decode, encode

MAP_ISO_OFF = 0xC10800
REGION = (0x5C00000, 0x6900000)
GAP = 0x4000

ROLE = ("라미아", "러브레스", "안쥬르그", "액셀", "알마", "소울게인",
        "Ｗ１７", "ＳＭＳＣ", "ＥＧ－Ｘ")
HANGUL = re.compile(r"[가-힣]")


def read_records(iso: Path):
    a, b = REGION
    with iso.open("rb") as fh:
        fh.seek(MAP_ISO_OFF + a)
        data = fh.read(b - a)
    pos = a
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
        yield off, len(raw), text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("runtime/scenes.json"))
    args = ap.parse_args()

    recs = list(read_records(args.iso))
    scenes, cur = [], [recs[0]]
    for r in recs[1:]:
        if r[0] - cur[-1][0] > GAP:
            scenes.append(cur)
            cur = []
        cur.append(r)
    scenes.append(cur)

    # "액셀렌" 은 엑셀렌 브라우닝의 이표기라 액셀과 무관하다 — 세지 않는다.
    out = []
    for i, sc in enumerate(scenes):
        joined = "\n".join(t for _, _, t in sc)
        hits = {w: joined.count(w) for w in ROLE if w in joined}
        if "액셀" in hits:
            hits["액셀"] -= joined.count("액셀렌")
            if hits["액셀"] <= 0:
                del hits["액셀"]
        out.append({
            "id": i, "start": sc[0][0], "end": sc[-1][0],
            "records": len(sc), "roles": hits,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    todo = [s for s in out if s["roles"]]
    print(f"장면 {len(out)}개 / 레코드 {len(recs)}줄")
    print(f"역할 인물 등장 장면 {len(todo)}개 / "
          f"읽을 레코드 {sum(s['records'] for s in todo)}줄")
    print(f"제외 {len(out) - len(todo)}개 / "
          f"{sum(s['records'] for s in out if not s['roles'])}줄")
    for s in todo:
        r = " ".join(f"{k}{v}" for k, v in sorted(s["roles"].items(),
                                                  key=lambda kv: -kv[1]))
        print(f"  #{s['id']:3} 0x{s['start']:07X} {s['records']:5}줄  {r}")


if __name__ == "__main__":
    main()
