# -*- coding: utf-8 -*-
"""SRW A Portable [K] 에서 액셀 대사를 전량 추출해 Markdown 으로 낸다.

배경
  A Portable(PSP)은 OGs(PS2)와 같은 엔진 계열이다 — LICE/Wpbb 아카이브,
  `PTbl`/`Plot`/`Unit`/`Weap`/`Sent` 태그, 그리고 **동일한 전투대사 청크 구조**
  (헤더 u16[16] 의 [12..15] = f2/f3/f4/pool, 병렬배열 4개 + 문자열 풀).

  원본 아카이브(battle.bin/shared.bin/map.bin)는 일본어 그대로이고,
  한국어 패치는 **USRDIR/dummy.bin** 에 따로 들어 있다. 코덱은 OGs 와 동일.

추출 대상
  전투대사 청크 (dummy.bin = 한국어 / battle.bin 엔트리2 = 일본어, 인덱스로 짝지음)
    raw키 0x0D4  아군 액셀 (기억상실 시절, 반말)
    raw키 0x0D5  각성 후 액셀
  시나리오 대사 (dummy.bin 평면 텍스트 풀)
    화자가 액셀인 줄 + 그 앞뒤 문맥
"""
from __future__ import annotations
import argparse
import re
import struct
from pathlib import Path

from ogs_korean_codec import decode as kdec, encode as kenc

ISO_DEFAULT = Path("../Super Robot Wars A Portable [K].iso")
DUMMY = 0x6D50000
DUMMY_SIZE = 0x15340000
BATTLE = 0x36060000

KR_CHUNK_REGION = (0x7C0000, 0x800000)   # dummy.bin 내 전투대사 청크 대역
AXEL_KEYS = {0x0D4: "아군 액셀 (기억상실)", 0x0D5: "각성 후 액셀"}

FLAG = {0x0000: "일반", 0x0800: "공격", 0x1000: "-", 0x1800: "피격/격파",
        0x2000: "-", 0x3800: "회피/명중", 0x4800: "라이벌", 0x7000: "필살/무기명"}
HANGUL = re.compile(r"[가-힣]")


def chunk_at(d: bytes, o: int):
    if o + 0x20 > len(d):
        return None
    t = struct.unpack_from("<4H", d, o + 0x18)
    if not all(t[i] < t[i + 1] for i in range(3)):
        return None
    if not (0 < t[0] < 0x40000) or t[3] >= 0x40000:
        return None
    if (t[1] - t[0]) != (t[2] - t[1]):
        return None
    n = (t[1] - t[0]) // 2
    if not (8 <= n <= 1500):
        return None
    if abs((t[3] - t[2]) - 4 * n) > 8:
        return None
    key = struct.unpack_from("<H", d, o + t[0])[0] & 0x7FF
    if key == 0:
        return None
    return {"off": o, "n": n, "f2": o + t[0], "f3": o + t[1],
            "f4": o + t[2], "pool": o + t[3], "key": key}


def find_chunks(d: bytes, key_filter=None) -> list[dict]:
    out = []
    for o in range(0, len(d) - 0x40, 0x800):
        c = chunk_at(d, o)
        if c and (key_filter is None or c["key"] in key_filter):
            out.append(c)
    return out


def read_chunk(d: bytes, c: dict, dec) -> list[dict]:
    rows = []
    f1 = c["f2"] - 2 * c["n"]
    for i in range(c["n"]):
        tag = struct.unpack_from("<H", d, c["f2"] + i * 2)[0]
        if (tag & 0x7FF) != c["key"]:
            continue
        off = struct.unpack_from("<H", d, c["f3"] + i * 2)[0]
        end = d.find(b"\x00", c["pool"] + off)
        raw = d[c["pool"] + off:end]
        try:
            txt = dec(raw)
        except Exception:
            txt = "<디코드 실패>"
        rows.append({
            "i": i,
            "trig": struct.unpack_from("<H", d, f1 + i * 2)[0],
            "flag": tag & 0xF800,
            "vid": struct.unpack_from("<I", d, c["f4"] + i * 4)[0],
            "text": txt.replace("　", " "),
        })
    return rows


def scan_scenario(fh, speaker: str, context: int) -> list[dict]:
    """dummy.bin 전체에서 화자가 speaker 인 줄과 그 앞뒤 문맥을 모은다."""
    needle = kenc(speaker) + b"@"
    hits = []
    pos, CH, prev = 0, 1 << 24, b""
    while pos < DUMMY_SIZE:
        fh.seek(DUMMY + pos)
        d = fh.read(min(CH, DUMMY_SIZE - pos))
        if not d:
            break
        buf = prev + d
        base = pos - len(prev)
        s = 0
        while True:
            i = buf.find(needle, s)
            if i < 0:
                break
            s = i + 1
            # 문자열 시작이어야 화자다 (직전 바이트가 NUL)
            if base + i > 0 and buf[i - 1:i] == b"\x00":
                hits.append(base + i)
        prev = buf[-32:]
        pos += len(d)

    blocks = []
    for h in hits:
        win_start = max(0, h - 0x600)
        fh.seek(DUMMY + win_start)
        win = fh.read(0xC00)
        lines, p = [], 0
        for raw in win.split(b"\x00"):
            off = win_start + p
            p += len(raw) + 1
            if len(raw) < 3:
                continue
            try:
                t = kdec(raw)
            except Exception:
                continue
            if not HANGUL.search(t):
                continue
            lines.append((off, t.replace("　", " ")))
        idx = next((k for k, (o, _) in enumerate(lines) if o == h), None)
        if idx is None:
            continue
        lo, hi = max(0, idx - context), min(len(lines), idx + context + 1)
        blocks.append({"off": h, "focus": idx - lo,
                       "lines": lines[lo:hi]})
    return blocks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", type=Path, default=ISO_DEFAULT)
    ap.add_argument("--out", type=Path,
                    default=Path("reports/APORTABLE_AXEL_DIALOGUE.md"))
    ap.add_argument("--context", type=int, default=3)
    args = ap.parse_args()

    fh = args.iso.open("rb")

    # 한국어 전투대사 청크
    lo, hi = KR_CHUNK_REGION
    fh.seek(DUMMY + lo)
    kr = fh.read(hi - lo)
    kr_chunks = {c["key"]: c for c in find_chunks(kr, AXEL_KEYS)}

    # 일본어 전투대사 청크 (battle.bin 엔트리2)
    fh.seek(BATTLE + 0x800)
    h = fh.read(0x60)
    e2_off, e2_sz = struct.unpack_from("<2I", h, 8 + 2 * 8)
    fh.seek(BATTLE + e2_off)
    jp = fh.read(e2_sz)
    jp_chunks = {}
    for c in find_chunks(jp, AXEL_KEYS):
        jp_chunks.setdefault(c["key"], c)

    md = ["# SRW A Portable [K] — 액셀 대사 전량 추출", "",
          f"원본: `{args.iso.name}`", "",
          "A Portable(PSP)은 OGs(PS2)와 같은 엔진 계열이라 **전투대사 청크 구조가 동일**하다",
          "(헤더 `u16[16]` 의 `[12..15]` = f2/f3/f4/pool, 병렬배열 4개 + 문자열 풀).",
          "원본 아카이브는 일본어이고 **한국어 패치는 `USRDIR/dummy.bin`** 에 들어 있으며,",
          "텍스트 코덱은 OGs 와 동일하다 — 즉 바이트를 거의 그대로 이식할 수 있다.", "",
          "| 항목 | 값 |", "|---|---|",
          f"| dummy.bin ISO 오프셋 | `0x{DUMMY:X}` (크기 `0x{DUMMY_SIZE:X}`) |",
          f"| 한국어 청크 대역 | `0x{lo:X}`~`0x{hi:X}` (dummy.bin 상대) |",
          f"| 일본어 청크 | battle.bin 엔트리2 `0x{e2_off:X}` (크기 `0x{e2_sz:X}`) |",
          ""]

    md.append("## 1. 전투 대사")
    md.append("")
    md.append("`문맥ID`는 무기/상대 식별자, `음성ID`는 A Portable 음성 아카이브 기준값이다.")
    md.append("OGs 로 이식할 때 이 둘은 재매핑이 필요하다(텍스트는 그대로).")
    md.append("")
    for key, label in AXEL_KEYS.items():
        kc, jc = kr_chunks.get(key), jp_chunks.get(key)
        md.append(f"### raw키 `0x{key:03X}` — {label}")
        md.append("")
        if not kc:
            md.append("_한국어 청크를 찾지 못했다._")
            md.append("")
            continue
        krow = read_chunk(kr, kc, kdec)
        jrow = read_chunk(jp, jc, lambda b: b.decode("cp932")) if jc else []
        md.append(f"청크 dummy.bin `0x{lo + kc['off']:X}` · N={kc['n']} · 유효 {len(krow)}줄")
        if jc:
            md.append(f"일본어 대응 battle.bin 엔트리2 `0x{jc['off']:X}` · N={jc['n']} · {len(jrow)}줄")
        md.append("")
        md.append("| # | 문맥ID | 상황 | 음성ID | 한국어 | 일본어 |")
        md.append("|---|---|---|---|---|---|")
        bar = "\\|"
        for k, r in enumerate(krow):
            j = jrow[k]["text"] if k < len(jrow) else ""
            kt = r["text"].replace("|", bar)
            jt = j.replace("|", bar)
            sit = FLAG.get(r["flag"], hex(r["flag"]))
            md.append(f"| {r['i']} | `0x{r['trig']:04X}` | {sit}"
                      f" | `0x{r['vid']:06X}` | {kt} | {jt} |")
        md.append("")

    md.append("## 2. 시나리오 대사 (앞뒤 문맥 포함)")
    md.append("")
    md.append(f"화자가 `액셀` 인 줄을 dummy.bin 전체에서 찾아 앞뒤 {args.context}줄씩 붙였다.")
    md.append("**★** 표시가 액셀 대사다.")
    md.append("")
    blocks = scan_scenario(fh, "액셀", args.context)
    md.append(f"총 {len(blocks)}개 지점.")
    md.append("")
    for b in blocks:
        md.append(f"### dummy.bin `0x{b['off']:X}`")
        md.append("")
        md.append("```")
        for k, (off, t) in enumerate(b["lines"]):
            mark = "★" if k == b["focus"] else "  "
            md.append(f"{mark} 0x{off:07X}  {t}")
        md.append("```")
        md.append("")

    fh.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(md), encoding="utf-8")
    print(f"작성: {args.out}  ({len(md)}줄)")
    print(f"  전투대사 청크: {sorted(hex(k) for k in kr_chunks)}")
    print(f"  시나리오 지점: {len(blocks)}개")


if __name__ == "__main__":
    main()
