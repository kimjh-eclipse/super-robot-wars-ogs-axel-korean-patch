# -*- coding: utf-8 -*-
"""배치안을 만들고 뱅크 용량에 맞게 줄인다.

용량은 descriptor 개수(194)가 아니라 **STRM 바이트**(0x88A800)가 한계다.
추정식이 실제 인코딩보다 4%쯤 작게 나오므로 예산을 0x800000 으로 잡는다.

주의 두 가지 — 둘 다 실기에서 적발된 사고다.
  · 무기 이름을 부르는 대사는 **그 무기 슬롯에만** 쓴다(place_axel_battle_lines).
  · 클립을 줄일 때도 **대체 순서(FALLBACK)를 지켜야** 한다. 그냥 atk 로 떨어뜨리면
    "에에이、여기까진가！"(위기) 자리에 "이 녀석에게선 벗어날 수 없어！"(공격)가 들어간다.
"""
from __future__ import annotations
import json
import math
from collections import Counter
from pathlib import Path

import place_axel_battle_lines as PL
import port_aportable_axel_voice as P

AP = Path("C:/Emul/PSP/Super Robot Wars A Portable [K].iso")
# 기체 선택 전용 슬롯(extend_machine_lines)이 무기명 대사용으로 신규 클립을
# 몇 개 더 쓴다. 그 자리를 미리 떼어 두지 않으면 재패킹에서 넘친다
# (실측 8,996,864 > 8,955,904).
RESERVE = 0xC0000
BUDGET = 0x800000 - RESERVE
CAP = 194

res = {}
corr_all = {}
for key, anchor, ap, k in ((0x416, "orig416", "apD4", 0xD4),
                           (0x417, "orig417", "apD5", 0xD5)):
    a = json.loads(Path(f"runtime/{anchor}.json").read_text(encoding="utf-8"))
    p = json.loads(Path(f"runtime/{ap}.json").read_text(encoding="utf-8"))
    # A Portable 0xD5 는 OGs 액셀과 같은 스크립트라 상황 판정의 근거가 된다.
    ref = json.loads(Path("runtime/apD5.json").read_text(encoding="utf-8"))
    corr = PL.build_corr(a, ref, 0xD5)
    m, pool = PL.build_map(a, p, set(range(1000)), k, corr)
    print(f"  대응으로 판정 {len(corr)} / 고유문장 {len({r['text'] for r in a})}")
    corr_all.update(corr)
    res[key] = (a, m, pool)
    print(f"0x{key:X} 풀", {kk: len(v) for kk, v in sorted(pool.items())})

_size = {}


def clipsize(c: int) -> int:
    if c not in _size:
        s = P.riff_samples(P.a_riff(AP, c))
        o = math.ceil(s * 32000 / 44100)
        _size[c] = P.align(0x810 + math.ceil(o / 28) * 16, 0x800)
    return _size[c]


def used() -> Counter:
    cnt = Counter()
    for a, m, _ in res.values():
        for r in a:
            v = m[r["text"]]["voice"]
            if v:
                cnt[v % 1000] += 1
    return cnt


def alt_pool(pool, cat, have, drop):
    """대체 순서를 지켜서 후보를 고른다."""
    for c in PL.FALLBACK.get(cat, [cat]):
        cand = [r for r in pool.get(c, [])
                if r["voice"] and r["voice"] % 1000 in have
                and r["voice"] % 1000 != drop]
        if cand:
            return cand
    return []


c = used()
total = sum(clipsize(x) for x in c)
guard = 0
while (total > BUDGET or len(c) > CAP) and guard < 120:
    guard += 1
    cand = {}
    for key, (a, m, pool) in res.items():
        for txt, pick in m.items():
            if not pick["voice"] or PL.weapon_key(txt):
                continue
            cand.setdefault(pick["voice"] % 1000, []).append((key, txt))
    if not cand:
        break
    drop = max(cand, key=lambda x: clipsize(x) / max(c[x], 1))
    moved = False
    for key, txt in cand[drop]:
        a, m, pool = res[key]
        pick = alt_pool(pool, corr_all.get(txt) or PL.classify(txt), set(c), drop)
        if pick:
            m[txt] = max(pick, key=lambda r: c[r["voice"] % 1000])
            moved = True
    if not moved:
        break
    c = used()
    total = sum(clipsize(x) for x in c)

print(f"클립 {len(c)}/{CAP}  추정 0x{total:X} / 예산 0x{BUDGET:X}")
leak = 0
for key, (a, m, _) in res.items():
    out = []
    for r in a:
        pick = m[r["text"]]
        if PL.weapon_key(pick["text"]) and not PL.weapon_key(r["text"]):
            leak += 1
        out.append({"i": r["i"], "ctx": r["ctx"], "flag": r["flag"],
                    "orig": r["text"], "ap_i": pick["i"],
                    "voice": pick["voice"], "text": pick["text"]})
    Path(f"runtime/place{key:X}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"0x{key:X} {len(out)}슬롯 고유문장 "
          f"{len({o['text'] for o in out})}")
print(f"무기명 유출 {leak}건")
