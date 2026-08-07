# -*- coding: utf-8 -*-
"""상황을 맞춰 고른 A Portable 대사·음성을 OGs 플레이어 청크에 적용한다.

코덱스 이식본(`port_aportable_axel_voice.py`)은 0x416/0x417 을 고친 뒤
내용 교환을 다시 돌리는 구조였다. 여기서는 **플레이어 청크에 직접 쓴다** —
내용 교환은 이미 적용돼 있고, 슬롯 순서(f1/f2)도 그대로 두면 되기 때문이다.
바꾸는 것은 f3(텍스트 오프셋)·f4(음성ID)·문자열 풀뿐이다.

  0x3F4 / 0x4A4  ← runtime/place416.json (원본 0x416 슬롯 기준)
  0x4A5 / 0x521  ← runtime/place417.json (원본 0x417 슬롯 기준)

음성은 A Portable ATRAC3+ → PCM → PS2 ADPCM 으로 다시 인코딩해
OGs 액셀 bank 1046 의 고정 공간에 재패킹한다(인코더는 코덱스 도구 재사용).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

import battle_block as bb
import port_aportable_axel_voice as P
from ogs_korean_codec import encode

PAIRS = ((0x3F4, "place416"), (0x4A4, "place416"),
         (0x4A5, "place417"), (0x521, "place417"))


def chunk_writes(d: bytes, c: dict, key: int, rows, clip_slots, extras=()):
    """f3·f4·pool 을 새로 만든다. 기존 슬롯의 f1/f2 는 손대지 않는다.

    `extras` 는 내용 교환 때 잘려나간 **기체 선택 전용 슬롯**이다. 이건
    f1(문맥ID)·f2(플래그|키)까지 되살려야 하므로 빈 구간에 새로 쓴다.
    기준 ISO 를 보면 청크마다 `f2=0` 슬롯이 **맨 끝에 딱 하나**뿐이다 —
    0 은 종단자다. 그래서 빈 구간 앞쪽부터 채우되 **마지막 하나는 0 으로 남긴다.**
    """
    n = c["n"]
    a1 = bytearray(d[c["f2"] - 2 * n:c["f2"]])
    a2 = bytearray(d[c["f2"]:c["f2"] + 2 * n])
    a3 = bytearray(d[c["f3"]:c["f3"] + 2 * n])
    a4 = bytearray(d[c["f4"]:c["f4"] + 4 * n])
    free = [i for i in range(n)
            if struct.unpack_from("<H", a2, i * 2)[0] == 0][:-1]
    if len(free) < len(extras):
        raise ValueError(f"0x{key:X}: 빈 슬롯 {len(free)} < 추가 {len(extras)}")
    pool = bytearray()
    strings: dict[bytes, int] = {}
    slot = 0
    for i, e in zip(free, extras):
        struct.pack_into("<H", a1, i * 2, e["ctx"])
        struct.pack_into("<H", a2, i * 2, e["flag"] | key)
    for i in range(n):
        tag = struct.unpack_from("<H", a2, i * 2)[0]
        if (tag & 0x7FF) != key:
            continue
        if slot >= len(rows):
            raise ValueError(f"0x{key:X}: 슬롯 {slot} 에 대응하는 배치가 없다")
        r = rows[slot]
        slot += 1
        r = rows[slot - 1]
        raw = encode(r["text"])
        if raw in strings:
            off = strings[raw]
        else:
            off = len(pool)
            strings[raw] = off
            pool += raw + b"\0"
        struct.pack_into("<H", a3, i * 2, off)
        voice = 0
        if r["voice"]:
            voice = P.OG_AXEL_BANK * 1000 + clip_slots[r["voice"] % 1000]
        struct.pack_into("<I", a4, i * 4, voice)
    if slot != len(rows):
        raise ValueError(f"0x{key:X}: 슬롯 {slot} != 배치 {len(rows)}")
    if len(pool) > c["pool_cap"]:
        raise ValueError(f"0x{key:X} 풀 초과: {len(pool)}>{c['pool_cap']}")
    return [(c["f2"] - 2 * n, bytes(a1)), (c["f2"], bytes(a2)),
            (c["f3"], bytes(a3)), (c["f4"], bytes(a4)),
            (c["pool"], bytes(pool) + b"\0" * (c["pool_cap"] - len(pool)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aportable", type=Path, required=True)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--baseline", type=Path,
                    default=Path("baseline/srwogs-v1.4.3s1.iso"))
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--chunks", type=Path, default=Path("runtime/entry5_chunks.json"))
    ap.add_argument("--ffmpeg", type=Path, default=Path(
        "ffmpeg"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", type=Path,
                    default=Path("runtime/axel_placement_backup.bin"))
    ap.add_argument("--manifest", type=Path,
                    default=Path("runtime/axel_placement.json"))
    args = ap.parse_args()

    extra = json.loads(Path("runtime/machine_extra.json").read_text(encoding="utf-8"))
    if args.restore:
        rec = json.loads(args.manifest.read_text(encoding="utf-8"))
        blob = args.backup.read_bytes()
        with args.target.open("r+b") as fh:
            for r in rec["ranges"]:
                fh.seek(r["iso_offset"])
                fh.write(blob[r["backup_pos"]:r["backup_pos"] + r["length"]])
        print(f"복원 {len(rec['ranges'])}건: {args.target}")
        return

    places = {name: json.loads(Path(f"runtime/{name}.json").read_text(encoding="utf-8"))
              for _k, name in PAIRS}
    clips = sorted({r["voice"] % 1000
                    for rows in list(places.values()) + list(extra.values())
                    for r in rows if r["voice"]})
    if len(clips) > P.OG_BANK_CAPACITY:
        raise ValueError(f"클립 {len(clips)} > 용량 {P.OG_BANK_CAPACITY}")
    clip_slots = {c: i for i, c in enumerate(clips)}

    entry = bb.read_entry5(args.target)
    chunks = P.load_chunks(args.chunks)
    writes = []
    for key, name in PAIRS:
        ex = extra.get(f"{key:X}", [])
        rows = places[name] + [{"text": e["text"], "voice": e["voice"]} for e in ex]
        w = chunk_writes(entry, chunks[key], key, rows, clip_slots, ex)
        writes += w
        print(f"0x{key:X}: {len(places[name])}+{len(ex)}슬롯 / 풀 "
              f"0x{len(w[4][1].rstrip(bytes(1))):X}/{chunks[key]['pool_cap']:X}")

    # 이미 한 번 재패킹한 ISO 는 디스크립터가 중복돼 구간 판정이 실패한다.
    # 구간은 원판 배치이므로 **기준 ISO** 에서 읽는다.
    ptr, lo, hi = P.og_bank_region(args.baseline)
    print(f"클립 {len(clips)}/{P.OG_BANK_CAPACITY}, STRM 0x{hi-lo:X}")
    if not args.apply:
        print("(--apply 없음: 파일 미수정)")
        return

    containers = []
    for pos, clip in enumerate(clips, 1):
        pcm = P.decode_atrac(args.ffmpeg, P.a_riff(args.aportable, clip))
        containers.append(P.make_ild(P.encode_psx_adpcm(pcm)))
        if pos % 25 == 0 or pos == len(clips):
            print(f"  인코딩 {pos}/{len(clips)}")
    packed = b"".join(containers)
    if len(packed) > hi - lo:
        raise ValueError(f"음성 {len(packed)} > 공간 {hi-lo}")

    desc = bytearray()
    cursor = lo
    for ild in containers:
        desc += struct.pack("<III", cursor // P.SECTOR, len(ild), 0x13FFF)
        cursor += len(ild)
    first = bytes(desc[:12])
    while len(desc) < P.OG_BANK_CAPACITY * 12:
        desc += first

    base = bb.BATTLE_BASE + bb.ENTRY5_OFF
    ranges = [(base + off, data, "battle") for off, data in writes]
    ranges.append((P.OG_SHARED + P.OG_BANK_TABLE + ptr, bytes(desc), "descriptors"))
    ranges.append((P.OG_STRM + lo, packed + b"\0" * ((hi - lo) - len(packed)), "strm"))

    backup = bytearray()
    meta = []
    with args.target.open("r+b") as fh:
        for off, data, kind in ranges:
            fh.seek(off)
            meta.append({"iso_offset": off, "length": len(data),
                         "backup_pos": len(backup), "kind": kind})
            backup += fh.read(len(data))
        for off, data, _kind in ranges:
            fh.seek(off)
            fh.write(data)
    args.backup.write_bytes(bytes(backup))
    args.manifest.write_text(json.dumps({
        "kind": "axel-battle-line-placement",
        "target": str(args.target.resolve()),
        "clips": clips, "clip_slots": {str(k): v for k, v in clip_slots.items()},
        "packed": len(packed), "capacity": hi - lo, "ranges": meta,
        "backup_sha256": hashlib.sha256(bytes(backup)).hexdigest().upper(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"기록 완료: {args.target}")
    print(f"백업: {args.backup} / manifest: {args.manifest}")


if __name__ == "__main__":
    main()
