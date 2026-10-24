# -*- coding: utf-8 -*-
"""Safely restore the four native player battle chunks for role-swapped Axel.

PASS34 treated the last ``2*N`` bytes before f2 as a row-by-row ``ctx`` array.
That was wrong: the whole chunk prefix contains several selector formats and
must be restored as one native unit.  Mixing that prefix with the compact
PASS33 payload layout produced black portraits, ``???`` speaker names and
attack cues that selected miss/dodge subtitles.

This revision copies ``chunk.off..f3`` (all selector data plus the complete f2
speaker/tag array) byte-for-byte from the native baseline, keeps all
``P=N-1`` physical payload rows in place, and rebuilds only f3/f4/string data.
The 16 mixed-speaker rows use their actual f2 speaker key when choosing the AP
Axel personality, and the seven historically undecodable 0x521 rows are
recovered by their native voice IDs.  Source semantics come from audited
physical spans, never from negation-sensitive keyword guesses.

The target ISO is edited transactionally.  Every write is journalled and a
failed post-write check restores the exact preimage.

--restore-soulgain is an incremental mode for the final 2026-10-02 ISO. It
adds native Soulgain selector graphs to both player personalities, preserves
the existing payloads, and expands the SSTM descriptor table within verified
archive padding. It does not rerun the original PASS35 semantic mapper.
--restore-vaisaga incrementally restores AP's D4/D5 Vaisaga graph on top of
that result and the audited 80-line scenario follow-up, without undoing either.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import struct
from pathlib import Path

import battle_block as BB
import extend_machine_lines as EXT
import place_axel_battle_lines as PLACE
import port_aportable_axel_voice as PORT
from ogs_korean_codec import decode, encode


SPECS = {
    0x3F4: ("D4", 0xD4),
    0x4A4: ("D4", 0xD4),
    0x4A5: ("D5", 0xD5),
    0x521: ("D5", 0xD5),
}

EXPECTED_OGS_SIZE = 4_518_150_144
EXPECTED_AP_SIZE = 1_497_765_888
EXPECTED_BASELINE_SHA256 = (
    "9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C")
EXPECTED_AP_SHA256 = (
    "EFBE571B194E33625ACB7D094E81A2090FD290A1B058E1F762795659030491CE")
EXPECTED_RUNTIME_SHA256 = {
    "apD4.json":
        "5FB0E1CC788D5F2A21B38417B8D3C95C889B0619B79236153FDEF8EDC595B711",
    "apD5.json":
        "2E9A26251E11A6E53923A9EFA72A8136F8323D5B0392CA47C266C22185295FE7",
    "entry5_chunks.json":
        "329FFDF2CF6CBD4BF1D8F3332885F33CDB6971F12B7C3B65B717AB7878B9DC5A",
    "place416.json":
        "569B9C548DFF761DCD8C002AF3804597B6A5B1F0BBEC8AEF8D962A874C8BC1E6",
    "place417.json":
        "FA69BF0262204E43844B9E3EEFE3C42259F59D09ECAAA79A42EC4AC38F31F028",
    "pass32_axel_battle_relation_overrides.json":
        "B15B2A9CABF68C83D7FA1B5C41EA923ECBEFA5ACED9C8866445A1F9D0EF745DD",
    "machine_extra.json":
        "E6FC994244C9A83A63F45A25C985175B49416620C87C414BE68F893956A7531E",
    "pass33_axel_battle_repeat_overrides.json":
        "B6DE5812C7B7454C0B24E624F67DEA86BABC986DC38230788BA7ABA70553FBC1",
}

# PASS33 uses 181 clips.  Four one-word fillers are deliberately retired and
# contextual/long alternatives are admitted.  The candidate pool may exceed
# the original 194-entry descriptor allocation; only the distinct clips actually
# selected by the mapping are packed and that final count is capped below.
DROP_CLIPS = {137, 149, 151, 152}  # 가랏 / 하앗 / 으럇 / 이야압 (D5 fillers)
ADD_CLIPS = {
    65, 66, 67, 69,       # Lemon/Vindel relationship lines
    128,                  # long generic attack
    163, 170,             # long finisher/Vaisaga lines
    188,                  # support
    194, 197,             # miss
    200, 201, 207, 215,   # dodge
    210, 223, 230,        # damage/light damage
}

EXTRA_GENERIC_CLIPS = {
    # Long or context-rich alternatives omitted by the compact PASS33 bank.
    46, 70, 72, 75, 77, 83, 95, 100, 103, 104, 105,
    161, 172, 192, 198, 213, 218, 235,
}

RELATION_RESERVED_D5 = set(range(10, 20)) | set(range(28, 32)) | set(
    range(37, 41)) | set(range(47, 51)) | {59, 60, 62, 63, 64, 65, 66}

RELATION_POOLS_D5 = {
    ("w17", "atk"): [10, 11, 12, 13, 14],
    ("w17", "fin"): [10, 11, 12, 13, 14],
    ("w17", "hit"): [28, 29, 30, 31, 37, 38, 39, 40],
    ("w17", "hit_light"): [28, 29, 30, 31, 37, 38, 39, 40],
    ("w17", "dodge"): [47, 48, 49, 50, 59, 60],
    ("w17", "miss"): [47, 48, 49, 50, 59, 60],
    ("lemon", "atk"): [15, 16],
    ("lemon", "fin"): [15, 16],
    ("vindel", "atk"): [17, 18, 19],
    ("vindel", "fin"): [17, 18, 19],
}

CONTROL_RE = re.compile(r"[「」『』…！？，。・、／/\s　]")
SILENCE_RE = re.compile(r"^[…・。\s　]*$")
REL_TEXT_RE = re.compile(r"레몬|빈델|Ｗ１７|인형")

# Audited native physical payload ledger.  These are payload indices, not
# selector indices.  In particular 4A5[118:120] are attack/defeat responses;
# identical-looking copies at 120+ are damage responses.
SOURCE_LEDGER = {
    0x3F4: [
        (0, 21, "atk"), (21, 47, "damage"), (47, 74, "dodge"),
        (74, 75, "silence"), (75, 81, "miss"), (81, 96, "support"),
        (96, 98, "silence"), (98, 367, "weapon"),
    ],
    0x4A4: [
        (0, 55, "atk"), (55, 109, "damage"), (109, 150, "dodge"),
        (150, 151, "silence"), (151, 157, "miss"),
        (157, 198, "support"), (198, 200, "silence"),
        (200, 471, "weapon"),
    ],
    0x4A5: [
        (0, 120, "atk"), (120, 204, "damage"), (204, 279, "dodge"),
        (279, 280, "silence"), (280, 286, "miss"),
        (286, 352, "support"), (352, 354, "silence"),
        (354, 625, "weapon"),
    ],
    0x521: [
        (0, 21, "atk"), (21, 46, "damage"), (46, 73, "dodge"),
        (73, 74, "silence"), (74, 80, "miss"), (80, 95, "support"),
        (95, 97, "silence"), (97, 361, "weapon"),
    ],
}

SILENCE_ROWS = {
    0x3F4: {74, 96, 97},
    0x4A4: {150, 198, 199},
    0x4A5: {279, 352, 353},
    0x521: {73, 95, 96},
}

AP_BY_SPEAKER = {
    0x3F4: ("D4", 0xD4),
    0x4A4: ("D4", 0xD4),
    0x4A5: ("D5", 0xD5),
    0x521: ("D5", 0xD5),
}

# These late AP attack rows are substantial, relation-neutral and structurally
# adjacent to the weapon table.  Reserve them for generic weapon cues instead
# of also leaving them in ordinary attack rotation; the pools must be disjoint
# so a selector transition cannot repeat the same subtitle twice.
WEAPON_ATTACK_RESERVE = {
    0xD4: {68, 69, 70, 71},
    0xD5: {108, 110, 111},
}

# AP weapon blocks are structural index ranges.  Continuation lines that do
# not repeat the weapon name remain attached to the right weapon.
AP_WEAPON_SPANS = {
    0xD4: {
        "matrix": range(72, 82), "halberd": range(82, 86),
        "sword": range(86, 92), "rekkajin": range(92, 94),
        "suiryu": range(94, 97), "shippu": range(97, 102),
        "fujin": range(102, 104), "koujin": range(104, 107),
        "vaisaga": range(92, 107),
        "seiryu": range(107, 109), "genbu": range(109, 112),
        "byakko": range(112, 115), "suzaku": range(115, 121),
        "kirin": range(121, 150),
        "soulgain": range(107, 150),
    },
    0xD5: {
        "matrix": range(112, 120), "halberd": range(120, 126),
        "sword": range(126, 130), "rekkajin": range(130, 131),
        "suiryu": range(131, 133), "shippu": range(133, 134),
        "fujin": range(134, 137), "koujin": range(137, 140),
        "vaisaga": range(130, 140),
        "seiryu": range(140, 142), "genbu": range(142, 145),
        "byakko": range(145, 148), "suzaku": range(148, 153),
        "kirin": range(153, 193),
        "soulgain": range(140, 193),
    },
}

# Native Vysaga payload block, inclusive start / exclusive end.  Its first
# eleven rows are the unnamed early weapons, followed by Wind Blade and the
# secret technique.  Physical position is the only reliable discriminator.
VAISAGA_BLOCKS = {
    0x3F4: (124, 150),
    0x4A4: (228, 254),
    0x4A5: (380, 408),
    0x521: (123, 151),
}

VAISAGA_SUBSPANS = {
    0x3F4: [(124, 132, "vaisaga"), (132, 141, "fujin"),
            (141, 150, "koujin")],
    0x4A4: [(228, 234, "vaisaga"), (234, 243, "fujin"),
            (243, 252, "koujin"), (252, 254, "vaisaga")],
    0x4A5: [(380, 388, "vaisaga"), (388, 397, "fujin"),
            (397, 406, "koujin"), (406, 408, "vaisaga")],
    0x521: [(123, 131, "vaisaga"), (131, 140, "fujin"),
            (140, 149, "koujin"), (149, 151, "vaisaga")],
}

SPECIAL_WEAPON_WORDS = {
    "열화인": "rekkajin", "손톱": "rekkajin",
    "수류조": "suiryu", "질공도": "shippu", "지참": "shippu",
    "광풍": "fujin", "풍인섬": "fujin", "광인섬": "koujin",
    "비늘포": "seiryu", "파이널　코드": "kirin", "파이널 코드": "kirin",
}

WEAPON_ALIASES = {
    "fujinsen": "fujin", "koujinsen": "koujin",
    "sword_breaker": "sword", "sword": "sword",
    "halbert": "halberd", "halberd": "halberd",
    "seiryurin": "seiryu", "genbugodan": "genbu",
    "byakkoko": "byakko", "maishujaku": "suzaku",
}

RANGED_CUE_RE = re.compile(
    r"조준|발사|캐논|런처|런쳐|미사일|사격|저격|포착|"
    r"(?<![가-힣])록(?![가-힣])|록온|탄|빔|애로우|랜서")
MELEE_CUE_RE = re.compile(
    r"검|칼|베어|베겠|베고|베라|베주|벤다|참격|찢|꿰뚫|때려|박|"
    r"근접|타격|연속|주먹|펀치|스테이크|벙커|할버|소드|칼날")
FINISH_CUE_RE = re.compile(
    r"끝이다|끝내|끝장|리미트|한계|오의|최대출력|풀\s*드라이브|코드|결착")
PURE_SHOUT_RE = re.compile(
    r"^[「」\s　]*(?:이야[아앗]*|하[아앗]*|으럇|우오[오옷]*|"
    r"으랴[아앗]*|으라챠[아앗]*|에에잇|가랏|간다)"
    r"[！…\s　「」]*$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(16 * 1024 * 1024):
            h.update(block)
    return h.hexdigest().upper()


def meaningful_length(text: str) -> int:
    return len(CONTROL_RE.sub("", text))


def weapon_key(text: str) -> str | None:
    for word, key in SPECIAL_WEAPON_WORDS.items():
        if word in text:
            return key
    key = EXT.ap_weapon_key(text) or EXT.lamia_weapon_key(text)
    return WEAPON_ALIASES.get(key, key)


def relation_kind(text: str) -> str | None:
    if "레몬" in text:
        return "lemon"
    if "빈델" in text:
        return "vindel"
    # In the native Lamia table, Axel/captain is the opposing role.  After the
    # swap that relationship becomes Axel addressing Lamia (W17).
    if "엑셀" in text or "액셀" in text or "대장" in text or "Ｗ１７" in text:
        return "w17"
    return None


def source_relation(key: int, index: int) -> str | None:
    """Return the audited native relationship block for a payload slot.

    The final line of the W17 and Vindel groups does not repeat the target's
    name, so keyword inference silently turned those lines generic.  Physical
    slots are authoritative here; 4A5[60:65] is deliberately *not* W17.
    """
    if key != 0x4A5:
        return None
    if 56 <= index <= 59:
        return "w17"
    if 65 <= index <= 67:
        return "lemon"
    if 68 <= index <= 69:
        return "vindel"
    return None


def ledger_category(key: int, index: int, flag: int) -> str:
    for lo, hi, category in SOURCE_LEDGER[key]:
        if lo <= index < hi:
            if category == "damage":
                # Native flags distinguish the stronger reaction variants.
                return "hit" if flag in {0x1000, 0x1800, 0x5800} else "hit_light"
            return category
    raise ValueError(f"0x{key:X}[{index}] is outside the audited payload ledger")


def source_weapon_key(key: int, index: int, text: str) -> str | None:
    for lo, hi, family in VAISAGA_SUBSPANS[key]:
        if lo <= index < hi:
            # The front block contains the first three weapons but their
            # selector boundaries are not proven, so it remains name-neutral.
            return family
    return weapon_key(text)


def weapon_cue(text: str, flag: int = 0) -> str:
    if flag == 0x7000 or FINISH_CUE_RE.search(text):
        return "fin"
    if RANGED_CUE_RE.search(text):
        return "ranged"
    if MELEE_CUE_RE.search(text):
        return "melee"
    return "generic"


def current_pass33_clips(runtime: Path) -> set[int]:
    rows416 = json.loads((runtime / "place416.json").read_text(encoding="utf-8"))
    rows417 = json.loads((runtime / "place417.json").read_text(encoding="utf-8"))
    ap4 = {r["i"]: r for r in json.loads((runtime / "apD4.json").read_text(encoding="utf-8"))}
    ap5 = {r["i"]: r for r in json.loads((runtime / "apD5.json").read_text(encoding="utf-8"))}
    p32 = json.loads((runtime / "pass32_axel_battle_relation_overrides.json").read_text(
        encoding="utf-8"))["overrides"]
    for index, ap_i in p32.items():
        rows417[int(index)].update(voice=ap5[int(ap_i)]["voice"], text=ap5[int(ap_i)]["text"])
    extras = json.loads((runtime / "machine_extra.json").read_text(encoding="utf-8"))
    p33 = json.loads((runtime / "pass33_axel_battle_repeat_overrides.json").read_text(
        encoding="utf-8"))
    for index, ap_i in p33["place416"].items():
        rows416[int(index)].update(voice=ap4[int(ap_i)]["voice"], text=ap4[int(ap_i)]["text"])
    for key, overrides in p33["machine_extra"].items():
        for index, ap_i in overrides.items():
            extras[key][int(index)].update(
                voice=ap4[int(ap_i)]["voice"], text=ap4[int(ap_i)]["text"])
    return {
        r["voice"] % 1000
        for rows in [rows416, rows417, *extras.values()]
        for r in rows if r["voice"]
    }


class Picker:
    def __init__(self, ap_rows: list[dict], ap_key: int, allowed: set[int]):
        self.ap_key = ap_key
        self.allowed = allowed
        self.rows = [r for r in ap_rows if r["voice"] and r["voice"] % 1000 in allowed]
        self.by_i = {r["i"]: r for r in self.rows}
        self.uses: collections.Counter[int] = collections.Counter()
        self.last_voice: int | None = None
        self.generic: dict[str, list[dict]] = collections.defaultdict(list)
        self.weapons: dict[str, list[dict]] = collections.defaultdict(list)
        self.weapon_generic: list[dict] = []
        self.weapon_attack_generic: list[dict] = []
        self.last_text: str | None = None

        for group, span in AP_WEAPON_SPANS[ap_key].items():
            self.weapons[group] = [self.by_i[i] for i in span if i in self.by_i]

        for row in self.rows:
            cat = PLACE.ap_class(row["i"], ap_key)
            if cat == "weapon":
                # Unsupported OGs machines receive only name-neutral lines.
                # Prefer substantial phrases so the old one-word-shout bias
                # does not return.
                if (not weapon_key(row["text"])
                        and not REL_TEXT_RE.search(row["text"])
                        and not PURE_SHOUT_RE.fullmatch(row["text"])
                        and meaningful_length(row["text"]) >= 4):
                    self.weapon_generic.append(row)
                continue
            if ap_key == 0xD5 and row["i"] in RELATION_RESERVED_D5:
                continue
            if REL_TEXT_RE.search(row["text"]):
                continue
            if (cat == "atk" and row["i"] in WEAPON_ATTACK_RESERVE[ap_key]
                    and not weapon_key(row["text"])
                    and not PURE_SHOUT_RE.fullmatch(row["text"])
                    and meaningful_length(row["text"]) >= 6):
                # AP's ordinary attack pool contains many substantial,
                # weapon-neutral lines.  Reusing them for generic weapon cues
                # avoids collapsing hundreds of restored native slots onto a
                # handful of cries while keeping miss/dodge lines out.
                self.weapon_attack_generic.append(row)
                continue
            self.generic[cat].append(row)

        self.relations: dict[tuple[str, str], list[dict]] = {}
        if ap_key == 0xD5:
            for key, indices in RELATION_POOLS_D5.items():
                self.relations[key] = [self.by_i[i] for i in indices if i in self.by_i]

    @staticmethod
    def _weight(row: dict) -> float:
        n = meaningful_length(row["text"])
        if n >= 18:
            return 2.0
        if n >= 12:
            return 1.7
        if n >= 9:
            return 1.4
        if n >= 6:
            return 0.70
        return 0.25

    def choose(self, candidates: list[dict], exact: set[int] | None = None) -> dict:
        if not candidates:
            raise ValueError("empty AP candidate pool")

        def score(row: dict):
            voice = row["voice"]
            weight = self._weight(row)
            repeat = 1 if (voice == self.last_voice or row["text"] == self.last_text) else 0
            specificity = 0 if exact is None or row["i"] in exact else 1
            return (repeat, self.uses[voice] / weight + specificity * 0.75,
                    specificity, -weight,
                    -meaningful_length(row["text"]), row["i"])

        row = min(candidates, key=score)
        self.uses[row["voice"]] += 1
        self.last_voice = row["voice"]
        self.last_text = row["text"]
        return row

    def pick(self, source: dict) -> tuple[dict, str, str | None, str | None]:
        cat = source["category"]
        rel = source.get("relation")
        wk = source["weapon"]
        if cat == "silence":
            return {"i": -1, "voice": 0, "text": "………"}, cat, rel, wk

        if cat == "weapon":
            exact_rows = list(self.weapons.get(wk, [])) if wk else []
            cue = source["cue"]
            # Match the native cue role inside a confirmed family: 0x7000 is
            # the technique-name/impact cue; ordinary flags favor the same
            # family's name-neutral setup/follow-up.  If a family has only a
            # named AP line, fall back to the complete family.
            had_substantive_family = False
            if exact_rows:
                if wk == "vaisaga":
                    preferred = [row for row in exact_rows
                                 if weapon_key(row["text"]) is None]
                elif source["flag"] == 0x7000:
                    preferred = [row for row in exact_rows
                                 if weapon_key(row["text"]) == wk]
                else:
                    preferred = [row for row in exact_rows
                                 if weapon_key(row["text"]) is None]
                preferred = preferred or exact_rows
                # A family-exact wordless yell is technically compatible but
                # makes the restored multi-cue selectors feel like nothing
                # but one-shot shouts.  Keep it only when that family truly
                # has no substantive alternative.
                substantive = [
                    row for row in preferred
                    if not PURE_SHOUT_RE.fullmatch(row["text"])
                    and meaningful_length(row["text"]) >= 4
                ]
                had_substantive_family = bool(substantive)
                preferred = substantive or preferred
                cue_preferred = [row for row in preferred
                                 if weapon_cue(row["text"]) == cue]
                preferred = cue_preferred or preferred
            else:
                preferred = []
            exact_ids = {row["i"] for row in preferred}
            exact_all = {row["i"] for row in exact_rows}
            if wk == "vaisaga":
                # Front/post Vysaga boundaries are not proven per weapon.
                # Never fall through to a named Heat/Water/Shippu line.
                exact_rows = preferred
            else:
                family_fallback = [row for row in exact_rows
                                   if row["i"] not in exact_ids]
                if had_substantive_family:
                    family_fallback = [
                        row for row in family_fallback
                        if not PURE_SHOUT_RE.fullmatch(row["text"])
                    ]
                exact_rows = preferred + family_fallback
            generic_rows = [row for row in (
                                self.weapon_generic
                                + self.weapon_attack_generic)
                            if row["i"] not in exact_all]
            role_generic = [row for row in generic_rows
                            if weapon_cue(row["text"]) == cue]
            candidates = exact_rows + (role_generic or generic_rows)
            if not candidates:
                candidates = list(self.generic.get("atk", []))
            return self.choose(candidates, exact_ids or None), cat, rel, wk

        relation = self.relations.get((rel, cat)) if rel else None
        if relation:
            return self.choose(relation), cat, rel, wk

        fallback = {
            "hit": ["hit", "hit_light"],
            "hit_light": ["hit_light", "hit"],
            "dodge": ["dodge"],
            "miss": ["miss"],
            "support": ["support"],
            "atk": ["atk"],
        }[cat]
        candidates: list[dict] = []
        seen_voices = set()
        for group in fallback:
            for row in self.generic.get(group, []):
                if row["voice"] not in seen_voices:
                    candidates.append(row)
                    seen_voices.add(row["voice"])
        return self.choose(candidates), cat, rel, wk


def _native_rows(entry: bytes, chunks: dict[int, dict]) -> dict[int, list[dict]]:
    """Read all P=N-1 native payloads and recover seven blank 0x521 texts."""
    out: dict[int, list[dict]] = {}
    voice_text: dict[int, str] = {}
    unresolved: list[dict] = []
    for key in SPECS:
        chunk = chunks[key]
        n = chunk["n"]
        p = (chunk["pool"] - chunk["f4"]) // 4
        if p != n - 1:
            raise ValueError(f"0x{key:X}: expected P=N-1, got N={n}, P={p}")
        rows = []
        pool_end = chunk["pool"] + chunk["pool_cap"]
        for i in range(p):
            tag = struct.unpack_from("<H", entry, chunk["f2"] + i * 2)[0]
            if not tag:
                raise ValueError(f"0x{key:X}[{i}] native active tag is zero")
            text_off = struct.unpack_from("<H", entry, chunk["f3"] + i * 2)[0]
            start = chunk["pool"] + text_off
            end = entry.find(b"\0", start, pool_end) if start < pool_end else -1
            text = ""
            if chunk["pool"] <= start < pool_end and end >= start:
                text = decode(entry[start:end])
            voice = struct.unpack_from("<I", entry, chunk["f4"] + i * 4)[0]
            row = {
                "i": i, "tag": tag, "speaker": tag & 0x7FF,
                "flag": tag & 0xF800, "source_voice": voice,
                "text": text,
            }
            rows.append(row)
            if text and voice >= 1_000_000:
                # A handful of shared native clips differ only in spacing or
                # punctuation; either valid copy is sufficient for the seven
                # genuinely undecodable 0x521 rows.
                voice_text.setdefault(voice, text)
            elif not text and voice >= 1_000_000:
                unresolved.append(row)
        out[key] = rows

    for row in unresolved:
        recovered = voice_text.get(row["source_voice"])
        if not recovered:
            raise ValueError(f"cannot recover native voice {row['source_voice']}")
        row["text"] = recovered
        row["recovered"] = True
    return out


def make_mapping(native_entry: bytes, chunks: dict[int, dict], runtime: Path,
                 allowed: set[int]) -> dict[int, list[dict]]:
    ap_data = {
        "D4": json.loads((runtime / "apD4.json").read_text(encoding="utf-8")),
        "D5": json.loads((runtime / "apD5.json").read_text(encoding="utf-8")),
    }
    native = _native_rows(native_entry, chunks)
    out: dict[int, list[dict]] = {}
    for key in SPECS:
        pickers: dict[int, Picker] = {}
        rows = []
        for source in native[key]:
            speaker = source["speaker"]
            if speaker not in AP_BY_SPEAKER:
                raise ValueError(f"0x{key:X}[{source['i']}] unknown speaker 0x{speaker:X}")
            ap_name, ap_key = AP_BY_SPEAKER[speaker]
            picker = pickers.setdefault(
                ap_key, Picker(ap_data[ap_name], ap_key, allowed))
            source["category"] = ledger_category(key, source["i"], source["flag"])
            source["relation"] = (
                source_relation(key, source["i"])
                or relation_kind(source["text"]))
            source["weapon"] = (
                source_weapon_key(key, source["i"], source["text"])
                if source["category"] == "weapon" else None)
            source["cue"] = (weapon_cue(source["text"], source["flag"])
                             if source["category"] == "weapon" else None)
            picked, category, relation, wk = picker.pick(source)
            rows.append({
                "i": source["i"], "tag": source["tag"],
                "speaker": speaker, "flag": source["flag"],
                "source_voice": source["source_voice"],
                "recovered": bool(source.get("recovered")),
                "orig": source["text"], "category": category,
                "relation": relation, "weapon": wk, "cue": source["cue"],
                "ap_name": ap_name, "ap_key": ap_key,
                "ap_i": picked["i"], "voice": picked["voice"],
                "clip": 0 if not picked["voice"] else picked["voice"] % 1000,
                "text": picked["text"],
            })
        out[key] = rows
    return out


def build_chunk(native: bytes, chunk: dict, key: int, rows: list[dict],
                clip_slots: dict[int, int]) -> tuple[list[tuple[int, bytes]], int]:
    n = chunk["n"]
    p = (chunk["pool"] - chunk["f4"]) // 4
    if p != n - 1 or len(rows) != p:
        raise ValueError(f"0x{key:X}: N={n}, P={p}, rows={len(rows)}")
    # Keep the final f3 sentinel and write only the true P-entry f4 span.
    a3 = bytearray(native[chunk["f3"]:chunk["f4"]])
    a4 = bytearray(4 * p)

    # pool[0:4] doubles as the historical f4 sentinel when the arrays are
    # viewed as N entries.  Preserve the complete first native string as an
    # unused prefix, then place all AP strings after it.
    native_first_end = native.find(
        b"\0", chunk["pool"], chunk["pool"] + chunk["pool_cap"])
    if native_first_end < 0:
        raise ValueError(f"0x{key:X}: native pool has no first terminator")
    pool = bytearray(native[chunk["pool"]:native_first_end + 1])
    strings: dict[bytes, int] = {}
    for row in rows:
        i = row["i"]
        if not 0 <= i < p:
            raise ValueError(f"0x{key:X} payload index {i} outside P={p}")
        raw = encode(row["text"])
        off = strings.get(raw)
        if off is None:
            off = len(pool)
            strings[raw] = off
            pool += raw + b"\0"
        if off > 0xFFFF:
            raise ValueError(f"0x{key:X} string offset exceeds u16")
        struct.pack_into("<H", a3, i * 2, off)
        if row["voice"]:
            clip = row["voice"] % 1000
            struct.pack_into("<I", a4, i * 4,
                             PORT.OG_AXEL_BANK * 1000 + clip_slots[clip])
    if len(pool) > chunk["pool_cap"]:
        raise ValueError(f"0x{key:X} pool {len(pool)} > {chunk['pool_cap']}")
    writes = [
        # This restores all selector formats plus the complete native f2 tags.
        (chunk["off"], native[chunk["off"]:chunk["f3"]]),
        (chunk["f3"], bytes(a3)),
        (chunk["f4"], bytes(a4)),
        (chunk["pool"], bytes(pool) + b"\0" * (chunk["pool_cap"] - len(pool))),
    ]
    return writes, len(pool)


def estimated_ild_size(aportable: Path, clip: int) -> int:
    samples = PORT.riff_samples(PORT.a_riff(aportable, clip))
    output_samples = math.ceil(samples * PORT.SAMPLE_RATE / 44100)
    return PORT.align(0x810 + math.ceil(output_samples / 28) * 16, PORT.SECTOR)


def mapping_stats(mapping: dict[int, list[dict]]) -> dict:
    all_rows = [row for rows in mapping.values() for row in rows]
    voiced = [row for row in all_rows if row["voice"]]
    short5 = [row for row in voiced if meaningful_length(row["text"]) <= 5]
    short8 = [row for row in voiced if meaningful_length(row["text"]) <= 8]
    relation_leaks = []
    for row in voiced:
        mapped_relation = None
        if row["ap_key"] == 0xD5:
            i = row["ap_i"]
            if i in set(range(10, 15)) | set(range(28, 32)) | set(
                    range(37, 41)) | set(range(47, 51)) | {59, 60}:
                mapped_relation = "w17"
            elif i in {15, 16}:
                mapped_relation = "lemon"
            elif i in {17, 18, 19}:
                mapped_relation = "vindel"
        if mapped_relation and mapped_relation != row["relation"]:
            relation_leaks.append(row)
    weapon_errors = []
    for row in voiced:
        mapped_key = weapon_key(row["text"])
        source_key = row["weapon"]
        compatible = (not mapped_key or mapped_key == source_key
                      or (source_key == "soulgain" and mapped_key in {
                          "seiryu", "genbu", "byakko", "suzaku", "kirin"}))
        if not compatible:
            weapon_errors.append({
                "i": row["i"], "orig": row["orig"], "mapped": row["text"],
                "source_weapon": row["weapon"], "mapped_weapon": mapped_key,
            })
    pure_shout_weapon = [
        {"key": f"0x{key:X}", "i": row["i"], "ap_i": row["ap_i"],
         "text": row["text"]}
        for key, rows in mapping.items() for row in rows
        if (row["voice"] and row["category"] == "weapon"
            and PURE_SHOUT_RE.fullmatch(row["text"]))
    ]
    cue_opposites = []
    for key, rows in mapping.items():
        for row in rows:
            if not row["voice"] or row["category"] != "weapon":
                continue
            mapped_cue = weapon_cue(row["text"])
            if ({row["cue"], mapped_cue} == {"ranged", "melee"}):
                cue_opposites.append({
                    "key": f"0x{key:X}", "i": row["i"],
                    "source_cue": row["cue"], "mapped_cue": mapped_cue,
                    "orig": row["orig"], "mapped": row["text"],
                })
    repeats = collections.Counter(row["text"] for row in voiced)
    adjacent_duplicates = []
    selector_cross_repeats = []
    per_key = {}
    for key, rows in mapping.items():
        key_voiced = [row for row in rows if row["voice"]]
        key_repeats = collections.Counter(row["text"] for row in key_voiced)
        per_key[f"0x{key:X}"] = {
            "rows": len(rows),
            "voiced": len(key_voiced),
            "unique_texts": len(key_repeats),
            "short_le_5": sum(meaningful_length(row["text"]) <= 5 for row in key_voiced),
            "top_repeats": key_repeats.most_common(10),
        }
        attack_rows = [row for row in rows
                       if row["voice"] and row["category"] == "atk"]
        weapon_rows = [row for row in rows
                       if row["voice"] and row["category"] == "weapon"]
        common_texts = sorted(
            {row["text"] for row in attack_rows}
            & {row["text"] for row in weapon_rows})
        common_clips = sorted(
            {row["clip"] for row in attack_rows}
            & {row["clip"] for row in weapon_rows})
        if common_texts or common_clips:
            selector_cross_repeats.append({
                "key": f"0x{key:X}", "texts": common_texts,
                "clips": common_clips,
            })
        for left, right in zip(rows, rows[1:]):
            if (left["voice"] and left["text"] == right["text"]
                    and left["voice"] == right["voice"]):
                adjacent_duplicates.append({
                    "key": f"0x{key:X}", "left": left["i"],
                    "right": right["i"], "text": left["text"],
                })
    critical_group_errors = []
    for key, indices in {0x4A5: (612, 613, 614),
                         0x521: (348, 349, 350)}.items():
        chosen = [mapping[key][i] for i in indices]
        pairs = {(row["text"], row["voice"]) for row in chosen}
        if len(pairs) != len(chosen):
            critical_group_errors.append({
                "key": f"0x{key:X}", "indices": list(indices),
                "mapped": [(row["text"], row["voice"]) for row in chosen],
            })
    return {
        "live_trigger_rows": len(all_rows),
        "voiced_rows": len(voiced),
        "unique_texts": len({row["text"] for row in voiced}),
        "unique_clips": len({row["voice"] % 1000 for row in voiced}),
        "short_le_5": len(short5),
        "short_le_5_ratio": round(len(short5) / len(voiced), 4),
        "short_le_8": len(short8),
        "short_le_8_ratio": round(len(short8) / len(voiced), 4),
        "categories": dict(collections.Counter(row["category"] for row in all_rows)),
        "top_repeats": repeats.most_common(20),
        "per_key": per_key,
        "relationship_leaks": relation_leaks,
        "weapon_mismatches": weapon_errors,
        "pure_shout_weapon": pure_shout_weapon,
        "cue_opposites": cue_opposites,
        "adjacent_duplicates": adjacent_duplicates,
        "selector_cross_repeats": selector_cross_repeats,
        "critical_group_errors": critical_group_errors,
        "recovered_native_rows": sum(bool(row["recovered"]) for row in all_rows),
        "mixed_speaker_rows": sum(row["speaker"] != key
                                  for key, rows in mapping.items() for row in rows),
    }


def validate_written(iso: Path, native: bytes, chunks: dict[int, dict],
                     mapping: dict[int, list[dict]],
                     clip_slots: dict[int, int]) -> None:
    entry = BB.read_entry5(iso)
    for key, rows in mapping.items():
        chunk = chunks[key]
        n = chunk["n"]
        p = (chunk["pool"] - chunk["f4"]) // 4
        if entry[chunk["off"]:chunk["f3"]] != native[chunk["off"]:chunk["f3"]]:
            raise ValueError(f"0x{key:X} selector/f2 prefix differs from native")
        if entry[chunk["pool"]:chunk["pool"] + 4] != native[
                chunk["pool"]:chunk["pool"] + 4]:
            raise ValueError(f"0x{key:X} f4/pool sentinel differs from native")
        if struct.unpack_from("<H", entry, chunk["f3"] + (n - 1) * 2)[0] != 0:
            raise ValueError(f"0x{key:X} final f3 sentinel is not zero")
        expected = {row["i"]: row for row in rows}
        if len(expected) != p:
            raise ValueError(f"0x{key:X} expected {p} mapped payloads")
        pool_end = chunk["pool"] + chunk["pool_cap"]
        for i in range(p):
            tag = struct.unpack_from("<H", entry, chunk["f2"] + i * 2)[0]
            row = expected[i]
            if tag != row["tag"]:
                raise ValueError(f"0x{key:X}[{i}] tag mismatch")
            text_off = struct.unpack_from("<H", entry, chunk["f3"] + i * 2)[0]
            start = chunk["pool"] + text_off
            end = entry.find(b"\0", start, pool_end)
            if not chunk["pool"] <= start < pool_end or end < start:
                raise ValueError(f"0x{key:X}[{i}] invalid text offset")
            if decode(entry[start:end]) != row["text"]:
                raise ValueError(f"0x{key:X}[{i}] text mismatch")
            voice = struct.unpack_from("<I", entry, chunk["f4"] + i * 4)[0]
            wanted_voice = 0 if not row["voice"] else (
                PORT.OG_AXEL_BANK * 1000 + clip_slots[row["voice"] % 1000])
            if voice != wanted_voice:
                raise ValueError(f"0x{key:X}[{i}] voice mismatch")
        final_tag = struct.unpack_from("<H", entry, chunk["f2"] + p * 2)[0]
        if final_tag != 0:
            raise ValueError(f"0x{key:X} final f2 sentinel is not zero")


SOULGAIN_KEYS = (106000, 106010, 106021, 106030, 106031, 106040, 106041)
SOULGAIN_SOURCE_SHA = "747832E0310F6CD4B23A702FC1FC928C19F6D44B8B51879184FCC2459BEF6915"
# AP D4 266xxx selectors were inspected directly.  Keep ordinary Kirin,
# excluding its separate Shin-Kyoku branch.  Duplicate the ordinary 8-line
# finish for OGs' two native alternatives, just as D5's donor does.
SOULGAIN_D4_ROWS = tuple(range(107, 124)) + tuple(range(126, 134))*2


def _weapon_tables(raw: bytes):
    h = list(struct.unpack_from("<16H", raw))
    a = 0x288
    b = a + h[0] * 8
    c = b + h[1] * 8
    return h, [struct.unpack_from("<IHH", raw, a+i*8) for i in range(h[0])], [
        struct.unpack_from("<HHBBH", raw, b+i*8) for i in range(h[1])], [
        struct.unpack_from("<BBH", raw, c+i*4) for i in range(h[2])], c+h[2]*4


def _add_soulgain_chunk(raw: bytes, donor: bytes, key: int, ap_rows, slots):
    """Append donor selector graph; preserve every existing payload/index."""
    h, first, second, third, end = _weapon_tables(raw)
    dh, df, ds, dt, _ = _weapon_tables(donor)
    p = (h[15]-h[14]) // 4
    if h[13]-h[12] != 2*(p+1) or h[14]-h[13] != 2*(p+1):
        raise ValueError("unexpected native payload sentinel layout")
    if set(SOULGAIN_KEYS) & {r[0] for r in first}:
        raise ValueError("Soulgain selectors already present")
    added = ap_rows
    if len(added) != 33:
        raise ValueError("Soulgain source span changed")
    for selector in SOULGAIN_KEYS:
        matches = [r for r in df if r[0] == selector]
        if len(matches) != 1:
            raise ValueError("donor selector is missing or ambiguous")
        _, count, start = matches[0]
        first.append((selector, count, len(second)))
        for cond_a, cond_b, variants, flags, ti in ds[start:start+count]:
            second.append((cond_a, cond_b, variants, flags, len(third)))
            for flag, length, row in dt[ti:ti+variants]:
                if row < 191 or row+(length & 15) > 224:
                    raise ValueError("donor sequence leaves verified 191..223 span")
                third.append((flag, length, p+row-191))
    first.sort(key=lambda r: r[0])
    tables = b"".join(struct.pack("<IHH", *r) for r in first)
    tables += b"".join(struct.pack("<HHBBH", *r) for r in second)
    tables += b"".join(struct.pack("<BBH", *r) for r in third)
    delta = 0x288+len(tables)-end
    # Keep all old strings, including the unused first sentinel string.
    pool = bytearray(raw[h[15]:].rstrip(b"\0") + b"\0")
    tags = bytearray(raw[h[12]:h[13]-2])
    offsets = bytearray(raw[h[13]:h[14]-2])
    voices = bytearray(raw[h[14]:h[15]])
    for pos, row in enumerate(added):
        tag = struct.unpack_from("<H", donor, dh[12]+(191+pos)*2)[0]
        tags += struct.pack("<H", (tag & 0xF800) | key)
        offsets += struct.pack("<H", len(pool))
        pool += row.text + b"\0"
        voices += struct.pack("<I", 1046000+slots[row.clip])
    tags += raw[h[13]-2:h[13]]
    offsets += raw[h[14]-2:h[14]]
    nh = h[:]
    nh[:3] = [len(first), len(second), len(third)]
    for i in range(3, 12):
        if h[i] != 0xFFFF:
            if not end <= h[i] < h[12]:
                raise ValueError("auxiliary offset outside relocatable region")
            nh[i] += delta
    nh[12] = h[12]+delta
    nh[13] = nh[12]+len(tags)
    nh[14] = nh[13]+len(offsets)
    nh[15] = nh[14]+len(voices)
    out = bytearray(raw[:0x288])
    out += tables + raw[end:h[12]] + tags + offsets + voices + pool
    if max(nh) > 0xFFFF or len(out) > len(raw):
        raise ValueError(f"0x{key:X}: rebuilt chunk exceeds native allocation")
    struct.pack_into("<16H", out, 0, *nh)
    out += b"\0"*(len(raw)-len(out))
    return bytes(out), {"old_rows": p, "added_rows": 33,
                        "table_growth": delta, "new_pool": nh[15],
                        "used_bytes": nh[15]+len(pool), "capacity": len(raw)}


def restore_soulgain(args) -> None:
    """Incremental D4/D5 restoration; never re-run the PASS35 mapper."""
    import os
    import subprocess
    import validate_axel_battle_semantic_rebalance as audit

    if args.rollback:
        raise ValueError("use the restoration preimage journal, not PASS35 rollback")
    before = sha256_file(args.iso)
    if before != SOULGAIN_SOURCE_SHA:
        raise ValueError(f"Soulgain source guard mismatch: {before}")
    if args.apply and args.expected_current_sha != before:
        raise ValueError("--apply requires the exact --expected-current-sha")
    for path, expected in [(args.baseline, EXPECTED_BASELINE_SHA256),
                           (args.aportable, EXPECTED_AP_SHA256)]:
        if sha256_file(path) != expected:
            raise ValueError(f"source hash mismatch: {path}")
    journal = json.loads(args.manifest.read_text(encoding="utf-8"))
    if "soulgain_restore" in journal:
        raise ValueError("existing restoration journal must be reviewed first")
    if args.backup.exists():
        raise ValueError("refusing to overwrite an existing rollback backup")
    slots = {int(k): v for k, v in journal["clip_slots"].items()}
    if set(slots.values()) != set(range(171)):
        raise ValueError("expected original 171-slot bank")
    d4 = {r.index: r for r in PORT.find_a_rows(args.aportable, 0xD4)}
    d5 = {r.index: r for r in PORT.find_a_rows(args.aportable, 0xD5)}
    selected = {0xD4: [d4[i] for i in SOULGAIN_D4_ROWS],
                0xD5: [d5[i] for i in range(140, 173)]}
    needed = {r.clip for rows in selected.values() for r in rows}
    missing = sorted(needed-set(slots))
    for clip in missing:
        slots[clip] = len(slots)
    # 194 is the old allocation, not an engine-wide maximum.  Grow the
    # descriptor table inside its own verified LICE-entry sector padding.
    if len(slots) >= 1000:
        raise ValueError("voice ID clip component exceeds three digits")
    chunks = PORT.load_chunks(args.runtime / "entry5_chunks.json")
    current = BB.read_entry5(args.iso)
    native = BB.read_entry5(args.baseline)
    dc = chunks[0x417]
    donor = native[dc["off"]:dc["pool"]+dc["pool_cap"]]
    ranges, chunk_stats = [], {}
    for key in (0x3F4, 0x4A4, 0x4A5, 0x521):
        c = chunks[key]
        old = current[c["off"]:c["pool"]+c["pool_cap"]]
        chosen = selected[AP_BY_SPEAKER[key][1]]
        rebuilt, info = _add_soulgain_chunk(old, donor, key, chosen, slots)
        audit.audit_soulgain_chunk(old, rebuilt, donor, key, chosen, slots)
        ranges.append((BB.BATTLE_BASE+BB.ENTRY5_OFF+c["off"], rebuilt, f"chunk-{key:X}"))
        chunk_stats[f"0x{key:X}"] = info
    ptr, stream_lo, stream_hi = PORT.og_bank_region(args.baseline)
    descriptor_base = PORT.OG_SHARED+PORT.OG_BANK_TABLE+ptr
    with args.iso.open("rb") as fh:
        fh.seek(PORT.OG_SHARED)
        shared = fh.read(PORT.OG_SHARED_SIZE)
        old_desc = shared[PORT.OG_BANK_TABLE+ptr:PORT.OG_BANK_TABLE+ptr+194*12]
        sector, size, magic = struct.unpack_from("<III", old_desc, 170*12)
        cursor = sector*2048+size
        if cursor-stream_lo != 8343552 or magic != 0x13FFF:
            raise ValueError("unexpected last occupied audio descriptor")
        fh.seek(PORT.OG_STRM+cursor)
        if any(fh.read(stream_hi-cursor)):
            raise ValueError("audio tail is not empty")
        # Repack existing ILDs without re-encoding their non-silent ADPCM.
        containers = []
        old_audio_audit = []
        for slot in range(171):
            sec, length, magic = struct.unpack_from("<III", old_desc, slot*12)
            if magic != 0x13FFF:
                raise ValueError("unexpected existing audio format")
            fh.seek(PORT.OG_STRM+sec*2048)
            original = fh.read(length)
            data_length = struct.unpack_from("<I", original, 0x1C)[0]-16
            vag = original[0x810:0x810+data_length]
            if original[:4] != b"ILD\0" or len(vag) != data_length or data_length % 16:
                raise ValueError("invalid original ILD")
            silent = 0
            for pos in range(len(vag)-16, -1, -16):
                frame = vag[pos:pos+16]
                if frame[0] >> 4 or frame[2:] != b"\0"*14 or frame[1] != 2:
                    break
                silent += 1
            cut = max(0, silent-37)*16  # preserve >=32 ms of exact silence
            kept = vag[:len(vag)-cut] if cut else vag
            container = PORT.make_ild(kept)
            if container[0x810:0x810+len(kept)] != vag[:len(kept)]:
                raise ValueError("existing voiced ADPCM changed")
            containers.append(container)
            old_audio_audit.append({"slot": slot, "removed_silent_frames": cut//16,
                                    "kept_adpcm_sha256": hashlib.sha256(kept).hexdigest().upper()})
    audio_stats = []
    for clip in missing:
        pcm = PORT.decode_atrac(args.ffmpeg, PORT.a_riff(args.aportable, clip))
        original_samples = len(pcm)//2
        samples = struct.unpack(f"<{original_samples}h", pcm)
        last = next((i for i in range(len(samples)-1, -1, -1) if samples[i]), None)
        if last is None:
            raise ValueError("unexpected silent source clip")
        # Remove only exact digital-zero tail; retain 32 ms for encoder decay.
        keep = min(original_samples, last+1+1024)
        pcm = pcm[:keep*2]
        container = PORT.make_ild(PORT.encode_psx_adpcm(pcm))
        containers.append(container)
        audio_stats.append({"clip": clip, "slot": slots[clip],
                            "source_samples": original_samples, "kept_samples": keep,
                            "trimmed_zero_samples": original_samples-keep,
                            "length": len(container),
                            "sha256": hashlib.sha256(container).hexdigest().upper()})
        print(f"Soulgain audio {clip}: {len(container)} bytes", flush=True)
    cursor = stream_lo
    descriptors = bytearray()
    for container in containers:
        descriptors += struct.pack("<III", cursor//2048, len(container), 0x13FFF)
        cursor += len(container)
    if cursor > stream_hi:
        raise ValueError(f"new audio exceeds allocation by {cursor-stream_hi}")
    bank_table = PORT.OG_BANK_TABLE
    count = struct.unpack_from("<I", shared, 0xD0804)[0]
    if count != 1300 or shared[0xD0000:0xD0004] != b"Wpbb":
        raise ValueError("unexpected SSTM directory")
    records = [struct.unpack_from("<II", shared, bank_table+i*8) for i in range(count)]
    old_end = max(bank_table+q+n*12 for q,n in records if n and q != 0xFFFFFFFF)
    entry_size = struct.unpack_from("<I", shared, 0xD000C)[0]
    if old_end != 0xD0800+entry_size or old_end != 0x11D5BC:
        raise ValueError("SSTM nested entry size does not match descriptor end")
    tail = bank_table+ptr+194*12
    growth = len(descriptors)-194*12
    if growth < 0 or old_end+growth > 0x11D800 or any(shared[old_end:old_end+growth]):
        raise ValueError("no verified SSTM padding for expanded descriptors")
    rebuilt_shared = bytearray(shared)
    rebuilt_shared[bank_table+ptr:old_end+growth] = descriptors+shared[tail:old_end]
    for i,(q,n) in enumerate(records):
        if i == 1046:
            struct.pack_into("<II", rebuilt_shared, bank_table+i*8, q, len(slots))
        elif n and bank_table+q >= tail:
            struct.pack_into("<I", rebuilt_shared, bank_table+i*8, q+growth)
    struct.pack_into("<I", rebuilt_shared, 0xD000C, entry_size+growth)
    # Every other bank must resolve to the exact same descriptor bytes.
    for i,(q,n) in enumerate(records):
        nq,nn = struct.unpack_from("<II", rebuilt_shared, bank_table+i*8)
        if i != 1046 and (nn != n or (n and shared[bank_table+q:bank_table+q+n*12] !=
                                     rebuilt_shared[bank_table+nq:bank_table+nq+n*12])):
            raise ValueError(f"other bank {i} changed")
    ranges += [(PORT.OG_SHARED+0xD000C, bytes(rebuilt_shared[0xD000C:0xD0010]), "sstm-size"),
               (PORT.OG_SHARED+bank_table, bytes(rebuilt_shared[bank_table:old_end+growth]), "sstm-descriptors"),
               (PORT.OG_STRM+stream_lo, b"".join(containers)+b"\0"*(stream_hi-cursor), "audio-bank")]
    ranges.sort(key=lambda r: r[0])
    for a, b in zip(ranges, ranges[1:]):
        if a[0]+len(a[1]) > b[0]:
            raise ValueError("overlapping restoration writes")
    result = {"kind": "D4/D5 Soulgain native weapon graph restoration", "state": "planned",
              "before_sha256": before, "target": str(args.iso.resolve()),
              "scope": ["0x3F4", "0x4A4", "0x4A5", "0x521"], "selectors": list(SOULGAIN_KEYS),
              "chunks": chunk_stats, "clips_added": missing, "total_clips": len(slots),
              "audio_used_bytes": cursor-stream_lo, "audio_free_bytes": stream_hi-cursor,
              "descriptor_growth": growth, "existing_audio_preservation": old_audio_audit,
              "d4_source_rows": list(SOULGAIN_D4_ROWS), "d5_source_rows": list(range(140,173)),
              "audio": audio_stats, "clip_slots": {str(k): v for k, v in slots.items()},
              "live_verified": False}
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not args.apply:
        report["soulgain_restore"] = result
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    processes = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True)
    if processes.returncode or b"pcsx2" in processes.stdout.lower():
        raise ValueError("PCSX2 process check failed or emulator is still running")
    if sha256_file(args.iso) != before:
        raise ValueError("target changed while building")
    backup, metadata = bytearray(), []
    with args.iso.open("r+b") as fh:
        for off, data, kind in ranges:
            fh.seek(off)
            old = fh.read(len(data))
            if len(old) != len(data):
                raise ValueError("short preimage")
            metadata.append({"offset": off, "length": len(data), "kind": kind,
                             "backup_pos": len(backup),
                             "old_sha256": hashlib.sha256(old).hexdigest().upper(),
                             "new_sha256": hashlib.sha256(data).hexdigest().upper()})
            backup += old
        args.backup.write_bytes(backup)
        result.update(state="prepared", ranges=metadata, backup=str(args.backup.resolve()),
                      backup_sha256=hashlib.sha256(backup).hexdigest().upper())
        journal["soulgain_restore"] = result
        args.manifest.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            for off, data, _ in ranges:
                fh.seek(off)
                fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
            for off, data, _ in ranges:
                fh.seek(off)
                if fh.read(len(data)) != data:
                    raise ValueError("write verification mismatch")
            # Replacing exactly the allowed ranges by their preimages must
            # reconstruct the previous full ISO hash (all other bytes unchanged).
            restored_hash = audit.soulgain_preimage_hash(args.iso, metadata, backup)
            if restored_hash != before:
                raise ValueError("bytes outside the allowed patch ranges changed")
            post = BB.read_entry5(args.iso)
            for key in (0x3F4, 0x4A4, 0x4A5, 0x521):
                c = chunks[key]; start, end = c["off"], c["pool"]+c["pool_cap"]
                audit.audit_soulgain_chunk(current[start:end], post[start:end], donor,
                                          key, selected[AP_BY_SPEAKER[key][1]], slots)
        except BaseException:
            for item in metadata:
                fh.seek(item["offset"])
                pos = item["backup_pos"]
                fh.write(backup[pos:pos+item["length"]])
            fh.flush()
            os.fsync(fh.fileno())
            result["state"] = "rolled_back_after_error"
            args.manifest.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
            if sha256_file(args.iso) != before:
                raise RuntimeError("automatic rollback hash mismatch")
            raise
    result.update(state="applied", after_sha256=sha256_file(args.iso),
                  outside_ranges_unchanged=True)
    args.manifest.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
    report["soulgain_restore"] = result
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


VAISAGA_SOURCE_SHA = "738C6F9B9D365204F75B4CF0CC50BAB57F69EDDA92A54FCA152872925D207B8B"
VAISAGA_KEYS = (50000, 50010, 50011, 50020, 50030, 50031, 50040, 50041)


def _ap_weapon_donor(iso, personality):
    # These are the complete original AP D4/D5 chunks, not a guessed f1 array.
    relative = {0xD4: 0x7C2800, 0xD5: 0x7C4000}[personality]
    with iso.open("rb") as fh:
        fh.seek(PORT.AP_DUMMY+relative)
        raw = fh.read(0x1800)
    h = struct.unpack_from("<16H", raw)
    if struct.unpack_from("<H", raw, h[12])[0] & 0x7FF != personality:
        raise ValueError("AP donor identity mismatch")
    return raw


def _restore_vaisaga_chunk(raw, donor, speaker, rows, slots):
    h, first, second, third, end = _weapon_tables(raw)
    dh, df, ds, dt, _ = _weapon_tables(donor)
    p = (h[15]-h[14])//4
    if h[13]-h[12] != 2*(p+1) or h[14]-h[13] != 2*(p+1):
        raise ValueError("unexpected OGs sentinel layout")
    source_start = rows[0].index
    source_end = rows[-1].index+1
    changed = []
    for i,(key,_,_) in enumerate(first):
        if key not in VAISAGA_KEYS:
            continue
        matches = [r for r in df if r[0] == key+214000]
        if len(matches) != 1:
            raise ValueError("missing AP Vaisaga selector")
        _, count, start = matches[0]
        first[i] = (key, count, len(second))
        for ca,cb,variants,flags,ti in ds[start:start+count]:
            second.append((ca,cb,variants,flags,len(third)))
            for flag,plen,row in dt[ti:ti+(variants & 127)]:
                if not source_start <= row < row+(plen & 15) <= source_end:
                    raise ValueError("AP sequence leaves audited Vaisaga span")
                third.append((flag,plen,p+row-source_start))
        changed.append(key)
    if set(changed) != set(VAISAGA_KEYS):
        raise ValueError("current player chunk lacks native Vaisaga keys")
    tables = b"".join(struct.pack("<IHH", *r) for r in first)
    tables += b"".join(struct.pack("<HHBBH", *r) for r in second)
    tables += b"".join(struct.pack("<BBH", *r) for r in third)
    delta = 0x288+len(tables)-end
    pool = bytearray(raw[h[15]:].rstrip(b"\0")+b"\0")
    tags = bytearray(raw[h[12]:h[13]-2])
    strings = bytearray(raw[h[13]:h[14]-2])
    voices = bytearray(raw[h[14]:h[15]])
    for row in rows:
        tag = struct.unpack_from("<H", donor, dh[12]+row.index*2)[0]
        tags += struct.pack("<H", (tag & 0xF800)|speaker)
        strings += struct.pack("<H", len(pool))
        pool += row.text+b"\0"
        voices += struct.pack("<I", 1046000+slots[row.clip])
    tags += raw[h[13]-2:h[13]]
    strings += raw[h[14]-2:h[14]]
    nh = h[:]
    nh[:3] = [len(first),len(second),len(third)]
    for i in range(3,12):
        if h[i] != 0xFFFF:
            if not end <= h[i] < h[12]:
                raise ValueError("auxiliary pointer out of range")
            nh[i] += delta
    nh[12] = h[12]+delta
    nh[13] = nh[12]+len(tags)
    nh[14] = nh[13]+len(strings)
    nh[15] = nh[14]+len(voices)
    out = bytearray(raw[:0x288])+tables+raw[end:h[12]]+tags+strings+voices+pool
    used = len(out)
    if used > len(raw) or max(nh) > 65535:
        raise ValueError("Vaisaga chunk exceeds its original allocation")
    struct.pack_into("<16H", out, 0, *nh)
    out += b"\0"*(len(raw)-used)
    return bytes(out), {"old_rows":p,"added_rows":len(rows),"used_bytes":used,
                        "capacity":len(raw),"table_growth":delta}


def restore_vaisaga(args):
    import os
    import subprocess
    import validate_axel_battle_semantic_rebalance as audit
    if args.rollback:
        raise ValueError("use the Vaisaga preimage journal, not legacy rollback")
    before = sha256_file(args.iso)
    if before != VAISAGA_SOURCE_SHA or (args.apply and args.expected_current_sha != before):
        raise ValueError(f"Vaisaga source guard mismatch: {before}")
    if sha256_file(args.aportable) != EXPECTED_AP_SHA256:
        raise ValueError("AP source hash mismatch")
    journal = json.loads(args.manifest.read_text(encoding="utf-8"))
    prior=journal.get("soulgain_restore",{})
    followup=json.loads((args.runtime/"mustache_axel_lamia_20261024.json").read_text(encoding="utf-8"))
    if prior.get("after_sha256")!=followup.get("before_sha256") or followup.get("after_sha256")!=before:
        raise ValueError("required Soulgain + dialogue follow-up chain not found")
    followup_preimage=bytearray();followup_ranges=[]
    with args.iso.open("rb") as fh:
        for r in prior["ranges"]:
            fh.seek(r["offset"])
            if hashlib.sha256(fh.read(r["length"])).hexdigest().upper()!=r["new_sha256"]:
                raise ValueError("Soulgain patch region changed")
        for e in sorted(followup["edits"],key=lambda x:int(x["iso_off"],16)):
            off=int(e["iso_off"],16);old=bytes.fromhex(e["before_hex"]);new=bytes.fromhex(e["after_hex"])
            fh.seek(off)
            if len(old)!=len(new) or fh.read(len(new))!=new:raise ValueError("dialogue follow-up bytes mismatch")
            followup_ranges.append({"offset":off,"length":len(old),"backup_pos":len(followup_preimage)})
            followup_preimage+=old
    if audit.soulgain_preimage_hash(args.iso,followup_ranges,followup_preimage)!=prior["after_sha256"]:
        raise ValueError("unexpected changes beyond recorded dialogue follow-up")
    if "vaisaga_restore" in journal or args.backup.exists():
        raise ValueError("refusing to overwrite an existing restoration/backup")
    slots = {int(k):v for k,v in journal["soulgain_restore"]["clip_slots"].items()}
    if set(slots.values()) != set(range(203)):
        raise ValueError("unexpected prior audio slots")
    sources, donors = {}, {}
    for personality,lo,hi in [(0xD4,92,107),(0xD5,130,140)]:
        sources[personality] = [r for r in PORT.find_a_rows(args.aportable,personality) if lo <= r.index < hi]
        donors[personality] = _ap_weapon_donor(args.aportable,personality)
    needed = {r.clip for rows in sources.values() for r in rows}
    missing = sorted(needed-set(slots))
    if missing != [55,56,57,58,167,168,169,174]:
        raise ValueError("unexpected new Vaisaga clips")
    for clip in missing:
        slots[clip] = len(slots)
    chunks = PORT.load_chunks(args.runtime/"entry5_chunks.json")
    current = BB.read_entry5(args.iso)
    ranges, chunk_stats = [], {}
    for key in (0x3F4,0x4A4,0x4A5,0x521):
        c = chunks[key]; personality = AP_BY_SPEAKER[key][1]
        raw = current[c["off"]:c["pool"]+c["pool_cap"]]
        out, info = _restore_vaisaga_chunk(raw,donors[personality],key,sources[personality],slots)
        audit.audit_vaisaga_chunk(raw,out,donors[personality],key,sources[personality],slots)
        ranges.append((BB.BATTLE_BASE+BB.ENTRY5_OFF+c["off"],out,f"chunk-{key:X}"))
        chunk_stats[f"0x{key:X}"] = info
    with args.iso.open("rb") as fh:
        fh.seek(PORT.OG_SHARED);shared=fh.read(PORT.OG_SHARED_SIZE)
        b=PORT.OG_BANK_TABLE
        ptr,n=struct.unpack_from("<II",shared,b+1046*8)
        if n!=203:
            raise ValueError("expected 203-clip Soulgain bank")
        first_sector=struct.unpack_from("<I",shared,b+ptr)[0]
        stream_lo=first_sector*2048
        stream_hi=stream_lo+8955904
        containers=[];preserved=[]
        for slot in range(n):
            sec,length,magic=struct.unpack_from("<III",shared,b+ptr+12*slot)
            if magic!=0x13FFF:
                raise ValueError("unknown voice container")
            fh.seek(PORT.OG_STRM+sec*2048);old=fh.read(length)
            ln=struct.unpack_from("<I",old,0x1C)[0]-16
            vag=old[0x810:0x810+ln]
            if old[:4]!=b"ILD\0" or len(vag)!=ln or ln%16:
                raise ValueError("bad original voice length")
            def zero(frame):
                return frame[0]>>4==0 and frame[1]==2 and frame[2:]==b"\0"*14
            head=tail=0
            for pos in range(0,ln,16):
                if not zero(vag[pos:pos+16]):break
                head+=1
            for pos in range(ln-16,-1,-16):
                if not zero(vag[pos:pos+16]):break
                tail+=1
            left=max(0,head-19)*16;right=ln-max(0,tail-19)*16
            if left>=right:
                raise ValueError("unexpected silent voice")
            kept=vag[left:right]
            containers.append(PORT.make_ild(kept))
            preserved.append({"slot":slot,"removed_head_frames":left//16,
                              "removed_tail_frames":(ln-right)//16,
                              "voiced_adpcm_sha256":hashlib.sha256(kept).hexdigest().upper()})
    new_audio=[]
    for clip in missing:
        pcm=PORT.decode_atrac(args.ffmpeg,PORT.a_riff(args.aportable,clip))
        samples=struct.unpack(f"<{len(pcm)//2}h",pcm)
        positions=[i for i,v in enumerate(samples) if v]
        start=max(0,positions[0]-512);stop=min(len(samples),positions[-1]+1+512)
        container=PORT.make_ild(PORT.encode_psx_adpcm(pcm[start*2:stop*2]))
        containers.append(container)
        new_audio.append({"clip":clip,"slot":slots[clip],"source_samples":len(samples),
                          "removed_zero_head_samples":start,"removed_zero_tail_samples":len(samples)-stop,
                          "length":len(container),"sha256":hashlib.sha256(container).hexdigest().upper()})
        print(f"Vaisaga audio {clip}: {len(container)} bytes",flush=True)
    cursor=stream_lo;desc=bytearray()
    for container in containers:
        desc+=struct.pack("<III",cursor//2048,len(container),0x13FFF)
        cursor+=len(container)
    if cursor>stream_hi:
        raise ValueError("Vaisaga audio does not fit original bank")
    recs=[struct.unpack_from("<II",shared,b+i*8) for i in range(1300)]
    end=max(b+q+c*12 for q,c in recs if c and q!=0xFFFFFFFF)
    old_size=struct.unpack_from("<I",shared,0xD000C)[0]
    if end!=0x11D628 or 0xD0800+old_size!=end:
        raise ValueError("SSTM extent guard mismatch")
    tail=b+ptr+n*12;growth=len(desc)-n*12
    if end+growth>0x11D800 or any(shared[end:end+growth]):
        raise ValueError("insufficient SSTM padding")
    ns=bytearray(shared);ns[b+ptr:end+growth]=desc+shared[tail:end]
    for bank,(q,c) in enumerate(recs):
        if bank==1046:struct.pack_into("<II",ns,b+bank*8,q,len(slots))
        elif c and b+q>=tail:struct.pack_into("<I",ns,b+bank*8,q+growth)
    struct.pack_into("<I",ns,0xD000C,old_size+growth)
    for bank,(q,c) in enumerate(recs):
        nq,nc=struct.unpack_from("<II",ns,b+bank*8)
        if bank!=1046 and (nc!=c or (c and shared[b+q:b+q+c*12]!=ns[b+nq:b+nq+nc*12])):
            raise ValueError("unrelated voice bank modified")
    ranges += [(PORT.OG_SHARED+0xD000C,bytes(ns[0xD000C:0xD0010]),"sstm-size"),
               (PORT.OG_SHARED+b,bytes(ns[b:end+growth]),"sstm-descriptors"),
               (PORT.OG_STRM+stream_lo,b"".join(containers)+b"\0"*(stream_hi-cursor),"audio-bank")]
    ranges.sort(key=lambda r:r[0])
    for a,z in zip(ranges,ranges[1:]):
        if a[0]+len(a[1])>z[0]:raise ValueError("overlapping writes")
    result={"kind":"AP D4/D5 Vaisaga weapon graph restoration","state":"planned",
            "target":str(args.iso.resolve()),"before_sha256":before,"chunks":chunk_stats,
            "clips_added":missing,"total_clips":len(slots),"clip_slots":{str(k):v for k,v in slots.items()},
            "audio":new_audio,"existing_audio_preservation":preserved,"audio_free_bytes":stream_hi-cursor,
            "descriptor_growth":growth,"live_verified":False}
    report=json.loads(args.report.read_text(encoding="utf-8"))
    if not args.apply:
        report["vaisaga_restore"]=result
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({k:v for k,v in result.items() if k not in ("existing_audio_preservation","clip_slots")},ensure_ascii=False,indent=2))
        return
    check=subprocess.run(["tasklist","/FO","CSV","/NH"],capture_output=True)
    if check.returncode or b"pcsx2" in check.stdout.lower():raise ValueError("PCSX2 still running or check failed")
    if sha256_file(args.iso)!=before:raise ValueError("target changed while building")
    backup=bytearray();metadata=[]
    with args.iso.open("r+b") as fh:
        for off,data,kind in ranges:
            fh.seek(off);old=fh.read(len(data))
            if len(old)!=len(data):raise ValueError("short preimage")
            metadata.append({"offset":off,"length":len(data),"kind":kind,"backup_pos":len(backup),
                             "old_sha256":hashlib.sha256(old).hexdigest().upper(),"new_sha256":hashlib.sha256(data).hexdigest().upper()})
            backup+=old
        args.backup.write_bytes(backup)
        result.update(state="prepared",ranges=metadata,backup=str(args.backup.resolve()),backup_sha256=hashlib.sha256(backup).hexdigest().upper())
        journal["vaisaga_restore"]=result
        args.manifest.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
        try:
            for off,data,_ in ranges:fh.seek(off);fh.write(data)
            fh.flush();os.fsync(fh.fileno())
            for off,data,_ in ranges:
                fh.seek(off)
                if fh.read(len(data))!=data:raise ValueError("readback mismatch")
            if audit.soulgain_preimage_hash(args.iso,metadata,backup)!=before:raise ValueError("out-of-scope change")
            post=BB.read_entry5(args.iso)
            for key in (0x3F4,0x4A4,0x4A5,0x521):
                c=chunks[key];lo,hi=c["off"],c["pool"]+c["pool_cap"];personality=AP_BY_SPEAKER[key][1]
                audit.audit_vaisaga_chunk(current[lo:hi],post[lo:hi],donors[personality],key,sources[personality],slots)
        except BaseException:
            for r in metadata:fh.seek(r["offset"]);fh.write(backup[r["backup_pos"]:r["backup_pos"]+r["length"]])
            fh.flush();os.fsync(fh.fileno());result["state"]="rolled_back_after_error"
            args.manifest.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
            if sha256_file(args.iso)!=before:raise RuntimeError("rollback failed")
            raise
    result.update(state="applied",after_sha256=sha256_file(args.iso),outside_ranges_unchanged=True)
    journal["vaisaga_restore"]=result;report["vaisaga_restore"]=result
    args.manifest.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("existing_audio_preservation","clip_slots")},ensure_ascii=False,indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--aportable", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, default=Path(
        r"C:/Users/OXP2/LaunchBox/ThirdParty/FFMPEG/ffmpeg.exe"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore-soulgain", action="store_true",
                        help="Incrementally add D4/D5 Soulgain selectors/audio to current release")
    parser.add_argument("--restore-vaisaga", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--expected-current-sha")
    parser.add_argument("--expected-rollback-sha")
    args = parser.parse_args()

    if args.restore_vaisaga:
        if args.restore_soulgain:
            raise ValueError("choose one incremental restoration mode")
        restore_vaisaga(args)
        return

    if args.restore_soulgain:
        restore_soulgain(args)
        return
    if args.manifest.exists():
        existing = json.loads(args.manifest.read_text(encoding="utf-8"))
        if existing.get("soulgain_restore", {}).get("state") == "applied":
            raise ValueError("Soulgain restoration is active: the legacy PASS35 builder/rollback "
                             "must not overwrite the expanded layout. Use its restoration journal.")

    if args.rollback:
        if not args.expected_current_sha or not args.expected_rollback_sha:
            raise ValueError(
                "--rollback requires --expected-current-sha and "
                "--expected-rollback-sha")
        expected_current = args.expected_current_sha.upper()
        expected_rollback = args.expected_rollback_sha.upper()
        actual_current = sha256_file(args.iso)
        if actual_current != expected_current:
            raise ValueError(
                f"rollback source SHA mismatch: {actual_current} != "
                f"{expected_current}")

        journal = json.loads(args.manifest.read_text(encoding="utf-8"))
        backup = args.backup.read_bytes()
        actual_backup = hashlib.sha256(backup).hexdigest().upper()
        if actual_backup != journal["backup_sha256"]:
            raise ValueError(
                f"rollback backup SHA mismatch: {actual_backup} != "
                f"{journal['backup_sha256']}")

        forward: list[bytes] = []
        with args.iso.open("r+b") as fh:
            for item in journal["ranges"]:
                fh.seek(item["offset"])
                current = fh.read(item["length"])
                if len(current) != item["length"]:
                    raise ValueError(
                        f"short rollback preimage read at 0x{item['offset']:X}")
                forward.append(current)
            try:
                for item in journal["ranges"]:
                    start = item["backup_pos"]
                    fh.seek(item["offset"])
                    fh.write(backup[start:start + item["length"]])
                fh.flush()
                actual_rollback = sha256_file(args.iso)
                if actual_rollback != expected_rollback:
                    raise ValueError(
                        f"rollback target SHA mismatch: {actual_rollback} != "
                        f"{expected_rollback}")
            except BaseException:
                for item, current in zip(journal["ranges"], forward):
                    fh.seek(item["offset"])
                    fh.write(current)
                fh.flush()
                restored = sha256_file(args.iso)
                if restored != expected_current:
                    raise RuntimeError(
                        f"rollback failed and forward restore SHA mismatch: "
                        f"{restored} != {expected_current}")
                raise
        print(json.dumps({
            "kind": "Axel battle rebuild transactional rollback",
            "target": str(args.iso.resolve()),
            "before_sha256": actual_current,
            "after_sha256": expected_rollback,
            "backup_sha256": actual_backup,
            "ranges": len(journal["ranges"]),
        }, ensure_ascii=False, indent=2))
        return

    if args.iso.stat().st_size != EXPECTED_OGS_SIZE:
        raise ValueError(
            f"target ISO size {args.iso.stat().st_size} != {EXPECTED_OGS_SIZE}")
    before_sha256 = sha256_file(args.iso)
    if args.apply:
        if not args.expected_current_sha:
            raise ValueError("--apply requires --expected-current-sha")
        expected_current = args.expected_current_sha.upper()
        if before_sha256 != expected_current:
            raise ValueError(
                f"apply source SHA mismatch: {before_sha256} != "
                f"{expected_current}")
        if args.baseline.stat().st_size != EXPECTED_OGS_SIZE:
            raise ValueError("baseline ISO size mismatch")
        baseline_sha = sha256_file(args.baseline)
        if baseline_sha != EXPECTED_BASELINE_SHA256:
            raise ValueError(
                f"baseline SHA mismatch: {baseline_sha} != "
                f"{EXPECTED_BASELINE_SHA256}")
        if args.aportable.stat().st_size != EXPECTED_AP_SIZE:
            raise ValueError("AP Portable ISO size mismatch")
        ap_sha = sha256_file(args.aportable)
        if ap_sha != EXPECTED_AP_SHA256:
            raise ValueError(
                f"AP Portable SHA mismatch: {ap_sha} != {EXPECTED_AP_SHA256}")
        for name, expected_sha in EXPECTED_RUNTIME_SHA256.items():
            source_sha = sha256_file(args.runtime / name)
            if source_sha != expected_sha:
                raise ValueError(
                    f"{name} SHA mismatch: {source_sha} != {expected_sha}")

    current = current_pass33_clips(args.runtime)
    if len(current) != 181:
        raise ValueError(f"expected PASS33 181-clip base, found {len(current)}")
    allowed = (current - DROP_CLIPS) | ADD_CLIPS | EXTRA_GENERIC_CLIPS

    chunks = PORT.load_chunks(args.runtime / "entry5_chunks.json")
    native_entry = BB.read_entry5(args.baseline)
    mapping = make_mapping(native_entry, chunks, args.runtime, allowed)
    stats = mapping_stats(mapping)
    if (stats["relationship_leaks"] or stats["weapon_mismatches"]
            or stats["pure_shout_weapon"] or stats["cue_opposites"]
            or stats["selector_cross_repeats"]
            or stats["critical_group_errors"]
            or stats["recovered_native_rows"] != 7
            or stats["mixed_speaker_rows"] != 16):
        raise ValueError(
            f"semantic validation failed: relation={len(stats['relationship_leaks'])}, "
            f"weapon={len(stats['weapon_mismatches'])}, "
            f"pure_shout={len(stats['pure_shout_weapon'])}, "
            f"cue_opposites={len(stats['cue_opposites'])}, "
            f"selector_cross={len(stats['selector_cross_repeats'])}, "
            f"critical_groups={len(stats['critical_group_errors'])}, "
            f"recovered={stats['recovered_native_rows']}, "
            f"mixed={stats['mixed_speaker_rows']}")

    used = sorted({row["voice"] % 1000 for rows in mapping.values()
                   for row in rows if row["voice"]})
    clips = used
    if len(clips) > PORT.OG_BANK_CAPACITY:
        raise ValueError(f"selected clips {len(clips)} > {PORT.OG_BANK_CAPACITY}")
    clip_slots = {clip: i for i, clip in enumerate(clips)}
    for rows in mapping.values():
        for row in rows:
            row["slot"] = None if not row["voice"] else clip_slots[row["clip"]]
    chunk_ranges: list[tuple[int, bytes, str]] = []
    base = BB.BATTLE_BASE + BB.ENTRY5_OFF
    pool_usage = {}
    for key, rows in mapping.items():
        writes, used_pool = build_chunk(native_entry, chunks[key], key, rows, clip_slots)
        for off, data in writes:
            chunk_ranges.append((base + off, data, f"battle-0x{key:X}"))
        pool_usage[f"0x{key:X}"] = {
            "rows": len(rows),
            "physical_capacity": chunks[key]["n"],
            "pool_used": used_pool,
            "pool_capacity": chunks[key]["pool_cap"],
        }

    ptr, stream_lo, stream_hi = PORT.og_bank_region(args.baseline)
    estimated = sum(estimated_ild_size(args.aportable, clip) for clip in clips)
    if estimated > stream_hi - stream_lo:
        raise ValueError(f"estimated audio {estimated} > {stream_hi - stream_lo}")

    summary = {
        "kind": "PASS35 native selector restoration and safe AP Axel payload rebuild",
        "target": str(args.iso.resolve()),
        "applied": bool(args.apply),
        "before_sha256": before_sha256,
        "old_live_rows": {"0x3F4": 290, "0x4A4": 294, "0x4A5": 259, "0x521": 249},
        "restored": pool_usage,
        "retired_short_clips": sorted(DROP_CLIPS),
        "added_context_clips": sorted(ADD_CLIPS | EXTRA_GENERIC_CLIPS),
        "available_candidate_clips": len(allowed),
        "bank_clips": len(clips),
        "mapped_used_clips": len(used),
        "estimated_audio_bytes": estimated,
        "audio_capacity_bytes": stream_hi - stream_lo,
        "stats": stats,
    }
    if not args.apply:
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    containers = []
    for position, clip in enumerate(clips, 1):
        pcm = PORT.decode_atrac(args.ffmpeg, PORT.a_riff(args.aportable, clip))
        containers.append(PORT.make_ild(PORT.encode_psx_adpcm(pcm)))
        if position % 25 == 0 or position == len(clips):
            print(f"  audio encode {position}/{len(clips)}")
    packed = b"".join(containers)
    if len(packed) > stream_hi - stream_lo:
        raise ValueError(f"encoded audio {len(packed)} > {stream_hi - stream_lo}")

    descriptors = bytearray()
    cursor = stream_lo
    for container in containers:
        descriptors += struct.pack("<III", cursor // PORT.SECTOR, len(container), 0x13FFF)
        cursor += len(container)
    first_descriptor = bytes(descriptors[:12])
    while len(descriptors) < PORT.OG_BANK_CAPACITY * 12:
        descriptors += first_descriptor
    audio_ranges = [
        (PORT.OG_SHARED + PORT.OG_BANK_TABLE + ptr, bytes(descriptors), "descriptors"),
        (PORT.OG_STRM + stream_lo,
         packed + b"\0" * ((stream_hi - stream_lo) - len(packed)), "strm"),
    ]
    ranges = chunk_ranges + audio_ranges
    ordered_ranges = sorted(ranges, key=lambda item: item[0])
    for previous, current_range in zip(ordered_ranges, ordered_ranges[1:]):
        previous_end = previous[0] + len(previous[1])
        if previous_end > current_range[0]:
            raise ValueError(
                f"overlapping writes 0x{previous[0]:X}..0x{previous_end:X} "
                f"and 0x{current_range[0]:X}")
    for off, data, kind in ranges:
        if off < 0 or off + len(data) > EXPECTED_OGS_SIZE:
            raise ValueError(f"{kind} write lies outside target ISO")
    # Audio encoding can take minutes.  Recheck immediately before collecting
    # the preimage so a concurrently replaced CURRENT ISO is never patched.
    prewrite_sha256 = sha256_file(args.iso)
    if prewrite_sha256 != before_sha256:
        raise ValueError(
            f"target changed during build: {prewrite_sha256} != "
            f"{before_sha256}")

    backup = bytearray()
    metadata = []
    with args.iso.open("r+b") as fh:
        for off, data, kind in ranges:
            fh.seek(off)
            old = fh.read(len(data))
            if len(old) != len(data):
                raise ValueError(f"short preimage read at 0x{off:X}")
            metadata.append({
                "offset": off, "length": len(data),
                "backup_pos": len(backup), "kind": kind,
                "old_sha256": hashlib.sha256(old).hexdigest().upper(),
                "new_sha256": hashlib.sha256(data).hexdigest().upper(),
            })
            backup += old
        args.backup.parent.mkdir(parents=True, exist_ok=True)
        args.backup.write_bytes(bytes(backup))
        backup_sha256 = hashlib.sha256(backup).hexdigest().upper()
        journal = {
            "kind": "PASS35 Axel battle safe rebuild rollback journal",
            "state": "prepared",
            "target": str(args.iso.resolve()),
            "before_sha256": before_sha256,
            "ranges": metadata,
            "backup": str(args.backup.resolve()),
            "backup_sha256": backup_sha256,
            "clip_slots": {str(k): v for k, v in clip_slots.items()},
            "ap_source_sha256": {
                "D4": hashlib.sha256(
                    (args.runtime / "apD4.json").read_bytes()
                ).hexdigest().upper(),
                "D5": hashlib.sha256(
                    (args.runtime / "apD5.json").read_bytes()
                ).hexdigest().upper(),
            },
            "payload_mapping": {
                f"0x{key:X}": rows for key, rows in mapping.items()
            },
        }
        # Persist the complete rollback journal before the first ISO write, so
        # an interrupted encode/apply still leaves an exact recovery path.
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(journal, ensure_ascii=False, indent=2),
            encoding="utf-8")
        try:
            for off, data, _kind in ranges:
                fh.seek(off)
                fh.write(data)
            fh.flush()
            validate_written(args.iso, native_entry, chunks, mapping, clip_slots)
        except BaseException:
            for item in metadata:
                fh.seek(item["offset"])
                start = item["backup_pos"]
                fh.write(backup[start:start + item["length"]])
            fh.flush()
            journal["state"] = "rolled_back_after_error"
            restored_sha256 = sha256_file(args.iso)
            journal["restored_sha256"] = restored_sha256
            args.manifest.write_text(
                json.dumps(journal, ensure_ascii=False, indent=2),
                encoding="utf-8")
            if restored_sha256 != before_sha256:
                raise RuntimeError(
                    f"automatic rollback SHA mismatch: {restored_sha256} != "
                    f"{before_sha256}")
            raise

    after_sha256 = sha256_file(args.iso)
    summary.update({
        "applied": True,
        "audio_bytes": len(packed),
        "audio_free_bytes": stream_hi - stream_lo - len(packed),
        "backup": str(args.backup.resolve()),
        "backup_sha256": backup_sha256,
        "sha256": after_sha256,
    })
    journal["state"] = "applied"
    journal["after_sha256"] = after_sha256
    args.manifest.write_text(
        json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
