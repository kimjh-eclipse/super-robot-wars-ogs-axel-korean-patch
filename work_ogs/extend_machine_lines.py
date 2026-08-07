# -*- coding: utf-8 -*-
"""기체 선택(바이사가·아슈세이버·라즈앙그리프·소울게인개) 전투대사를 되살린다.

사용자 지적(2026-08-07):
  OGs 중반부터 플레이어는 기체를 고를 수 있고 기체마다 전용 대사가 있다.
  라미아 청크에는 그게 다 들어 있는데, 내용 교환이 액셀 청크(266/231줄)만
  복사하면서 **넘치는 슬롯을 잘라버렸다.** 그래서 다른 기체를 타면 전용 대사가 없다.

되살리는 방법:
  플레이어 청크의 비어 있는 슬롯(f2=0)에 **라미아 원본의 기체 무기 문맥**을
  f1/f2 째로 되돌리고, 거기에 A Portable 액셀 대사를 붙인다.

  · 기체 무기 문맥 판정 = 라미아 원본에서 무기·기체 이름을 부르는 레코드의 ctx.
    같은 ctx 를 쓰는 레코드를 통째로 가져온다(무기당 슬롯이 여러 개다).
  · 액셀이 이미 쓰는 ctx 는 건드리지 않는다(소울게인 쪽이 깨진다).

A Portable 액셀이 가진 것과 없는 것:
  바이사가   「풍인섬！」「이것이 오의・광인섬…막 이래！」            → 있음
  아슈세이버 할버드 런처·소드브레이커(공용 무기)                    → 있음
  라즈앙그리프 리볼빙 스테이크·벙커·트윈 빔 캐논                    → **없음**
  안쥬르그   미라쥬 소드·일루젼 애로우·팬텀 피닉스                 → **없음**
없는 것은 무기명 없는 기합으로 채운다(다른 기체 무기를 외치는 것보다 낫다).
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

import place_axel_battle_lines as PL

# 라미아 원본에서 "이건 기체 무기 대사다" 를 알려주는 낱말
WEAPON_WORD = re.compile(
    "미라쥬|섀도우|일루젼|팬텀|정령|풍인섬|광인섬|바이사가|안쥬르그|"
    "아슈세이버|라즈앙그리프|스테이크|벙커|클레이모어|트윈|빔캐논|빔　캐논|"
    "블라스터|임팩트|솔리드|런처|캐논|소드브레이커|할버드")

# 라미아 원본 무기명 → A Portable 무기 키
LAMIA_TO_AP = {
    "풍인섬": "fujinsen", "광인섬": "koujinsen",
    "할버드": "halberd", "소드브레이커": "sword",
}
# A Portable 쪽 키(기존 WEAPON_KEYS 에 없는 바이사가 무기를 따로 잡는다)
AP_EXTRA = {"풍인섬": "fujinsen", "광인섬": "koujinsen"}

PAIRS = (("3F4", "416"), ("4A4", "416"), ("4A5", "417"), ("521", "417"))

# 바이사가 무장은 열화인 → (손톱) → 수류조 → 지참·질공도 → 풍인섬 → 오의・광인섬 순이다.
# A Portable 액셀에는 앞쪽 셋도 있는데, OGs 라미아 대사는 그 자리에서 무기 이름을
# 부르지 않는다(「받아라…！」「간다！」). 그래서 무기명 검색으로는 안 잡힌다.
#
# 라미아 청크를 ctx 순으로 보면 기체별로 뭉쳐 있다(실측 0x3F4):
#   0x00B1~0x00B6 안쥬르그(일루젼·팬텀) → 0x00BA~0x00C0 이름 없음 → 0x00C1 풍인섬
# 즉 **풍인섬 직전의 무기명 없는 슬롯들이 바이사가의 앞쪽 무장**이다.
VAISAGA_ANCHOR = re.compile("풍인섬|광인섬|바이사가")
VAISAGA_AP = re.compile("열화인|수류조|질공도|손톱|지참")
# 다른 기체의 무장 이름 — 역방향 탐색을 여기서 멈춘다
OTHER_MACHINE = re.compile(
    "미라쥬|섀도우|일루젼|팬텀|정령|안쥬르그|아슈세이버|라즈앙그리프|스테이크|"
    "벙커|클레이모어|트윈|빔캐논|빔　캐논|블라스터|임팩트|솔리드|런처|캐논|"
    "소드브레이커|할버드|매트릭스")


def vaisaga_slots(lam):
    """풍인섬 직전의 무기명 없는 슬롯을 **배열 인덱스 순**으로 돌려준다.

    0x3F4 은 ctx 가 기체별로 오름차순이라 ctx 순서로도 됐지만, 0x4A4·0x4A5 는
    ctx 를 0 으로 두는 슬롯이 섞여 있어 ctx 정렬이 무너진다. 네 청크 모두
    **배열 순서**는 같은 문장 차례(간다！ → 받아라！ → 가랏！ → 이　공격을…
    → 풍인섬！)를 유지하므로 인덱스를 기준으로 삼는다.
    """
    rows = sorted(lam, key=lambda r: r["i"])
    # 앵커는 **풍인섬**이어야 한다. 「바람처럼　춤춘다…　그것이　바이사가다」 같은
    # 기체 소개 대사는 무장 블록에서 멀리 떨어져 있어(실측 0x4A5) 앵커로 쓰면
    # 역방향 탐색이 엉뚱한 데서 시작해 곧바로 다른 기체에 막힌다.
    first = next((i for i, r in enumerate(rows) if "풍인섬" in r["text"]), None)
    if first is None:
        return []
    out = []
    for r in reversed(rows[:first]):
        if OTHER_MACHINE.search(r["text"]) or VAISAGA_ANCHOR.search(r["text"]):
            break
        out.append(r)
    return list(reversed(out))


def ap_weapon_key(text: str):
    for w, k in AP_EXTRA.items():
        if w in text:
            return k
    return PL.weapon_key(text)


def lamia_weapon_key(text: str):
    for w, k in LAMIA_TO_AP.items():
        if w in text:
            return k
    return PL.weapon_key(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path,
                    default=Path("runtime/machine_extra.json"))
    args = ap.parse_args()

    apd = {k: json.loads(Path(f"runtime/ap{k}.json").read_text(encoding="utf-8"))
           for k in ("D4", "D5")}
    out = {}
    for pk, ak in PAIRS:
        lam = json.loads(Path(f"runtime/orig{pk}.json").read_text(encoding="utf-8"))
        axel = json.loads(Path(f"runtime/orig{ak}.json").read_text(encoding="utf-8"))
        aprows = apd["D4" if ak == "416" else "D5"]
        # 슬롯 구분자는 ctx 단독이 아니라 **(ctx, 플래그) 쌍**이다.
        # ctx 만으로 걸렀더니 라미아 풍인섬(0x00C1/0x7000)이 액셀의
        # 0x00C1/0x0000 과 같은 ctx 라는 이유로 통째로 버려졌다(실측 0x3F4).
        axctx = {(r["ctx"], r["flag"]) for r in axel}

        # 기체 무기 문맥 = 무기명을 부르는 라미아 레코드의 ctx.
        # 단, `0x0100`·`0x0208`·`0x0441` 처럼 **여러 레코드가 공유하는 ctx 는
        # 무기ID가 아니라 범용 조건 코드**다(실측: 0x0100 에 39개). 그걸 끌어오면
        # 관계없는 대사까지 딸려온다. 레코드가 4개 이하인 희소 ctx 만 무기로 본다.
        from collections import Counter
        cnt = Counter(r["ctx"] for r in lam)
        wctx = {r["ctx"] for r in lam
                if WEAPON_WORD.search(r["text"]) and r["ctx"]
                and (r["ctx"], r["flag"]) not in axctx and cnt[r["ctx"]] <= 4}
        extra = [r for r in lam if r["ctx"] in wctx and r["text"] != "<범위밖>"
                 and (r["ctx"], r["flag"]) not in axctx]

        # 바이사가 앞쪽 무장 자리 — 라미아 대사가 무기명을 안 부르는 구간
        # 인덱스 탐색은 범용 조건 코드(0x0100 등, 레코드 16~39개)까지 지나간다.
        # 거기에 무기명을 넣으면 온갖 상황에서 「지참！　질공도！」가 튀어나온다.
        # 무기 슬롯 판정은 여기서도 **희소 ctx**로 제한한다.
        vs = [r for r in vaisaga_slots(lam)
              if (r["ctx"], r["flag"]) not in axctx
              and r["ctx"] not in wctx and r["text"] != "<범위밖>"
              and r["ctx"] and cnt[r["ctx"]] <= 4]
        vap, seen_v = [], set()
        for r in aprows:
            if r["voice"] and VAISAGA_AP.search(r["text"]) and r["voice"] not in seen_v:
                seen_v.add(r["voice"]); vap.append(r)
        # 역방향 탐색은 앞 기체의 꼬리까지 딸려온다. 실측 0x3F4 의 0x00B8
        # 「조준은　안빗나가！」는 안쥬르그 블록의 0x00AF 와 같은 문장이다.
        # 그래서 **풍인섬에 가장 가까운 쪽부터** 무장 수만큼만 쓴다.
        # 슬롯이 모자라면 **풍인섬에 가까운 무장부터** 남긴다.
        n = min(len(vs), len(vap))
        vs, vap = vs[-n:], vap[-n:]
        vmap = {}
        for r, pick in zip(vs, vap):
            vmap[(r["ctx"], r["flag"])] = pick
        extra = sorted(extra + [r for r in vs if (r["ctx"], r["flag"]) in vmap],
                       key=lambda r: (r["ctx"], r["flag"]))

        # A Portable 쪽 무기별 대사 (짝 포함)
        idx = {r["i"]: r for r in aprows}
        by_w = {}
        for r in aprows:
            if not r["voice"]:
                continue
            k = ap_weapon_key(r["text"])
            if not k:
                continue
            by_w.setdefault(k, []).append(r)
            nxt = idx.get(r["i"] + 1)
            if (nxt and nxt["voice"] and not ap_weapon_key(nxt["text"])
                    and not any(w in nxt["text"] for w in PL.AP_ONLY)):
                by_w.setdefault(k, []).append(nxt)

        # 무기명 없는 짧은 기합 (대응 없는 무기 슬롯용)
        shouts = [r for r in aprows
                  if r["voice"] and not ap_weapon_key(r["text"])
                  and not any(w in r["text"] for w in PL.AP_ONLY)
                  and len(r["text"]) <= 16
                  and PL.ap_class(r["i"], 0xD4 if ak == "416" else 0xD5)
                  in ("weapon", "atk")]

        # 무기 대응이 없는 슬롯은 **상황**으로 고른다(무작정 순환하면
        # "회피행동…！" 자리에 "거기냐…！"(공격) 가 들어간다).
        ref = json.loads(Path("runtime/apD5.json").read_text(encoding="utf-8"))
        corr = PL.build_corr(extra, ref, 0xD5)
        bycat = {}
        for r in aprows:
            if not r["voice"] or ap_weapon_key(r["text"]):
                continue
            if any(w in r["text"] for w in PL.AP_ONLY):
                continue
            c = PL.ap_class(r["i"], 0xD4 if ak == "416" else 0xD5)
            bycat.setdefault("atk" if c == "weapon" else c, []).append(r)

        # 같은 청크 안에서 같은 대사를 두 번 쓰지 않는다. 풀을 그냥 돌리면
        # 「맞아　줘야겠어！」가 한 청크에 두 번 나온다(실측 0x4A4).
        # 후보가 동나면 그때만 재사용을 허용한다.
        used: set[int] = set()

        # 음성은 bank 1046 의 **고정 바이트 공간**(0x88A800)에 다시 채워 넣는다.
        # 새 클립을 늘리면 바로 넘친다(실측 8,996,864 > 8,955,904). 그래서
        # 본 배치가 이미 쓰는 클립을 우선 고른다 — 재사용은 공짜다.
        free = {r["voice"] for name in ("place416", "place417")
                for r in json.loads(Path(f"runtime/{name}.json")
                                    .read_text(encoding="utf-8")) if r["voice"]}

        def take(pool, cheap_ok=True):
            """cheap_ok=False 는 무기명 풀. 여기서 재사용을 우선하면
            「풍인섬！」 대신 짝 대사가 뽑혀 무기명이 사라진다."""
            fresh = [x for x in pool if x["voice"] not in used]
            if not cheap_ok:
                return fresh or pool
            cheap = [x for x in fresh if x["voice"] in free]
            return cheap or fresh or pool

        rows, order = [], {}
        for r in extra:
            fixed = vmap.get((r["ctx"], r["flag"]))
            if fixed:
                used.add(fixed["voice"])
                rows.append({"ctx": r["ctx"], "flag": r["flag"], "orig": r["text"],
                             "voice": fixed["voice"], "text": fixed["text"]})
                continue
            k = lamia_weapon_key(r["text"])
            pool = by_w.get(k) if k else None
            if pool:
                pass
            elif WEAPON_WORD.search(r["text"]) or r["flag"] == 0x7000:
                # 무기 자리인데 대응 대사가 없으면 **짧은 기합**만 쓴다.
                # 일반 풀을 쓰면 "발사！！" 자리에 "간다、레몬" 같은
                # 이야기 대사가 들어간다(실측).
                pool, k = shouts, "shout"
            else:
                cat = corr.get(r["text"]) or PL.classify(r["text"])
                for c in PL.FALLBACK.get(cat, [cat]):
                    if bycat.get(c):
                        pool, k = bycat[c], "c:" + c
                        break
                else:
                    pool, k = shouts, "shout"
            cand = take(pool, cheap_ok=not str(k).isalpha() or k in ("shout",)
                        or k.startswith("c:"))
            pick = cand[order.get(k, 0) % len(cand)]
            used.add(pick["voice"])
            order[k] = order.get(k, 0) + 1
            rows.append({"ctx": r["ctx"], "flag": r["flag"], "orig": r["text"],
                         "voice": pick["voice"], "text": pick["text"]})
        out[pk] = rows
        named = sum(1 for x in rows if ap_weapon_key(x["text"]))
        print(f"0x{pk}: 문맥 {len(wctx):3}개 / 레코드 {len(rows):3}개 "
              f"(무기명 일치 {named})")

    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"→ {args.output}")


if __name__ == "__main__":
    main()
