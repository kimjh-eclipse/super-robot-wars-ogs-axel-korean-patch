# -*- coding: utf-8 -*-
"""역할 교환 대사 초안을 규칙으로 생성하고, 판단이 필요한 것만 따로 뽑는다.

근거: HANDOFF_EVENT_AND_PILOT_SWAP_2026-08-02.md §5-K

  6화~여러 구간을 손으로 처리하며 확인한 사실:
    · 고유명 치환은 기계적으로 안전하다(오탐 목록만 지키면).
    · 라미아 화자 대사는 말투 규칙으로 대부분 액셀 화법이 된다.
    · **성별 전제·타인 지칭은 자동으로 못 가린다** — 반드시 사람이 읽어야 한다.

  그래서 이 도구는 판정을 대신하지 않고 **둘로 나눈다**:
    auto   … 화자 라벨 + 고유명 + 말투 규칙만으로 끝나는 것
    manual … 지시(그녀/언니/여자…)·화법·양쪽 이름 동시 등장·성별 어휘가 걸린 것

길이 제약(레코드 ≤ 원본 바이트)은 전각공백→말줄임 순으로 상쇄하되,
**상쇄가 어색해질 수 있으므로 상쇄가 일어난 줄은 별도 표시**해 검토 대상에 넣는다.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from ogs_korean_codec import encode

# ── 고유명 (양방향) ───────────────────────────────────────────────
NAME_SWAP = {
    "라미아": "액셀", "액셀": "라미아",
    "러브레스": "알마", "알마": "러브레스",
    "안쥬르그": "소울게인", "소울게인": "안쥬르그",
    "ＳＭＳＣ": "ＥＧ－Ｘ", "ＥＧ－Ｘ": "ＳＭＳＣ",
    "Ｗ１７": "액셀",          # 사용자 판단(2026-08-07). Ｗ１６ 은 에키드나 코드라 유지
}
# "액셀렌"(= 엑셀렌 브라우닝의 이표기. 패치 안에 엑셀렌 2839 / 액셀렌 31)은
# 액셀과 무관한 다른 인물이다. 접두 일치로 "라미아렌" 이 되는 사고를 막는다.
# "액셀렌"(엑셀렌 이표기)과 "액셀레이션"(acceleration, 슬레이 필살기명)은
# 액셀과 무관하다. 접두 일치로 "라미아렌"·"라미아레이션" 이 되는 사고를 막는다.
NAME_RE = re.compile("|".join(sorted(NAME_SWAP, key=len, reverse=True))
                     .replace("액셀", "액셀(?!렌|레이션|러)"))

# 받침 유무 — 이름이 바뀌면 뒤따르는 조사도 함께 바뀌어야 한다.
#   라미아(모음) 와/는/가/를/라  ↔  액셀(받침 ㄹ) 과/은/이/을/이라
HAS_JONG = {"액셀": True, "라미아": False, "소울게인": True, "안쥬르그": False,
            "알마": False, "러브레스": True, "ＥＧ－Ｘ": True, "ＳＭＳＣ": True}
# (받침용, 모음용)
# 긴 것을 먼저 봐야 한다. ("이","가") 가 먼저 걸리면
# "액셀이란" → "라미아가란" 같은 비문이 나온다(실측).
PARTICLES = [("이라고", "라고"), ("이라는", "라는"), ("이란", "란"),
             ("이라", "라"), ("이여", "여"), ("이랑", "랑"), ("으로", "로"),
             ("이었", "였"), ("이야", "야"),
             ("과", "와"), ("은", "는"), ("을", "를"), ("이", "가")]


def fix_particle(name: str, tail: str) -> str:
    """이름 바로 뒤 조사를 새 이름의 받침에 맞춘다."""
    jong = HAS_JONG.get(name)
    if jong is None or not tail:
        return tail
    for withj, without in PARTICLES:
        want, other = (withj, without) if jong else (without, withj)
        if tail.startswith(other) and not tail.startswith(want):
            return want + tail[len(other):]
        if tail.startswith(want):
            return tail
    return tail


def swap_names_with_particles(text: str) -> str:
    out = []
    i = 0
    while i < len(text):
        m = NAME_RE.match(text, i)
        if not m:
            out.append(text[i]); i += 1; continue
        src = m.group(); dst = NAME_SWAP[src]
        i = m.end()
        tail = fix_particle(dst, text[i:])
        # 조사가 바뀌었으면 원문 쪽 조사를 소비한 만큼 건너뛴다
        consumed = len(text) - i - (len(tail) - (len(text) - i)) if tail else 0
        out.append(dst)
        # tail 을 통째로 다시 처리해야 하므로 text 를 재구성
        text = "".join(out) + tail
        i = len("".join(out))
        out = [text[:i]]
    return "".join(out)

# ── 라미아 말투 → 액셀 말투 (화자가 라미아일 때만) ────────────────
# 긴 것부터 적용해야 짧은 규칙이 먼저 먹는 사고를 막는다.
STYLE_RULES = [
    ("란　거랍니다에요", "란　말이지"), ("란거랍니다에요", "란　말이지"),
    ("거랍니다에요", "단　말이지"), ("거랍니다", "단　말이지"),
    ("랍니다인거에요", "단　말이지"), ("랍니다인거죠", "단　말이지"),
    ("입니다인거죠에요", "단　말이지"), ("합니다인거죠", "단　말이지"),
    ("습니다에요", "단　말이지"), ("입니다에요", "단　말이지"),
    ("합니다예요", "단　말이지"), ("습니다예요", "단　말이지"),
    ("인거에요", "단　말이지"), ("인거죠", "단　말이지"),
    ("랍니다", "단　말이지"), ("습니다만", "지만"),
    ("하십니까", "하나"), ("이십니까", "인가"), ("십니까", "나"),
    ("습니까", "나"), ("입니까", "인가"),
    ("엑세언니", "엑세누님"), ("엑세　언니", "엑세　누님"),
    ("호호호호", "하하하하"), ("오호호호", "하하하하"),
    ("호호호", "하하하"), ("우후후", "후후"),
    ("저는", "난"), ("저도", "나도"), ("저희", "우리"),
    ("제가", "내가"), ("저에게", "내게"),
    # ("제　","내　") 는 쓰면 안 된다 — "무장해제　해라"→"무장해내　해라",
    # "이제　끝내는건가"→"이내　끝내는건가" 처럼 어중을 때린다(실측 5건 오염).
    # 실사용에서 남았던 것들 보강
    ("하겠단　겁니다", "하겠단　말이지"), ("겁니다", "거란　말이지"),
    ("거나해버리고", "하고"), ("해버리고", "하고"),
    ("거나합니다", "한단　말이지"), ("하거나", "하고"),
    ("있는겁니다예요", "있단　말이지"), ("있습니다", "있다"),
    ("인데요", ""), ("이잖아요", "잖나"), ("잖아요", "잖나"),
    ("에요", "야"), ("예요", "야"),
    ("아뇨", "아니"), ("네에", "아아"),
    # ── 레몬 보고 장면: 라미아는 경어, 액셀은 반말 ──
    ("레몬님께서", "레몬、네가"), ("레몬님도", "레몬도"),
    ("레몬님과", "레몬과"), ("레몬님、", "레몬、"), ("레몬님", "레몬"),
    ("당신께서", "네가"), ("당신께", "네게"), ("께서", "가"),
    ("말씀하시는", "말하는"), ("말씀이십니까", "말인가"), ("말씀", "말"),
    ("해버리시는", "하는"), ("하시는", "하는"), ("셔주세요", "해라"),
    ("주셨습니다", "줬어"), ("주십시오", "해라"),
    # 어미 — **안전한 형태만**. 일반 "습니다/입니다" 는 규칙으로 바꾸면
    # "고맙어" "뿐야" "같어" 처럼 비문이 된다(실측). 그런 줄은 사람이 쓴다.
    ("있습니다", "있어"), ("없습니다", "없어"),
    ("알겠습니다", "알겠어"), ("하겠습니다", "하겠어"),
    ("모르겠습니다", "모르겠어"), ("되었습니다", "됐어"),
    # 1인칭
    ("저를", "날"), ("제게", "내게"), ("저에게", "내게"),
    ("전　", "난　"), ("저、", "나、"), ("저……", "나……"),
    # 라미아 특유 어미 잔재 — 단독으로 안전한 것만
    ("던가말던가", "든지"), ("라던가하던가", "라던가"),
]

# 반복되는 정형 대사 — 이름만 바꾸면 안 되고 상대역의 대사로 통째 교체한다.
LINE_SWAP = {
    "라미아：떨어지는…가。이런곳에서…！": "액셀：큭！@여기까진가…！！",
    "액셀：큭！@여기까진가…！！": "라미아：떨어지는…가！",
    "라미아：탈출하겠단　겁니다…@크…！　꼴　사납군…":
        "액셀：탈출하겠단　말이지…@크…！　꼴　사납군…",
}

# 말투 규칙을 돌린 뒤에도 이게 남아 있으면 라미아 어투가 살아있는 것 —
# 액셀이 라미아처럼 말하게 되므로 자동 적용하지 않고 사람에게 넘긴다.
QUIRK_MARKERS = ("거에요", "거예요", "인거", "해버리",
                 "거나하", "던가하", "하던가", "지요",
                 "잖아요", "세요", "에요", "예요", "데요", "니깐요",
                 # 경어 잔재 — 액셀은 레몬·소령에게도 반말/평어다
                 "까요", "어요", "아요", "드려", "셨", "시겠", "으세",
                 # 라미아 특유의 "~거나 ~거나" 가 부분 치환돼 남은 꼴
                 "하고　하지", "거나　하지", "고　하지",
                 # 액셀은 Ｗ넘버즈가 아니다 — 자칭이 남으면 내용을 다시 써야 한다
                 "Ｗ넘버")


def has_hapnida(text: str) -> bool:
    """습니다/입니다/합니다/랍니다… = 종성 ㅂ + "니다". "아니다"는 걸리지 않는다."""
    for i in range(len(text) - 2):
        if text[i + 1:i + 3] != "니다":
            continue
        c = text[i]
        if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 == 17:   # 종성 ㅂ
            return True
    return False


# 규칙이 서로 겹쳐서 만들어내는 비문 — 나오면 사람에게 넘긴다.
# (실측: "잘 알겠어란 단 말이지", "죄송합니다가 됐어")
BROKEN_PATTERNS = ("란　단", "어란", "야란", "가　됐어", "가　되었",
                   "고맙어", "뿐야", "같어", "야야", "인가야", "해　단",
                   "단　단", "말이지란", "지야", "어어")

# ── 수동 검토가 필요한 신호 ───────────────────────────────────────
REF_WORDS = ("그녀", "여자", "여성", "아가씨", "소녀", "누나", "언니",
             "짱", "찡", "미녀", "미인", "글래머", "가슴", "몸매", "예쁘", "귀엽")
STYLE_WORDS = ("화법", "말투", "요상", "유행", "말버릇", "사투리")
SPEAKER_RE = re.compile(r"^([^：（(]{1,12})[：（(]")


def swap_names(text: str) -> str:
    return swap_names_with_particles(text)


def apply_style(text: str) -> str:
    for a, b in STYLE_RULES:
        text = text.replace(a, b)
    return text


# 상쇄는 **티가 덜 나는 자리부터** 지운다. 아무 공백이나 지우면
# "안 일어난다이건가" 처럼 단어가 붙어버려 게임에서 바로 눈에 띈다.
# 축약 사다리 — 레코드가 상한을 넘을 때만, 넘는 만큼만 순서대로 적용한다.
# 원인의 대부분은 "액셀"(2자) → "라미아"(3자) 로 화자명이 +2B 늘어나는 것이다.
# 모두 뜻이 그대로인 구어 축약이라 문장이 깨지지 않는다(어절을 붙이지 않는다).
SHORTEN_STEPS = [
    ("해　버리", "해버리"), ("해　버렸", "해버렸"), ("고　말았", "고말았"),
    ("그렇다면", "그럼"), ("무엇을", "뭘"), ("무엇이", "뭐가"), ("무엇", "뭐"),
    ("그것은", "그건"), ("이것은", "이건"), ("저것은", "저건"),
    ("그것을", "그걸"), ("이것을", "이걸"), ("저것을", "저걸"),
    ("그것이", "그게"), ("이것이", "이게"), ("저것이", "저게"),
    ("것이다", "거다"), ("것인가", "건가"), ("것이야", "거야"),
    ("것은", "건"), ("것을", "걸"), ("것이", "게"),
    ("에서는", "에선"), ("에게는", "에겐"), ("해서는", "해선"),
    ("으로는", "으론"), ("말이야", "말야"),
    ("되어", "돼"), ("되었", "됐"),
    ("그러니까", "그러니"), ("어째서", "왜"), ("어찌해서", "왜"),
    ("그　중", "그중"), ("이　때", "이때"), ("그　때", "그때"),
    ("한　번", "한번"), ("두　번", "두번"), ("하고　있", "하고있"),
    ("그렇지만", "하지만"),
]

# 어감이 바뀌는 축약 — 말줄임을 지우는 것보다도 뒤에 둔다.
LAST_SHORTEN = [("그러나", "허나"), ("하지만", "허나")]

# 정말 마지막 수단: 구두점·줄머리에 붙은 말줄임 하나를 지운다.
# 뜻은 그대로고 어절이 붙지 않는다. 그래도 어감이 약해지므로 맨 끝에 둔다.
ELLIPSIS_SPOTS = [("：…", "："), ("（…", "（"), ("。…", "。"), ("、…", "、"),
                  ("！…", "！"), ("？…", "？"), ("@…", "@"), ("…@", "@")]
# 어중에 걸리면 뜻이 바뀌는 것들("일어나는"→"일어난", "하나를"→"하날")은
# 어절 첫머리에서만 줄인다. "지 않"→"잖" 은 부정을 뒤집어서 아예 뺐다.
SHORTEN_ANCHORED = [
    ("나는", "난"), ("너는", "넌"), ("나를", "날"), ("너를", "널"),
]
_BOUND = "　@：（(」』、。？！…"

TRIM_STEPS = [
    ("　　", "　"),                                   # 중복 공백
    ("。　", "。"), ("、　", "、"), ("？　", "？"), ("！　", "！"),
    ("…　", "…"), ("　…", "…"),
    ("……", "…"), ("…。", "…"), ("。@", "@"),
    ("　@", "@"),                                      # 줄바꿈 직전 공백
]


def trim_to_fit(text: str, limit: int) -> tuple[str, bool]:
    """길이 초과분을 자연스러운 순서로 줄인다. 마지막 수단이 일반 공백."""
    if len(encode(text)) <= limit:
        return text, False
    orig = text
    for a, b in TRIM_STEPS:
        while len(encode(text)) > limit and a in text:
            i = text.rfind(a)
            text = text[:i] + b + text[i + len(a):]
    # 구두점 정리로 부족하면 뜻이 같은 구어 축약을 넘는 만큼만 적용한다.
    for a, b in SHORTEN_STEPS:
        while len(encode(text)) > limit and a in text:
            i = text.rfind(a)
            text = text[:i] + b + text[i + len(a):]
    for a, b in SHORTEN_ANCHORED:
        while len(encode(text)) > limit:
            i = -1
            for j in range(len(text) - len(a), -1, -1):
                if text[j:j + len(a)] == a and (j == 0 or text[j - 1] in _BOUND):
                    i = j
                    break
            if i < 0:
                break
            text = text[:i] + b + text[i + len(a):]
    for a, b in ELLIPSIS_SPOTS:
        while len(encode(text)) > limit and a in text:
            i = text.rfind(a)
            text = text[:i] + b + text[i + len(a):]
    for a, b in LAST_SHORTEN:
        while len(encode(text)) > limit and a in text:
            i = text.rfind(a)
            text = text[:i] + b + text[i + len(a):]
    # 여기서 더 줄이려면 단어가 붙어버린다("되게여유있군"). 자동화하지 않고
    # 사람에게 넘긴다 — 게임에서 바로 눈에 띄는 종류의 손상이기 때문.
    return text, len(encode(text)) > limit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", type=Path, required=True)
    ap.add_argument("--auto", type=Path, required=True)
    ap.add_argument("--manual", type=Path, required=True)
    args = ap.parse_args()

    rows = json.loads(args.targets.read_text(encoding="utf-8"))
    auto, manual = [], []

    for r in rows:
        text = r["text"]
        m = SPEAKER_RE.match(text)
        spk = m.group(1) if m else ""
        reasons = []

        # 이름이 하나도 없으면 지시/화법 때문에 걸린 것 — 무조건 수동
        has_name = bool(NAME_RE.search(text))
        # '그녀석' 은 '그녀' 오탐 — 그것만 있으면 지시로 치지 않는다
        refs = [w for w in REF_WORDS if w in text]
        if refs == ["그녀"] and text.count("그녀") == text.count("그녀석"):
            refs = []
        if refs:
            reasons.append("지시")
        if any(w in text for w in STYLE_WORDS):
            reasons.append("화법")
        if "라미아" in text and "액셀" in text:
            reasons.append("양쪽이름")
        if not has_name:
            reasons.append("이름없음")

        if reasons:
            manual.append({**r, "spk": spk, "reasons": reasons})
            continue

        if text in LINE_SWAP:
            new = LINE_SWAP[text]
            if len(encode(new)) <= r["len"]:
                auto.append({"off": r["off"], "orig": text, "new": new,
                             "orig_len": r["len"],
                             "new_len": len(encode(new)), "fit": True})
                continue

        new = swap_names(text)
        if spk == "라미아":
            new = apply_style(new)
            if (any(q in new for q in QUIRK_MARKERS) or has_hapnida(new)
                    or any(b in new for b in BROKEN_PATTERNS)):
                manual.append({**r, "spk": spk, "reasons": ["말투잔존"],
                               "attempt": new})
                continue
        if new == text:
            continue
        new, trimmed = trim_to_fit(new, r["len"])
        if len(encode(new)) > r["len"]:
            manual.append({**r, "spk": spk, "reasons": ["길이초과"],
                           "attempt": new})
            continue
        if trimmed:
            manual.append({**r, "spk": spk, "reasons": ["길이상쇄"],
                           "attempt": new})
            continue
        auto.append({"off": r["off"], "orig": text, "new": new,
                     "orig_len": r["len"], "new_len": len(encode(new)),
                     "fit": True})

    args.auto.parent.mkdir(parents=True, exist_ok=True)
    args.auto.write_text(json.dumps(auto, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    args.manual.write_text(json.dumps(manual, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    from collections import Counter
    print(f"대상 {len(rows)}건 → 자동 {len(auto)} / 수동 {len(manual)}")
    c = Counter(x for r in manual for x in r["reasons"])
    print("  수동 사유:", dict(c.most_common()))
    print(f"  {args.auto} / {args.manual}")


if __name__ == "__main__":
    main()
