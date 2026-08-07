# -*- coding: utf-8 -*-
"""A Portable 액셀 대사를 OGs 전투 슬롯에 **상황을 맞춰** 다시 배치한다.

코덱스 이식본은 `general/damage/defense/weapon` 네 풀을 **순환**해서 넣었다.
그래서 소울게인 무기 슬롯에 알트아이젠 무기 대사(`소드 브레이커`)가 들어가거나,
피격 슬롯에 공격 대사가 들어갔다.

여기서는 두 가지를 근거로 삼는다.

1. **원본 OGs 액셀 대사가 그 슬롯의 정답지다.** 슬롯 순서는 그대로이므로
   (플레이어 청크 slot i ↔ 원본 0x416/0x417 slot i) 원본 문장의 상황을 읽으면
   그 자리가 공격인지 피격인지 회피인지 필살인지 알 수 있다.
2. **무기명은 화면과 맞아야 한다.** OGs 소울게인의 무기는 열화인·수류조아·
   지참질공도뿐이다. `소드 브레이커`(알트아이젠)·`할버드 런처`·`코드 기린`
   ·`광인섬`(라피에사쥬)·`청룡린`류(용호왕)·`매트릭스 미사일`(OGs에 없음)을
   부르는 A Portable 대사는 **버린다**.

같은 원본 문장이 여러 슬롯에 반복되면 같은 A Portable 문장을 배정한다
(원본의 반복 구조를 그대로 살린다).
"""
from __future__ import annotations
import argparse
import json
import re
import struct
from collections import defaultdict
from pathlib import Path

# ── 상황 분류 ────────────────────────────────────────────────────
# 순서가 곧 우선순위다. 먼저 걸리는 것이 그 문장의 상황이다.
RULES = [
    ("silence", (r"^[…・。\s　]*$",)),
    ("crisis", (r"여기까진가", r"여기까지", r"한계", r"물러날", r"이\s*정돈가",
                r"끝인가", r"당하다니", r"뒤쳐진다니", r"이런\s*곳에서")),
    ("hit", (r"^크윽", r"^큭", r"^우욱", r"^으극", r"^윽", r"^아야",
             r"^크아", r"당했", r"실수", r"맞았", r"받아버렸", r"한\s*방\s*먹었",
             r"흔들리는군", r"비명", r"참을\s*수\s*없", r"수리가\s*귀찮",
             r"악수가\s*됐", r"농담이\s*지나치", r"진짜냐", r"어떻게\s*된거야")),
    ("hit_light", (r"장갑", r"스쳤", r"흔들렸을\s*뿐", r"문제없", r"멀쩡",
                   r"아직\s*움직", r"버티나", r"에너지가\s*텅")),
    ("dodge", (r"회피", r"피했", r"빗나", r"사각", r"맞을\s*거\s*같냐",
               r"안\s*통한다", r"소용\s*없", r"가볍게", r"여유", r"아슬아슬",
               r"꽤\s*하잖아", r"세상은\s*마음대로", r"또\s*오라구",
               r"가만있을\s*수는", r"범위\s*밖", r"놓쳐버렸")),
    ("support", (r"원호", r"편승", r"길동무", r"마무리", r"덤이", r"이것도\s*받",
                 r"이것도\s*가져")),
    # "사거리 안이다"는 빗나감이 아니라 사거리에 들어왔다는 공격 대사다.
    # "되는 대로 밖에 안 되나"도 빗나감이 아니다 — A Portable 대응
    # 「될 대로 되는 수밖에 없나」가 **공격 구간**에 있다(실기에서 적발:
    # 현무강탄 문맥 ctx=0x04B5 에 "어라？ 범위 밖인가" 가 들어갔다).
    ("miss", (r"간격으로는\s*무리", r"거리에선\s*무리",
              r"놓쳐", r"범위\s*밖", r"빗나")),
    ("taunt", (r"무르", r"아쉽", r"그\s*정도냐", r"대단하지\s*않", r"고작",
               r"그걸로\s*끝이냐", r"부주의",
               r"과연", r"수법은\s*알았다", r"실력도\s*다르", r"싸울\s*맛")),
    ("fin", (r"끝이다", r"끝장", r"이\s*일격", r"결착", r"우오오", r"데야앗",
             r"파괴해주지", r"부서져라", r"지워주마", r"한계를\s*넘어",
             r"각오하라구", r"리미트\s*해제", r"끝내주마", r"끝내주지",
             r"우오옷", r"이야아", r"우랴아", r"으라챠")),
]
ATTACK = "atk"


def classify(text: str) -> str:
    t = text.replace("@", " ").replace("「", "").replace("」", "")
    for name, pats in RULES:
        for p in pats:
            if re.search(p, t):
                return name
    return ATTACK


# ── 무기명 대응 ──────────────────────────────────────────────────
# ★ 정정: 처음엔 "OGs 소울게인 무기는 열화인/수류조아/지참질공도뿐"이라 보고
# 소드브레이커·할버드런처·매트릭스미사일·청룡린류를 전부 버렸다. **틀렸다.**
# OGs 액셀 자신의 원본 대사에 그 무기 슬롯이 그대로 있다(ctx = 무기ID):
#   0x0351 매트릭스・미사일   0x03F1/0x0401 리니어 캐논
#   0x0421/0x0441 할버드・런처  0x0461/0x0471 소드브레이커
#   0x0491/0x04A1 청룡린      0x04B3/0x04E8 현무강탄
#   0x0622 백호교            0x0741/0x0761 무주작   0x07A1 소울게인 풀 드라이브
# 사용자 지적대로 소드브레이커·할버드런처·매트릭스미사일은 **공용 무기**라
# 파일럿마다 전용 음성이 있다. 버릴 게 아니라 **이름으로 맞춰야** 한다.
#
# 두 게임의 표기가 조금 달라서(할버트/할버드, 소드 브레이커/소드브레이커)
# 정규화 키로 묶는다.
WEAPON_KEYS = {
    "매트릭스": "matrix", "할버트": "halberd", "할버드": "halberd",
    "소드　브레이커": "sword", "소드브레이커": "sword",
    "리니어": "linear", "청룡린": "seiryu", "현무강탄": "genbu",
    "백호교": "byakko", "무주작": "suzaku",
    "코드　기린": "kirin", "코드기린": "kirin",
    # 「기린！ 진・극！！」(麒麟・真極) 도 기린 계열 필살기명이다.
    "진・극": "kirin", "기린！": "kirin",
    "소울게인": "soulgain",
}
# A Portable 에만 있고 OGs 액셀에겐 없는 무기 — 화면과 어긋나므로 쓰지 않는다.
# ("소울　펀치" 는 뺐다 — 사용자 확인: 「로케트・소울 펀치！ 막 이래！」는
#  현무강탄 세트의 **둘째 줄**이라 그 무기 그룹에 속한다.)
AP_ONLY = ("열화인", "수류조", "질공도", "지참", "손톱", "풍인섬", "광인섬",
           "파이널　코드", "비늘포")


# 무기 구간 안에서 "결정타"로 쓸 만한 기합
FIN_RE = re.compile(r"끝장이다|끝이다|이\s*일격|우오랴|이야아|우오옷|으라챠|"
                    r"각오하라구|리미트\s*해제|끝내주|한계를\s*넘어")


def weapon_key(text: str):
    for w, k in WEAPON_KEYS.items():
        if w in text:
            return k
    return None


def weapon_ok(text: str) -> bool:
    if weapon_key(text):
        return True
    return not any(w in text for w in AP_ONLY)


def is_soulgain(text: str) -> bool:
    return weapon_key(text) is not None


# ── 배치 ────────────────────────────────────────────────────────
# 대체 순서: 그 상황이 비면 가까운 상황에서 빌려온다.
FALLBACK = {
    "miss": ["miss", "dodge", "taunt", "hit_light"],
    "support": ["support", "atk", "taunt"],
    "silence": ["silence", "hit_light", "dodge", "atk"],
    "crisis": ["crisis", "hit", "hit_light", "dodge"],
    "hit": ["hit", "crisis", "hit_light", "dodge"],
    "hit_light": ["hit_light", "hit", "dodge", "taunt"],
    "dodge": ["dodge", "taunt", "hit_light", "atk"],
    "taunt": ["taunt", "dodge", "miss", "atk"],
    "fin": ["fin", "atk", "taunt"],
    "atk": ["atk", "fin", "taunt", "dodge"],
}


# A Portable 대사는 **인덱스 구간이 곧 상황**이다(덤프로 확인).
# 키워드로는 "나 원 참、다시 준비하고 오는게 낫다구"(피격)를 공격으로 오분류한다.
AP_SPANS = {
    0xD4: [("atk", range(0, 9)), ("hit", range(9, 23)),
           ("hit_light", range(23, 29)), ("dodge", range(29, 53)),
           ("hit_light", range(53, 55)), ("miss", range(55, 58)),
           ("support", range(58, 64)),
           ("silence", range(64, 68)), ("atk", range(68, 72)),
           ("weapon", range(72, 150))],
    0xD5: [("atk", range(0, 10)), ("hit", range(20, 41)),
           ("hit_light", range(41, 45)), ("dodge", range(45, 87)),
           ("miss", range(87, 98)), ("support", range(98, 104)),
           ("silence", range(104, 108)), ("atk", range(108, 112)),
           ("weapon", range(112, 193))],
}


def _norm(t: str) -> str:
    return t.replace("「", "").replace("」", "").replace("@", "").replace("　", "")


def build_corr(anchor_rows, ap_rows, ap_key: int, cutoff: float = 0.6):
    """OGs 원본 문장 → 상황. **A Portable 0xD5 와의 대응**이 1순위 근거다.

    OGs 액셀 대사와 A Portable `0xD5`(각성 액셀)는 같은 스크립트라
    번역만 다를 뿐 그대로 대응한다. 그러니 대응되는 줄의 **구간**이
    그 슬롯의 상황이다 — 내가 만든 키워드 규칙보다 정확하다.

    실측 사고: `되는 대로 밖에 안 되나`(공격)를 키워드가 "빗나감"으로 봐서
    현무강탄 문맥에 `어라？ 범위 밖인가` 가 들어갔다.
    """
    import difflib
    out = {}
    cand = [(r, _norm(r["text"])) for r in ap_rows if r["voice"]]
    for text in {r["text"] for r in anchor_rows}:
        n = _norm(text)
        best, ratio = None, 0.0
        for r, rn in cand:
            v = difflib.SequenceMatcher(None, n, rn).ratio()
            if v > ratio:
                ratio, best = v, r
        if best is not None and ratio >= cutoff:
            cat = ap_class(best["i"], ap_key)
            out[text] = "atk" if cat == "weapon" else cat
    return out


def ap_class(i: int, key: int) -> str:
    for name, span in AP_SPANS[key]:
        if i in span:
            return name
    return "atk"


def build_map(anchor_rows, ap_rows, available_clips, ap_key, corr=None):
    """원본 문장 → A Portable 문장. 같은 원본은 같은 문장으로 간다."""
    corr = corr or {}
    pools = defaultdict(list)
    for r in ap_rows:
        if not r["voice"]:
            continue
        clip = r["voice"] % 1000
        if r["voice"] // 1000 != 212 or clip not in available_clips:
            continue
        if not weapon_ok(r["text"]):
            continue
        # ★ 무기 이름을 부르는 대사는 **그 무기 슬롯에만** 쓴다.
        # 일반 풀에 넣으면 원본이 "데야앗！！"(단순 기합)이나 대사인 자리에
        # "코드 기린！！" 이 들어간다(실기에서 적발).
        if weapon_key(r["text"]):
            continue
        cat = ap_class(r["i"], ap_key)
        if cat == "weapon":
            # 무기명이 없는 기합 중 결정타로 쓸 만한 것만 필살 자리로.
            cat = "fin" if FIN_RE.search(r["text"]) else "atk"
        pools[cat].append(r)
    if not pools["fin"]:
        pools["fin"] = pools["atk"]

    # 무기명을 부르는 A Portable 대사를 키별로 모아둔다.
    #
    # ★ A Portable 무기 공격은 **두 줄이 한 세트**다. 둘째 줄이 무기명을
    #    안 부르는 경우가 있다 — 사용자 확인: 현무강탄은
    #      109 「날아랏！ 현무강탄！！」 + 110 「로케트・소울 펀치！ 막 이래！」
    #    OGs 도 무기당 슬롯이 2개(현무강탄 = ctx 0x04B3 / 0x04E8)라 짝이 맞는다.
    #    그러니 무기명 줄 바로 뒤의 줄도 **같은 무기 그룹**에 넣는다.
    #    (뒤 줄이 다른 무기를 부르면 그건 별개 세트이므로 넣지 않는다.)
    idx = {r["i"]: r for r in ap_rows}
    ok = lambda r: (r and r["voice"] and r["voice"] // 1000 == 212
                    and r["voice"] % 1000 in available_clips)
    by_weapon = defaultdict(list)
    for r in ap_rows:
        if not ok(r):
            continue
        k = weapon_key(r["text"])
        if not k:
            continue
        by_weapon[k].append(r)
        nxt = idx.get(r["i"] + 1)
        if (ok(nxt) and not weapon_key(nxt["text"])
                and not any(w in nxt["text"] for w in AP_ONLY)):
            by_weapon[k].append(nxt)

    order = defaultdict(int)
    used = set()
    mapping: dict[str, dict] = {}
    for text in [r["text"] for r in anchor_rows]:
        if text in mapping:
            continue
        # 원본이 무기 이름을 부르면, 같은 무기를 부르는 A Portable 대사를 쓴다.
        wk = weapon_key(text)
        if wk:
            pool = by_weapon.get(wk)
            if pool:
                pick = pool[order["w:" + wk] % len(pool)]
                order["w:" + wk] += 1
            else:
                # 대응하는 무기 대사가 없으면 **무기명 없는 짧은 기합**으로 때운다.
                # 일반 풀을 쓰면 이야기 대사가 무기 슬롯에 들어가고
                # (실측: "리니어 캐논！ 가라앗！" → "간다、레몬"),
                # 무기명이 든 걸 쓰면 다른 무기를 외친다.
                pool = [r for r in pools["fin"] + pools["atk"]
                        if not weapon_key(r["text"]) and len(r["text"]) <= 16]
                pool = pool or pools["atk"]
                pick = pool[order["w:none"] % len(pool)]
                order["w:none"] += 1
            used.add(pick["voice"])
            mapping[text] = pick
            continue
        # 대응이 있으면 그쪽을 믿는다. 없을 때만 키워드 규칙.
        want = corr.get(text) or classify(text)
        if classify(text) == "silence":
            want = "silence"
        if want == "silence":
            # 원본이 침묵이면 침묵 그대로 둔다(음성 없음).
            mapping[text] = {"i": -1, "voice": 0, "text": text}
            continue
        pick = None
        for cat in FALLBACK[want]:
            pool = pools.get(cat)
            if not pool:
                continue
            # 아직 안 쓴 것을 먼저, 없으면 순환
            fresh = [r for r in pool if r["voice"] not in used]
            cand = fresh if fresh else pool
            pick = cand[order[cat] % len(cand)]
            order[cat] += 1
            break
        if pick is None:
            raise ValueError(f"배치할 문장이 없다: {want}")
        used.add(pick["voice"])
        mapping[text] = pick
    return mapping, pools


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", type=Path, required=True, help="원본 OGs 청크 json")
    ap.add_argument("--ap", type=Path, required=True, help="A Portable 청크 json")
    ap.add_argument("--manifest", type=Path,
                    default=Path("runtime/aportable_voice_port.json"))
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--ap-key", type=lambda v: int(v, 0), required=True)
    args = ap.parse_args()

    anchor = json.loads(args.anchor.read_text(encoding="utf-8"))
    aprows = json.loads(args.ap.read_text(encoding="utf-8"))
    clips = {int(k) for k in json.loads(
        args.manifest.read_text(encoding="utf-8"))["clip_slots"]}

    mapping, pools = build_map(anchor, aprows, clips, args.ap_key)
    print("A Portable 사용 가능 풀:",
          {k: len(v) for k, v in sorted(pools.items())})
    from collections import Counter
    print("슬롯 상황 분포:",
          dict(Counter(classify(r["text"]) for r in anchor)))

    out = []
    for r in anchor:
        pick = mapping[r["text"]]
        out.append({"i": r["i"], "ctx": r["ctx"], "flag": r["flag"],
                    "orig": r["text"], "ap_i": pick["i"],
                    "voice": pick["voice"], "text": pick["text"]})
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"배치 {len(out)}슬롯 / 고유 문장 {len({o['text'] for o in out})}"
          f" → {args.output}")


if __name__ == "__main__":
    main()
