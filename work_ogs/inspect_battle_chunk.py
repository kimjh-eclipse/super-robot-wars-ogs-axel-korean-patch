# -*- coding: utf-8 -*-
"""전투대사 청크를 (문맥ID, 플래그, 대사, 음성ID) 로 펼쳐 본다.

코덱스가 A Portable 대사를 이식하며 **풀 순환**으로 배치해서(`plan_chunk`),
슬롯의 실제 문맥(무기·상대·상황)과 문장이 어긋났다. 다시 배치하려면 먼저
"어떤 슬롯이 어떤 상황인가"를 봐야 한다.

f1 = 문맥ID(무기ID 또는 상대 raw키, 0xFFFF=무조건), f2 = 플래그|raw키,
f3 = 풀 상대오프셋, f4 = 음성ID.
"""
from __future__ import annotations
import argparse
import json
import struct
from pathlib import Path

import battle_block as bb
from ogs_korean_codec import decode


def load_chunks(path: Path) -> dict[int, dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda x: x["off"])
    out = {}
    for i, c in enumerate(rows):
        t = [int(x, 16) for x in c["t"]]
        nxt = rows[i + 1]["off"] if i + 1 < len(rows) else bb.ENTRY5_SIZE
        out[c["key"]] = {
            "off": c["off"], "n": (t[1] - t[0]) // 2,
            "f2": c["off"] + t[0], "f3": c["off"] + t[1],
            "f4": c["off"] + t[2], "pool": c["off"] + t[3],
            "pool_cap": nxt - (c["off"] + t[3]),
        }
    return out


def rows_of(d: bytes, c: dict, key: int):
    n = c["n"]
    f1 = c["f2"] - 2 * n
    for i in range(n):
        tag = struct.unpack_from("<H", d, c["f2"] + i * 2)[0]
        if (tag & 0x7FF) != key:
            continue
        ctx = struct.unpack_from("<H", d, f1 + i * 2)[0]
        off = struct.unpack_from("<H", d, c["f3"] + i * 2)[0]
        voice = struct.unpack_from("<I", d, c["f4"] + i * 4)[0]
        end = d.index(b"\0", c["pool"] + off)
        try:
            text = decode(d[c["pool"] + off:end])
        except Exception:
            text = "<디코드실패>"
        yield i, ctx, tag & 0xF800, voice, text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, required=True)
    ap.add_argument("--key", type=lambda v: int(v, 0), required=True)
    ap.add_argument("--chunks", type=Path, default=Path("runtime/entry5_chunks.json"))
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    d = bb.read_entry5(args.iso)
    c = load_chunks(args.chunks)[args.key]
    out = []
    for i, ctx, flag, voice, text in rows_of(d, c, args.key):
        out.append({"i": i, "ctx": ctx, "flag": flag, "voice": voice, "text": text})
        print(f"{i:4} ctx=0x{ctx:04X} flag=0x{flag:04X} v=0x{voice:06X} "
              f"{text.replace('@', ' / ')}")
    print(f"--- 0x{args.key:X}: {len(out)}줄 ---")
    if args.json:
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                             encoding="utf-8")


if __name__ == "__main__":
    main()
