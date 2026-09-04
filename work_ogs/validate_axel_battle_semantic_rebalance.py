# -*- coding: utf-8 -*-
"""Standalone audit for the safe player-Axel battle subtitle rebuild.

This validator intentionally does not call the builder or any of its parsing,
mapping, or audio helpers.  It reconstructs the four native chunk layouts from
fixed, independently audited constants, compares the complete selector/tag
prefixes with the pristine baseline, checks every physical payload against the
persisted provenance manifest and AP source JSON, and validates the PTbl/Plot
identity and transplanted ILD/PSX-ADPCM bank directly from the ISO.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

from ogs_korean_codec import decode


ISO_SIZE = 4_518_150_144
BASELINE_SHA256 = "9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C"
EXPECTED_BEFORE_SHA256 = "79A812BDC3D5FD467BCCDBEC3DAACB7CCC24A74BDD3CEA836EDD16F0C63B9924"
EXPECTED_MASKED_SHA256 = "CB3B9FB227B49843A655B005FFFFB46B399C12DA88087201D7138D2A68A8A13F"
AP_SOURCE_SHA256 = {
    "D4": "5FB0E1CC788D5F2A21B38417B8D3C95C889B0619B79236153FDEF8EDC595B711",
    "D5": "2E9A26251E11A6E53923A9EFA72A8136F8323D5B0392CA47C266C22185295FE7",
}
ENTRY5_CHUNKS_SHA256 = "329FFDF2CF6CBD4BF1D8F3332885F33CDB6971F12B7C3B65B717AB7878B9DC5A"

DROP_CLIPS = {137, 149, 151, 152}
ADD_CLIPS = {
    65, 66, 67, 69, 128, 163, 170, 188, 194, 197, 200, 201, 207,
    210, 215, 223, 230,
}
EXTRA_GENERIC_CLIPS = {
    46, 70, 72, 75, 77, 83, 95, 100, 103, 104, 105, 161, 172,
    192, 198, 213, 218, 235,
}

ENTRY_BASE = 0x8574E000
ENTRY_SIZE = 0x2A8000

# off, N, f2, f3, f4, pool, pool capacity -- all entry-relative.
CHUNKS = {
    0x3F4: dict(off=1_097_728, n=368, f2=1_101_256, f3=1_101_992,
                f4=1_102_728, pool=1_104_196, pool_cap=7_868),
    0x4A4: dict(off=2_228_224, n=472, f2=2_232_356, f3=2_233_300,
                f4=2_234_244, pool=2_236_128, pool_cap=10_528),
    0x4A5: dict(off=2_246_656, n=626, f2=2_251_244, f3=2_252_496,
                f4=2_253_748, pool=2_256_248, pool_cap=12_936),
    0x521: dict(off=2_772_992, n=362, f2=2_776_432, f3=2_777_156,
                f4=2_777_880, pool=2_779_324, pool_cap=5_956),
}

PREFIX_SHA256 = {
    0x3F4: "98A650D22249E9741CF9D9722E6076BAA0A00E7424B29FB2F9578EC44E7B6570",
    0x4A4: "B9930426184F9BDC3AA341405AA818706EA0BA412C00BFEDE2C828F4CB7494E8",
    0x4A5: "3F7E8FA6BD1EAA1CE4A1C55918547CD2F233E54148EEA38D89497E4F6EB549C2",
    0x521: "B0135AE303C0BFA1F93D82B7CE86E30DC253232745D865CB8919FB71EEDCB994",
}
F1_SHA256 = {
    0x3F4: "2654CE39617F63931572FD318239250067EBE867ACA25E7A066693DCE885F1E6",
    0x4A4: "147AA0025A121C3AFAD8E60DA44DA6967AFC8AA5437F169C37A4FD2039CC953B",
    0x4A5: "788443A3B78133D92F6704897780569DF6A74540FB6C71A5139698D3B75BF649",
    0x521: "C0D975EBB5A0520B66A716ABDB70745D9E6B7ED5694BB5CE199F959C7D4EF99D",
}
F2_SHA256 = {
    0x3F4: "49755BDC0FFA5288F651180B1BE447B0B5CE6EF32C195790EFB700FF2EAEF37D",
    0x4A4: "FF961BEA34A07D2C13517E3F0C58B79571F4D9BF843345F70F8115516BD1D193",
    0x4A5: "13B40A9757CECB2E6ED61070F485B81D658690E4F8C23436963304B32DC6AB86",
    0x521: "75CDE5F905C7D6D617DBE09DDD010C47E28DC6A17BC2E129C25101BC9F3EC184",
}

EXPECTED_SPEAKERS = {
    0x3F4: {0x3F4: 367},
    0x4A4: {0x4A4: 471},
    0x4A5: {0x4A5: 611, 0x4A4: 14},
    0x521: {0x521: 359, 0x4A4: 2},
}
EXPECTED_FLAGS = {
    0x3F4: {0x0000: 41, 0x0800: 223, 0x1000: 9, 0x1800: 6,
            0x7000: 88},
    0x4A4: {0x0000: 49, 0x0800: 294, 0x1000: 14, 0x1800: 16,
            0x2000: 8, 0x5800: 1, 0x7000: 89},
    0x4A5: {0x0000: 85, 0x0800: 386, 0x1000: 25, 0x1800: 16,
            0x2000: 9, 0x5800: 1, 0x7000: 103},
    0x521: {0x0000: 40, 0x0800: 219, 0x1000: 9, 0x1800: 6,
            0x7000: 87},
}
MIXED_SPEAKER_ROWS = {
    0x3F4: set(),
    0x4A4: set(),
    0x4A5: set(range(30, 37)) | set(range(249, 254)) | {612, 613},
    0x521: {348, 349},
}
RECOVERED_ROWS = {0x521: {317, 318, 319, 323, 324, 325, 329}}
RECOVERED_TEXT = {
    317: "가랏！　소드브레이커！",
    318: "이　무기엔　사각은　없어…！",
    319: "소드브레이커！",
    323: "폴　딩・솔리드캐논、전개",
    324: "데이터로드　완료…！　조준！",
    325: "발사한다！",
    329: "대구경이니만큼、위력은　확실해",
}
SILENCE_ROWS = {
    0x3F4: {74, 96, 97},
    0x4A4: {150, 198, 199},
    0x4A5: {279, 352, 353},
    0x521: {73, 95, 96},
}
SOURCE_LEDGER = {
    0x3F4: [(0, 21, "atk"), (21, 47, "damage"),
            (47, 74, "dodge"), (74, 75, "silence"),
            (75, 81, "miss"), (81, 96, "support"),
            (96, 98, "silence"), (98, 367, "weapon")],
    0x4A4: [(0, 55, "atk"), (55, 109, "damage"),
            (109, 150, "dodge"), (150, 151, "silence"),
            (151, 157, "miss"), (157, 198, "support"),
            (198, 200, "silence"), (200, 471, "weapon")],
    0x4A5: [(0, 120, "atk"), (120, 204, "damage"),
            (204, 279, "dodge"), (279, 280, "silence"),
            (280, 286, "miss"), (286, 352, "support"),
            (352, 354, "silence"), (354, 625, "weapon")],
    0x521: [(0, 21, "atk"), (21, 46, "damage"),
            (46, 73, "dodge"), (73, 74, "silence"),
            (74, 80, "miss"), (80, 95, "support"),
            (95, 97, "silence"), (97, 361, "weapon")],
}
EXPECTED_CATEGORIES = {
    "atk": 217, "hit": 87, "hit_light": 102, "dodge": 170,
    "silence": 12, "miss": 24, "support": 137, "weapon": 1075,
}

AP_BY_SPEAKER = {
    0x3F4: ("D4", 0xD4), 0x4A4: ("D4", 0xD4),
    0x4A5: ("D5", 0xD5), 0x521: ("D5", 0xD5),
}
RELATION_RESERVED_D5 = (
    set(range(10, 20)) | set(range(28, 32)) | set(range(37, 41)) |
    set(range(47, 51)) | {59, 60, 62, 63, 64, 65, 66}
)
W17_D5 = (set(range(10, 15)) | set(range(28, 32)) |
           set(range(37, 41)) | set(range(47, 51)) | {59, 60})
LEMON_D5 = {15, 16}
VINDEL_D5 = {17, 18, 19}

AP_WEAPON_SPANS = {
    0xD4: {
        "matrix": range(72, 82), "halberd": range(82, 86),
        "sword": range(86, 92), "rekkajin": range(92, 94),
        "suiryu": range(94, 97), "shippu": range(97, 102),
        "fujin": range(102, 104), "koujin": range(104, 107),
        "vaisaga": range(92, 107), "seiryu": range(107, 109),
        "genbu": range(109, 112), "byakko": range(112, 115),
        "suzaku": range(115, 121), "kirin": range(121, 150),
        "soulgain": range(107, 150),
    },
    0xD5: {
        "matrix": range(112, 120), "halberd": range(120, 126),
        "sword": range(126, 130), "rekkajin": range(130, 131),
        "suiryu": range(131, 133), "shippu": range(133, 134),
        "fujin": range(134, 137), "koujin": range(137, 140),
        "vaisaga": range(130, 140), "seiryu": range(140, 142),
        "genbu": range(142, 145), "byakko": range(145, 148),
        "suzaku": range(148, 153), "kirin": range(153, 193),
        "soulgain": range(140, 193),
    },
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

F1_CANARIES = {15: 0x223, 35: 0x233, 57: 0x242}
CRITICAL_GROUPS = {
    0x4A5: ((612, 613, 614), (0x4A4, 0x4A4, 0x4A5)),
    0x521: ((348, 349, 350), (0x4A4, 0x4A4, 0x521)),
}

SHARED_BASES = (0x5DA000, 0x83F000)
PT_MAGIC_REL = 0x13A478
PT_DATA_REL = 0x13A484
PLOT_MAGIC_REL = 0x13B484
PLOT_DATA_REL = 0x13B490
PLOT_STRIDE = 0x94
PLOT_PORTRAIT_OFF = 0x48
EXPECTED_PTBL = {
    0x3F4: 53, 0x4A4: 53, 0x4A5: 53, 0x521: 53,
    0x416: 242, 0x417: 243,
}
EXPECTED_PORTRAITS = {53: 0x14, 242: 0x7E, 243: 0x7E}

OG_SHARED = 0x005DA000
OG_STRM = 0x087D1F800
OG_BANK_TABLE = 0xD0820
OG_AXEL_BANK = 1046
OG_BANK_CAPACITY = 194
OG_BANK_PTR = 0x34F1C
SECTOR = 0x800
SAMPLE_RATE = 32000
STREAM_LO = 0x355D2800
STREAM_HI = 0x35E5D000
DESCRIPTOR_ABS = OG_SHARED + OG_BANK_TABLE + OG_BANK_PTR
STREAM_ABS_LO = OG_STRM + STREAM_LO
STREAM_ABS_HI = OG_STRM + STREAM_HI

MASK_RANGES = (
    (0x006DF73C, 0x006E0054),
    (0x8585A000, 0x8585D800),
    (0x8596E000, 0x85978000),
    (0x859F3000, 0x859F6000),
    (0xBD2F2000, 0xBDB7C800),
)

SPECIAL_WEAPON_WORDS = (
    ("열화인", "rekkajin"), ("손톱", "rekkajin"),
    ("수류조", "suiryu"), ("질공도", "shippu"),
    ("지참", "shippu"), ("광풍", "fujin"),
    ("풍인섬", "fujin"), ("광인섬", "koujin"),
    ("비늘포", "seiryu"), ("파이널　코드", "kirin"),
    ("파이널 코드", "kirin"),
)
WEAPON_WORDS = (
    ("매트릭스", "matrix"), ("할버트", "halberd"),
    ("할버드", "halberd"), ("소드　브레이커", "sword"),
    ("소드브레이커", "sword"), ("리니어", "linear"),
    ("청룡린", "seiryu"), ("현무강탄", "genbu"),
    ("소울　펀치", "genbu"), ("소울펀치", "genbu"),
    ("백호교", "byakko"), ("무주작", "suzaku"),
    ("코드　기린", "kirin"), ("코드기린", "kirin"),
    ("진・극", "kirin"), ("기린！", "kirin"),
    ("소울게인", "soulgain"),
)
REL_TEXT_RE = re.compile(r"레몬|빈델|Ｗ１７|인형")
CONTROL_RE = re.compile(r"[「」『』…！？，。・、／/\s　]")
PURE_SHOUT_RE = re.compile(
    r"^[「」\s　]*(?:이야[아앗]*|하[아앗]*|으럇|우오[오옷]*|"
    r"으랴[아앗]*|으라챠[아앗]*|에에잇|가랏|간다)"
    r"[！…\s　「」]*$")
RANGED_CUE_RE = re.compile(
    r"조준|발사|캐논|런처|런쳐|미사일|사격|저격|포착|"
    r"(?<![가-힣])록(?![가-힣])|록온|탄|빔|애로우|랜서")
MELEE_CUE_RE = re.compile(
    r"검|칼|베어|베겠|베고|베라|베주|벤다|참격|찢|꿰뚫|때려|박|근접|타격|연속|주먹|펀치|스테이크|벙커|할버|소드|칼날")
FINISH_CUE_RE = re.compile(
    r"끝이다|끝내|끝장|리미트|한계|오의|최대출력|풀\s*드라이브|코드|결착")


class Audit:
    """Collect failures without flooding the JSON when a table is displaced."""

    def __init__(self) -> None:
        self.error_count = 0
        self.errors: list[str] = []

    def fail(self, message: str) -> None:
        self.error_count += 1
        if len(self.errors) < 500:
            self.errors.append(message)

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.fail(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def masked_sha256(path: Path, ranges: tuple[tuple[int, int], ...]) -> str:
    digest = hashlib.sha256()
    size = path.stat().st_size
    cursor = 0
    zero = b"\0" * (1024 * 1024)
    with path.open("rb") as fh:
        for lo, hi in ranges:
            if not (cursor <= lo <= hi <= size):
                raise ValueError(f"invalid mask range 0x{lo:X}..0x{hi:X}")
            remaining = lo - cursor
            while remaining:
                block = fh.read(min(16 * 1024 * 1024, remaining))
                if not block:
                    raise ValueError("short read while calculating masked SHA-256")
                digest.update(block)
                remaining -= len(block)
            fh.seek(hi)
            remaining = hi - lo
            while remaining:
                amount = min(len(zero), remaining)
                digest.update(zero[:amount])
                remaining -= amount
            cursor = hi
        remaining = size - cursor
        while remaining:
            block = fh.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise ValueError("short final read while calculating masked SHA-256")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest().upper()


def patched_sha256(path: Path, replacements: list[tuple[int, bytes]],
                   masks: tuple[tuple[int, int], ...] = ()) -> str:
    """Hash a virtual view with follow-up bytes rolled back and masks zeroed."""
    intervals: list[tuple[int, int, bytes | None]] = [
        (offset, offset + len(data), data) for offset, data in replacements]
    intervals += [(lo, hi, None) for lo, hi in masks]
    intervals.sort()
    size = path.stat().st_size
    cursor = 0
    digest = hashlib.sha256()
    zero = b"\0" * (1024 * 1024)
    with path.open("rb") as fh:
        for lo, hi, data in intervals:
            if not (cursor <= lo <= hi <= size):
                raise ValueError(f"overlapping patched hash interval 0x{lo:X}..0x{hi:X}")
            remaining = lo - cursor
            while remaining:
                block = fh.read(min(16 * 1024 * 1024, remaining))
                if not block:
                    raise ValueError("short read in patched SHA-256")
                digest.update(block)
                remaining -= len(block)
            fh.seek(hi)
            remaining = hi - lo
            if data is not None:
                if len(data) != remaining:
                    raise ValueError("replacement length differs")
                digest.update(data)
            else:
                while remaining:
                    amount = min(len(zero), remaining)
                    digest.update(zero[:amount])
                    remaining -= amount
            cursor = hi
        remaining = size - cursor
        while remaining:
            block = fh.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise ValueError("short final read in patched SHA-256")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest().upper()


def read_region(path: Path, offset: int, length: int) -> bytes:
    with path.open("rb") as fh:
        fh.seek(offset)
        data = fh.read(length)
    if len(data) != length:
        raise ValueError(
            f"short read {path} @0x{offset:X}: {len(data)} != {length}")
    return data


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def source_category(key: int, index: int, flag: int) -> str:
    for lo, hi, category in SOURCE_LEDGER[key]:
        if lo <= index < hi:
            if category == "damage":
                return "hit" if flag in {0x1000, 0x1800, 0x5800} else "hit_light"
            return category
    raise ValueError(f"0x{key:X}[{index}] outside source ledger")


def ap_category(ap_key: int, index: int) -> str | None:
    if ap_key == 0xD4:
        spans = (
            (0, 9, "atk"), (9, 23, "hit"), (23, 29, "hit_light"),
            (29, 53, "dodge"), (53, 55, "hit_light"),
            (55, 58, "miss"), (58, 64, "support"),
            (64, 68, "silence"), (68, 72, "atk"),
            (72, 150, "weapon"),
        )
    elif ap_key == 0xD5:
        spans = (
            (0, 20, "atk"), (20, 41, "hit"),
            (41, 45, "hit_light"), (45, 87, "dodge"),
            (87, 98, "miss"), (98, 104, "support"),
            (104, 108, "silence"), (108, 112, "atk"),
            (112, 193, "weapon"),
        )
    else:
        return None
    return next((category for lo, hi, category in spans
                 if lo <= index < hi), None)


def meaningful_length(text: str) -> int:
    return len(CONTROL_RE.sub("", text))


def semantic_compatible(source: str, mapped: str | None,
                        mapped_text: str = "") -> bool:
    if source in {"hit", "hit_light"}:
        return mapped in {"hit", "hit_light"}
    if source == "weapon" and mapped == "atk":
        # The safe mapping deliberately admits only substantial, neutral AP
        # attack lines into generic weapon cues.  Dodge/miss/support remain
        # forbidden, which is the failure mode this audit is designed to catch.
        return (weapon_key(mapped_text) is None and
                not REL_TEXT_RE.search(mapped_text) and
                not PURE_SHOUT_RE.fullmatch(mapped_text) and
                meaningful_length(mapped_text) >= 6)
    return source == mapped


def relation_kind(text: str) -> str | None:
    if "레몬" in text:
        return "lemon"
    if "빈델" in text:
        return "vindel"
    if any(word in text for word in ("엑셀", "액셀", "대장", "Ｗ１７")):
        return "w17"
    return None


def source_relation(key: int, index: int, text: str) -> str | None:
    """Use the audited physical group before keyword fallback.

    4A5[59] and 4A5[69] are continuation lines that omit the target's name;
    4A5[60:65] is intentionally not part of W17.  This prevents a text-only
    heuristic from silently merging the adjacent W-number blocks.
    """
    if key == 0x4A5:
        if 56 <= index <= 59:
            return "w17"
        if 65 <= index <= 67:
            return "lemon"
        if 68 <= index <= 69:
            return "vindel"
    return relation_kind(text)


def mapped_relation(ap_key: int, index: int) -> str | None:
    if ap_key != 0xD5:
        return None
    if index in W17_D5:
        return "w17"
    if index in LEMON_D5:
        return "lemon"
    if index in VINDEL_D5:
        return "vindel"
    return None


def weapon_key(text: str) -> str | None:
    for word, family in SPECIAL_WEAPON_WORDS:
        if word in text:
            return family
    for word, family in WEAPON_WORDS:
        if word in text:
            return family
    return None


def source_weapon_key(key: int, index: int, text: str) -> str | None:
    for lo, hi, family in VAISAGA_SUBSPANS[key]:
        if lo <= index < hi:
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


def weapon_compatible(source: str | None, mapped: str | None) -> bool:
    return (mapped is None or mapped == source or
            (source == "soulgain" and mapped in {
                "seiryu", "genbu", "byakko", "suzaku", "kirin"}))


def decode_pool_text(entry: bytes, chunk: dict[str, int], index: int) -> tuple[int, str] | None:
    text_off = struct.unpack_from("<H", entry, chunk["f3"] + index * 2)[0]
    start = chunk["pool"] + text_off
    pool_end = chunk["pool"] + chunk["pool_cap"]
    if not chunk["pool"] <= start < pool_end:
        return None
    end = entry.find(b"\0", start, pool_end)
    if end < start:
        return None
    try:
        return text_off, decode(entry[start:end])
    except Exception:
        return None


def pool_boundaries(entry: bytes, chunk: dict[str, int]) -> tuple[set[int], int, bool]:
    pool = entry[chunk["pool"]:chunk["pool"] + chunk["pool_cap"]]
    starts: set[int] = set()
    pos = 0
    while pos < len(pool):
        end = pool.find(b"\0", pos)
        if end < 0:
            return starts, len(pool), False
        if end == pos:
            return starts, pos, not any(pool[pos:])
        starts.add(pos)
        pos = end + 1
    return starts, pos, True


def baseline_rows(entry: bytes, audit: Audit) -> dict[int, list[dict[str, Any]]]:
    rows_by_key: dict[int, list[dict[str, Any]]] = {}
    voice_text: dict[int, str] = {}
    unresolved: list[dict[str, Any]] = []
    for key, chunk in CHUNKS.items():
        p = chunk["n"] - 1
        rows: list[dict[str, Any]] = []
        for index in range(p):
            tag = struct.unpack_from("<H", entry, chunk["f2"] + index * 2)[0]
            voice = struct.unpack_from("<I", entry, chunk["f4"] + index * 4)[0]
            decoded = decode_pool_text(entry, chunk, index)
            text = decoded[1] if decoded is not None else ""
            row = {
                "i": index, "tag": tag, "speaker": tag & 0x7FF,
                "flag": tag & 0xF800, "source_voice": voice,
                "raw_text": text, "text": text,
                "recovered": decoded is None or not text,
            }
            rows.append(row)
            if text and voice >= 1_000_000:
                voice_text.setdefault(voice, text)
            elif voice >= 1_000_000:
                unresolved.append(row)
        rows_by_key[key] = rows

    for row in unresolved:
        recovered = voice_text.get(row["source_voice"])
        if recovered is None:
            audit.fail(f"baseline voice {row['source_voice']} cannot recover text")
            recovered = ""
        row["text"] = recovered
    return rows_by_key


def expected_manifest_ranges() -> list[dict[str, Any]]:
    expected: list[dict[str, Any]] = []
    backup_pos = 0
    for key, chunk in CHUNKS.items():
        p = chunk["n"] - 1
        parts = (
            (ENTRY_BASE + chunk["off"], chunk["f3"] - chunk["off"]),
            (ENTRY_BASE + chunk["f3"], chunk["f4"] - chunk["f3"]),
            (ENTRY_BASE + chunk["f4"], 4 * p),
            (ENTRY_BASE + chunk["pool"], chunk["pool_cap"]),
        )
        for offset, length in parts:
            expected.append({
                "offset": offset, "length": length,
                "backup_pos": backup_pos, "kind": f"battle-0x{key:X}",
            })
            backup_pos += length
    for offset, length, kind in (
            (DESCRIPTOR_ABS, OG_BANK_CAPACITY * 12, "descriptors"),
            (STREAM_ABS_LO, STREAM_HI - STREAM_LO, "strm")):
        expected.append({
            "offset": offset, "length": length,
            "backup_pos": backup_pos, "kind": kind,
        })
        backup_pos += length
    return expected


def validate_manifest(manifest: dict[str, Any], iso: Path, runtime: Path,
                      actual_sha: str, audit: Audit) -> dict[int, int]:
    audit.check(manifest.get("state") == "applied", "manifest state is not applied")
    audit.check(manifest.get("before_sha256") == EXPECTED_BEFORE_SHA256,
                "manifest before_sha256 is not the audited PASS33 source")
    audit.check(manifest.get("after_sha256") == actual_sha,
                "manifest after_sha256 differs from target ISO")
    try:
        target = Path(manifest.get("target", "")).resolve()
        audit.check(target == iso.resolve(), "manifest target path differs from --iso")
    except Exception:
        audit.fail("manifest target path is invalid")

    audit.check(manifest.get("ap_source_sha256") == AP_SOURCE_SHA256,
                "manifest AP source hashes differ from fixed audited hashes")
    expected_ranges = expected_manifest_ranges()
    ranges = manifest.get("ranges", [])
    range_fields = ("offset", "length", "backup_pos", "kind")
    actual_range_core = [
        {field: item.get(field) for field in range_fields}
        for item in ranges if isinstance(item, dict)
    ] if isinstance(ranges, list) else []
    audit.check(actual_range_core == expected_ranges,
                "manifest write ranges are not the exact safe rebuild ranges")

    if isinstance(ranges, list):
        total = sum(item.get("length", 0) for item in ranges
                    if isinstance(item, dict))
        backup_path = Path(manifest.get("backup", ""))
        if backup_path.is_file():
            audit.check(backup_path.stat().st_size == total,
                        "rollback backup length differs from journal ranges")
            audit.check(sha256_file(backup_path) == manifest.get("backup_sha256"),
                        "rollback backup SHA-256 differs from manifest")
            backup = backup_path.read_bytes()
            with iso.open("rb") as target_fh:
                for position, item in enumerate(ranges):
                    if not isinstance(item, dict):
                        continue
                    offset = int(item.get("offset", -1))
                    length = int(item.get("length", -1))
                    backup_pos = int(item.get("backup_pos", -1))
                    if offset < 0 or length < 0 or backup_pos < 0:
                        audit.fail(f"manifest range {position} has invalid bounds")
                        continue
                    old = backup[backup_pos:backup_pos + length]
                    audit.check(
                        hashlib.sha256(old).hexdigest().upper()
                        == item.get("old_sha256"),
                        f"manifest range {position} old SHA-256 differs")
                    target_fh.seek(offset)
                    new = target_fh.read(length)
                    audit.check(len(new) == length,
                                f"manifest range {position} target read is short")
                    audit.check(
                        hashlib.sha256(new).hexdigest().upper()
                        == item.get("new_sha256"),
                        f"manifest range {position} new SHA-256 differs")
        else:
            audit.fail(f"rollback backup is missing: {backup_path}")

    raw_slots = manifest.get("clip_slots")
    slots: dict[int, int] = {}
    if not isinstance(raw_slots, dict):
        audit.fail("manifest clip_slots is not an object")
        return slots
    try:
        slots = {int(clip): int(slot) for clip, slot in raw_slots.items()}
    except (TypeError, ValueError):
        audit.fail("manifest clip_slots contains a non-integer key/value")
        return {}
    ordered = sorted(slots)
    audit.check(len(slots) == 171, f"clip slot count {len(slots)} != 171")
    audit.check([slots[clip] for clip in ordered] == list(range(len(slots))),
                "clip slots are not clip-sorted contiguous slots 0..170")
    return slots


def validate_ap_sources(runtime: Path, audit: Audit) -> dict[str, dict[int, dict[str, Any]]]:
    out: dict[str, dict[int, dict[str, Any]]] = {}
    for name in ("D4", "D5"):
        path = runtime / f"ap{name}.json"
        actual_hash = sha256_file(path)
        audit.check(actual_hash == AP_SOURCE_SHA256[name],
                    f"{path.name} SHA-256 {actual_hash} is not audited source")
        data = load_json(path)
        audit.check(isinstance(data, list), f"{path.name} is not a row list")
        rows = {int(row["i"]): row for row in data}
        expected_len = 150 if name == "D4" else 193
        audit.check(len(rows) == expected_len,
                    f"{path.name} row count {len(rows)} != {expected_len}")
        audit.check(set(rows) == set(range(expected_len)),
                    f"{path.name} indices are not contiguous")
        for index, row in rows.items():
            voice = int(row.get("voice", 0))
            if voice:
                audit.check(voice // 1000 == 212,
                            f"{name}[{index}] voice bank is not AP Axel bank 212")
        out[name] = rows
    return out


def independent_allowed_clips(runtime: Path, audit: Audit) -> set[int]:
    """Reconstruct the candidate-clip policy from persisted PASS33 inputs.

    This exists only to judge whether a wordless family cue had an admitted
    substantive alternative.  It does not create the payload mapping.
    """
    chunks_path = runtime / "entry5_chunks.json"
    chunks_hash = sha256_file(chunks_path)
    audit.check(chunks_hash == ENTRY5_CHUNKS_SHA256,
                f"entry5_chunks.json SHA-256 {chunks_hash} differs")
    try:
        rows416 = load_json(runtime / "place416.json")
        rows417 = load_json(runtime / "place417.json")
        ap4 = {int(row["i"]): row for row in load_json(runtime / "apD4.json")}
        ap5 = {int(row["i"]): row for row in load_json(runtime / "apD5.json")}
        relation = load_json(
            runtime / "pass32_axel_battle_relation_overrides.json")["overrides"]
        for index, ap_i in relation.items():
            rows417[int(index)].update(
                voice=ap5[int(ap_i)]["voice"], text=ap5[int(ap_i)]["text"])
        extras = load_json(runtime / "machine_extra.json")
        repeats = load_json(
            runtime / "pass33_axel_battle_repeat_overrides.json")
        for index, ap_i in repeats["place416"].items():
            rows416[int(index)].update(
                voice=ap4[int(ap_i)]["voice"], text=ap4[int(ap_i)]["text"])
        for key, overrides in repeats["machine_extra"].items():
            for index, ap_i in overrides.items():
                extras[key][int(index)].update(
                    voice=ap4[int(ap_i)]["voice"], text=ap4[int(ap_i)]["text"])
        base = {
            int(row["voice"]) % 1000
            for rows in [rows416, rows417, *extras.values()]
            for row in rows if int(row.get("voice", 0))
        }
    except Exception as exc:
        audit.fail(f"cannot reconstruct PASS33 candidate clips: {exc}")
        return set()
    audit.check(len(base) == 181, f"PASS33 base clip count {len(base)} != 181")
    allowed = (base - DROP_CLIPS) | ADD_CLIPS | EXTRA_GENERIC_CLIPS
    audit.check(len(allowed) == 212,
                f"candidate clip count {len(allowed)} != 212")
    return allowed


def validate_native_structure(target: bytes, baseline: bytes, audit: Audit) -> dict[str, Any]:
    per_key: dict[str, Any] = {}
    for key, chunk in CHUNKS.items():
        n = chunk["n"]
        p = n - 1
        audit.check((chunk["pool"] - chunk["f4"]) // 4 == p,
                    f"0x{key:X} hardcoded P is not N-1")
        prefix = target[chunk["off"]:chunk["f2"]]
        f1 = target[chunk["f2"] - 2 * n:chunk["f2"]]
        f2 = target[chunk["f2"]:chunk["f3"]]
        audit.check(prefix == baseline[chunk["off"]:chunk["f2"]],
                    f"0x{key:X} complete native selector prefix differs")
        audit.check(f2 == baseline[chunk["f2"]:chunk["f3"]],
                    f"0x{key:X} complete native f2 speaker/tag array differs")
        audit.check(sha256_bytes(prefix) == PREFIX_SHA256[key],
                    f"0x{key:X} selector prefix SHA-256 differs")
        audit.check(sha256_bytes(f1) == F1_SHA256[key],
                    f"0x{key:X} f1 SHA-256 differs")
        audit.check(sha256_bytes(f2) == F2_SHA256[key],
                    f"0x{key:X} f2 SHA-256 differs")
        audit.check(struct.unpack_from("<H", target,
                                      chunk["f2"] + p * 2)[0] == 0,
                    f"0x{key:X} final f2 sentinel is not zero")
        audit.check(struct.unpack_from("<H", target,
                                      chunk["f3"] + p * 2)[0] == 0,
                    f"0x{key:X} final f3 sentinel is not zero")

        first_end = baseline.find(b"\0", chunk["pool"],
                                  chunk["pool"] + chunk["pool_cap"])
        audit.check(first_end >= chunk["pool"],
                    f"0x{key:X} baseline first pool string has no terminator")
        if first_end >= chunk["pool"]:
            audit.check(target[chunk["pool"]:first_end + 1] ==
                        baseline[chunk["pool"]:first_end + 1],
                        f"0x{key:X} native f4/pool sentinel string differs")

        speakers: collections.Counter[int] = collections.Counter()
        flags: collections.Counter[int] = collections.Counter()
        mixed: set[int] = set()
        for index in range(p):
            tag = struct.unpack_from("<H", target,
                                     chunk["f2"] + index * 2)[0]
            speakers[tag & 0x7FF] += 1
            flags[tag & 0xF800] += 1
            if (tag & 0x7FF) != key:
                mixed.add(index)
        audit.check(dict(speakers) == EXPECTED_SPEAKERS[key],
                    f"0x{key:X} speaker distribution {dict(speakers)} differs")
        audit.check(dict(flags) == EXPECTED_FLAGS[key],
                    f"0x{key:X} flag distribution {dict(flags)} differs")
        audit.check(mixed == MIXED_SPEAKER_ROWS[key],
                    f"0x{key:X} mixed-speaker rows differ: {sorted(mixed)}")
        per_key[f"0x{key:X}"] = {
            "payloads": p,
            "speakers": {f"0x{k:X}": v for k, v in speakers.items()},
            "flags": {f"0x{k:04X}": v for k, v in flags.items()},
            "mixed_rows": sorted(mixed),
            "prefix_sha256": sha256_bytes(prefix),
            "f1_sha256": sha256_bytes(f1),
            "f2_sha256": sha256_bytes(f2),
        }

    c = CHUNKS[0x4A5]
    f1_start = c["f2"] - 2 * c["n"]
    for index, expected in F1_CANARIES.items():
        actual = struct.unpack_from("<H", target, f1_start + index * 2)[0]
        audit.check(actual == expected,
                    f"0x4A5 f1[{index}] 0x{actual:X} != 0x{expected:X}")
    return per_key


def validate_payloads(target: bytes, baseline: bytes,
                      manifest: dict[str, Any], clip_slots: dict[int, int],
                      ap_rows: dict[str, dict[int, dict[str, Any]]],
                      allowed_clips: set[int], audit: Audit) -> dict[str, Any]:
    native = baseline_rows(baseline, audit)
    raw_mapping = manifest.get("payload_mapping")
    if not isinstance(raw_mapping, dict):
        audit.fail("manifest payload_mapping is not an object")
        raw_mapping = {}

    categories: collections.Counter[str] = collections.Counter()
    actual_used_clips: set[int] = set()
    voiced = silence = mixed = recovered = 0
    unique_texts: set[str] = set()
    per_key: dict[str, Any] = {}

    for key, chunk in CHUNKS.items():
        key_name = f"0x{key:X}"
        p = chunk["n"] - 1
        raw_rows = raw_mapping.get(key_name)
        if not isinstance(raw_rows, list):
            audit.fail(f"manifest mapping {key_name} is not a list")
            raw_rows = []
        by_index: dict[int, dict[str, Any]] = {}
        for row in raw_rows:
            try:
                index = int(row["i"])
            except (KeyError, TypeError, ValueError):
                audit.fail(f"{key_name} manifest row has invalid index")
                continue
            if index in by_index:
                audit.fail(f"{key_name}[{index}] duplicated in manifest")
            by_index[index] = row
        audit.check(len(raw_rows) == p,
                    f"{key_name} manifest row count {len(raw_rows)} != {p}")
        audit.check(set(by_index) == set(range(p)),
                    f"{key_name} manifest indices are not exactly 0..{p - 1}")

        boundaries, pool_used, tail_zero = pool_boundaries(target, chunk)
        audit.check(tail_zero, f"{key_name} string pool tail is not zero-filled")
        offsets_seen: set[int] = set()
        decoded_rows: list[tuple[str, int]] = []
        key_voiced = 0
        atk_texts: set[str] = set()
        weapon_texts: set[str] = set()
        atk_clips: set[int] = set()
        weapon_clips: set[int] = set()

        for index in range(p):
            row = by_index.get(index, {})
            native_row = native[key][index]
            tag = struct.unpack_from("<H", target,
                                     chunk["f2"] + index * 2)[0]
            flag = tag & 0xF800
            speaker = tag & 0x7FF
            actual_voice = struct.unpack_from("<I", target,
                                              chunk["f4"] + index * 4)[0]
            decoded = decode_pool_text(target, chunk, index)
            if decoded is None:
                audit.fail(f"{key_name}[{index}] invalid/undecodable text offset")
                text_off, actual_text = -1, ""
            else:
                text_off, actual_text = decoded
                offsets_seen.add(text_off)
                audit.check(text_off in boundaries,
                            f"{key_name}[{index}] offset 0x{text_off:X} is not a string boundary")
                audit.check(bool(actual_text), f"{key_name}[{index}] text is empty")

            expected_cat = source_category(key, index, flag)
            expected_relation = source_relation(key, index, native_row["text"])
            expected_weapon = (source_weapon_key(key, index, native_row["text"])
                               if expected_cat == "weapon" else None)
            expected_cue = (weapon_cue(native_row["text"], flag)
                            if expected_cat == "weapon" else None)
            expected_recovered = index in RECOVERED_ROWS.get(key, set())
            expected_mixed = index in MIXED_SPEAKER_ROWS[key]
            expected_ap_name, expected_ap_key = AP_BY_SPEAKER.get(
                speaker, (None, None))

            categories[expected_cat] += 1
            mixed += int(expected_mixed)
            recovered += int(expected_recovered)

            audit.check(tag == native_row["tag"],
                        f"{key_name}[{index}] tag differs from baseline")
            audit.check(bool(native_row["recovered"]) == expected_recovered,
                        f"{key_name}[{index}] native recovery state differs")
            if expected_recovered:
                audit.check(native_row["text"] == RECOVERED_TEXT[index],
                            f"{key_name}[{index}] recovered native text differs")

            expected_fields = {
                "tag": native_row["tag"], "speaker": speaker, "flag": flag,
                "source_voice": native_row["source_voice"],
                "recovered": expected_recovered, "orig": native_row["text"],
                "category": expected_cat, "relation": expected_relation,
                "weapon": expected_weapon, "cue": expected_cue,
                "ap_name": expected_ap_name, "ap_key": expected_ap_key,
            }
            for field, wanted in expected_fields.items():
                audit.check(row.get(field) == wanted,
                            f"{key_name}[{index}] manifest {field} differs")

            if expected_cat == "silence":
                silence += 1
                wanted_silence = {
                    "ap_i": -1, "voice": 0, "clip": 0,
                    "slot": None, "text": "………",
                }
                for field, wanted in wanted_silence.items():
                    audit.check(row.get(field) == wanted,
                                f"{key_name}[{index}] silence {field} differs")
                audit.check(actual_voice == 0,
                            f"{key_name}[{index}] silence row has voice {actual_voice}")
            else:
                voiced += 1
                key_voiced += 1
                try:
                    ap_i = int(row.get("ap_i"))
                except (TypeError, ValueError):
                    ap_i = -999
                ap_source = ap_rows.get(str(expected_ap_name), {}).get(ap_i)
                if ap_source is None:
                    audit.fail(f"{key_name}[{index}] AP provenance row is absent")
                    expected_voice = expected_clip = expected_slot = None
                else:
                    expected_voice = int(ap_source["voice"])
                    expected_clip = expected_voice % 1000
                    expected_slot = clip_slots.get(expected_clip)
                    audit.check(expected_voice != 0,
                                f"{key_name}[{index}] mapped AP row is silent")
                    audit.check(row.get("voice") == expected_voice,
                                f"{key_name}[{index}] manifest AP voice differs")
                    audit.check(row.get("clip") == expected_clip,
                                f"{key_name}[{index}] manifest AP clip differs")
                    audit.check(row.get("slot") == expected_slot,
                                f"{key_name}[{index}] manifest bank slot differs")
                    audit.check(row.get("text") == ap_source["text"],
                                f"{key_name}[{index}] manifest text differs from AP source")
                    wanted_voice = (OG_AXEL_BANK * 1000 + expected_slot
                                    if expected_slot is not None else None)
                    audit.check(actual_voice == wanted_voice,
                                f"{key_name}[{index}] ISO voice {actual_voice} != {wanted_voice}")
                    actual_used_clips.add(expected_clip)
                    if expected_cat == "atk":
                        atk_texts.add(ap_source["text"])
                        atk_clips.add(expected_clip)
                    elif expected_cat == "weapon":
                        weapon_texts.add(ap_source["text"])
                        weapon_clips.add(expected_clip)

                    mapped_cat = ap_category(expected_ap_key, ap_i)
                    audit.check(semantic_compatible(
                                    expected_cat, mapped_cat, ap_source["text"]),
                                f"{key_name}[{index}] semantic {expected_cat}->{mapped_cat}")
                    mapped_rel = mapped_relation(expected_ap_key, ap_i)
                    audit.check(not mapped_rel or mapped_rel == expected_relation,
                                f"{key_name}[{index}] relationship leak {mapped_rel}/{expected_relation}")
                    if expected_ap_key == 0xD5 and ap_i in {62, 63, 64, 65, 66}:
                        audit.fail(f"{key_name}[{index}] uses excluded D5 relationship row {ap_i}")
                    relation_pool_exists = (
                        expected_relation == "w17" and expected_cat in {
                            "atk", "hit", "hit_light", "dodge", "miss"}
                    ) or (
                        expected_relation in {"lemon", "vindel"} and
                        expected_cat == "atk"
                    )
                    if expected_ap_key == 0xD5 and relation_pool_exists:
                        audit.check(mapped_rel == expected_relation,
                                    f"{key_name}[{index}] missed available relationship pool")
                    if REL_TEXT_RE.search(ap_source["text"]):
                        audit.check(expected_relation is not None,
                                    f"{key_name}[{index}] unrelated AP relationship text leaked")

                    mapped_weapon = weapon_key(ap_source["text"])
                    audit.check(weapon_compatible(expected_weapon, mapped_weapon),
                                f"{key_name}[{index}] weapon {expected_weapon}->{mapped_weapon}")
                    if expected_cat == "weapon" and mapped_weapon is not None:
                        family_span = AP_WEAPON_SPANS[expected_ap_key].get(mapped_weapon)
                        if family_span is not None:
                            audit.check(ap_i in family_span,
                                        f"{key_name}[{index}] named AP weapon is outside family span")
                    if (expected_cat == "weapon" and
                            PURE_SHOUT_RE.fullmatch(ap_source["text"])):
                        family_span = AP_WEAPON_SPANS[expected_ap_key].get(
                            expected_weapon, range(0))
                        substantive = [
                            candidate for candidate_i, candidate in
                            ap_rows[str(expected_ap_name)].items()
                            if candidate_i in family_span and candidate.get("voice")
                            and int(candidate["voice"]) % 1000 in allowed_clips
                            and not PURE_SHOUT_RE.fullmatch(candidate["text"])
                            and meaningful_length(candidate["text"]) >= 4
                        ]
                        audit.check(not substantive,
                                    f"{key_name}[{index}] pure shout used despite substantive family alternative")

            audit.check(actual_text == row.get("text"),
                        f"{key_name}[{index}] ISO text differs from manifest")
            if actual_voice:
                unique_texts.add(actual_text)
            decoded_rows.append((actual_text, actual_voice))

        expected_boundaries = {0} | offsets_seen
        audit.check(boundaries == expected_boundaries,
                    f"{key_name} pool contains unreferenced/noncanonical strings")
        adjacent = []
        for index, (left, right) in enumerate(zip(decoded_rows, decoded_rows[1:])):
            if left[1] and left == right:
                adjacent.append(index)
        audit.check(not adjacent,
                    f"{key_name} adjacent identical voiced rows at {adjacent}")
        text_overlap = sorted(atk_texts & weapon_texts)
        clip_overlap = sorted(atk_clips & weapon_clips)
        audit.check(not text_overlap,
                    f"{key_name} attack/weapon text pools overlap: {text_overlap}")
        audit.check(not clip_overlap,
                    f"{key_name} attack/weapon clip pools overlap: {clip_overlap}")
        per_key[key_name] = {
            "payloads": p, "voiced": key_voiced,
            "silence": p - key_voiced, "pool_used": pool_used,
            "pool_capacity": chunk["pool_cap"],
            "string_boundaries": len(boundaries),
            "adjacent_identical_voiced": adjacent,
            "attack_weapon_text_overlap": text_overlap,
            "attack_weapon_clip_overlap": clip_overlap,
        }

    audit.check(dict(categories) == EXPECTED_CATEGORIES,
                f"category totals {dict(categories)} differ")
    audit.check(voiced == 1812, f"voiced payloads {voiced} != 1812")
    audit.check(silence == 12, f"silent payloads {silence} != 12")
    audit.check(mixed == 16, f"mixed-speaker payloads {mixed} != 16")
    audit.check(recovered == 7, f"recovered payloads {recovered} != 7")
    audit.check(actual_used_clips == set(clip_slots),
                "mapped clips and manifest clip_slots differ")
    audit.check(actual_used_clips <= allowed_clips,
                "mapped clips include a clip outside the independent candidate policy")

    critical: dict[str, Any] = {}
    for key, (indices, speakers) in CRITICAL_GROUPS.items():
        key_name = f"0x{key:X}"
        rows = raw_mapping.get(key_name, [])
        by_index = {int(row["i"]): row for row in rows
                    if isinstance(row, dict) and "i" in row}
        pairs = [(by_index.get(index, {}).get("text"),
                  by_index.get(index, {}).get("voice")) for index in indices]
        actual_speakers = tuple(
            struct.unpack_from("<H", target,
                               CHUNKS[key]["f2"] + index * 2)[0] & 0x7FF
            for index in indices)
        audit.check(actual_speakers == speakers,
                    f"{key_name} critical group speaker sequence differs")
        audit.check(len(set(pairs)) == len(indices),
                    f"{key_name} critical 3-cue group is not distinct")
        critical[key_name] = {
            "indices": list(indices),
            "speakers": [f"0x{s:X}" for s in actual_speakers],
            "pairs": pairs,
        }

    return {
        "payloads": voiced + silence, "voiced": voiced, "silence": silence,
        "mixed_speaker_rows": mixed, "recovered_native_rows": recovered,
        "categories": dict(categories), "unique_texts": len(unique_texts),
        "used_clips": len(actual_used_clips), "per_key": per_key,
        "critical_groups": critical,
    }


def validate_ptbl_plot(iso: Path, audit: Audit) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    with iso.open("rb") as fh:
        for base in SHARED_BASES:
            fh.seek(base + PT_MAGIC_REL)
            audit.check(fh.read(4) == b"PTbl",
                        f"archive 0x{base:X} PTbl magic differs")
            fh.seek(base + PLOT_MAGIC_REL)
            audit.check(fh.read(4) == b"Plot",
                        f"archive 0x{base:X} Plot magic differs")
            values: dict[str, int] = {}
            for raw_key, wanted_plot in EXPECTED_PTBL.items():
                fh.seek(base + PT_DATA_REL + raw_key * 2)
                data = fh.read(2)
                actual_plot = struct.unpack("<H", data)[0] if len(data) == 2 else -1
                audit.check(actual_plot == wanted_plot,
                            f"archive 0x{base:X} PTbl[0x{raw_key:X}]={actual_plot} != {wanted_plot}")
                values[f"0x{raw_key:X}"] = actual_plot
            portraits: dict[str, int] = {}
            for plot, wanted_portrait in EXPECTED_PORTRAITS.items():
                fh.seek(base + PLOT_DATA_REL + plot * PLOT_STRIDE +
                        PLOT_PORTRAIT_OFF)
                data = fh.read(2)
                actual = struct.unpack("<H", data)[0] if len(data) == 2 else -1
                audit.check(actual == wanted_portrait,
                            f"archive 0x{base:X} Plot[{plot}] portrait 0x{actual:X} != 0x{wanted_portrait:X}")
                portraits[str(plot)] = actual
            observations.append({
                "archive_base": f"0x{base:X}", "ptbl": values,
                "portraits": {k: f"0x{v:X}" for k, v in portraits.items()},
            })
    return observations


def _validate_baseline_audio_region(baseline: Path, audit: Audit) -> None:
    with baseline.open("rb") as fh:
        fh.seek(OG_SHARED + OG_BANK_TABLE + OG_AXEL_BANK * 8)
        header = fh.read(8)
        if len(header) != 8:
            audit.fail("baseline bank 1046 header is truncated")
            return
        ptr, count = struct.unpack("<II", header)
        audit.check(ptr == OG_BANK_PTR and count == OG_BANK_CAPACITY,
                    f"baseline bank header ptr/count 0x{ptr:X}/{count} differs")
        fh.seek(OG_SHARED + OG_BANK_TABLE + ptr)
        descriptors = [struct.unpack("<III", fh.read(12))
                       for _ in range(count)]
    starts = [sector * SECTOR for sector, _size, magic in descriptors
              if magic == 0x13FFF]
    ends = [sector * SECTOR + size for sector, size, magic in descriptors
            if magic == 0x13FFF]
    audit.check(len(starts) == OG_BANK_CAPACITY,
                "baseline bank descriptors do not all have 0x13FFF magic")
    if len(starts) == OG_BANK_CAPACITY:
        audit.check(starts[0] == STREAM_LO and ends[-1] == STREAM_HI,
                    "baseline bank stream bounds differ from fixed bounds")
        audit.check(all(ends[i] == starts[i + 1]
                        for i in range(len(starts) - 1)),
                    "baseline bank stream region is not contiguous")


def validate_audio(iso: Path, baseline: Path, clip_slots: dict[int, int],
                   audit: Audit) -> dict[str, Any]:
    _validate_baseline_audio_region(baseline, audit)
    active = len(clip_slots)
    with iso.open("rb") as fh:
        fh.seek(OG_SHARED + OG_BANK_TABLE + OG_AXEL_BANK * 8)
        header = fh.read(8)
        if len(header) != 8:
            audit.fail("target bank 1046 header is truncated")
            return {}
        ptr, count = struct.unpack("<II", header)
        audit.check(ptr == OG_BANK_PTR, f"target bank ptr 0x{ptr:X} != 0x{OG_BANK_PTR:X}")
        audit.check(count == OG_BANK_CAPACITY,
                    f"target bank descriptor count {count} != {OG_BANK_CAPACITY}")
        fh.seek(OG_SHARED + OG_BANK_TABLE + ptr)
        descriptors = []
        for _ in range(OG_BANK_CAPACITY):
            data = fh.read(12)
            descriptors.append(struct.unpack("<III", data)
                               if len(data) == 12 else (-1, -1, -1))

        cursor = STREAM_LO
        containers: list[dict[str, Any]] = []
        for slot in range(active):
            sector, size, magic = descriptors[slot]
            start = sector * SECTOR
            audit.check(start == cursor,
                        f"audio descriptor {slot} start 0x{start:X} != 0x{cursor:X}")
            audit.check(size >= 0x1000 and size % SECTOR == 0,
                        f"audio descriptor {slot} size 0x{size:X} is invalid")
            audit.check(magic == 0x13FFF,
                        f"audio descriptor {slot} magic 0x{magic:X} differs")
            if start != cursor or size <= 0 or cursor + size > STREAM_HI:
                cursor = max(cursor, cursor + max(size, 0))
                continue
            fh.seek(OG_STRM + start)
            container = fh.read(size)
            if len(container) != size:
                audit.fail(f"audio container {slot} is truncated")
                cursor += size
                continue
            if len(container) >= 0x810:
                magic4, version, data_off, region_size, preamble_size = \
                    struct.unpack_from("<4sIIII", container, 0)
                audit.check(magic4 == b"ILD\0" and version == 1,
                            f"audio container {slot} ILD magic/version differs")
                audit.check(data_off == 0x800 and region_size == size - 0x800 and
                            preamble_size == 0x10,
                            f"audio container {slot} ILD outer header differs")
                h = struct.unpack_from("<IIIIIII", container, 0x18)
                table_off, table_size, frame_hdr, channels, rate, zero, data_size = h
                audit.check(table_off == 0x20 and table_size == data_size + 0x10 and
                            frame_hdr == 0x10 and channels == 1 and
                            rate == SAMPLE_RATE and zero == 0,
                            f"audio container {slot} ILD inner header differs")
                audit.check(container[0x800:0x810] == b"\x00\x02" + b"\0" * 14,
                            f"audio container {slot} preamble differs")
                data_end = 0x810 + data_size
                audit.check(data_size > 0 and data_size % 16 == 0 and
                            data_end <= size,
                            f"audio container {slot} ADPCM data size is invalid")
                if data_size > 0 and data_size % 16 == 0 and data_end <= size:
                    frames = container[0x810:data_end]
                    audit.check(all(frames[pos + 1] == 0x02
                                    for pos in range(0, len(frames), 16)),
                                f"audio container {slot} ADPCM frame flag differs")
                    audit.check(all((frames[pos] >> 4) <= 4 and
                                    (frames[pos] & 0xF) <= 12
                                    for pos in range(0, len(frames), 16)),
                                f"audio container {slot} ADPCM filter/shift is invalid")
                    audit.check(not any(container[data_end:]),
                                f"audio container {slot} sector padding is nonzero")
                containers.append({
                    "slot": slot, "stream_offset": start, "size": size,
                    "data_size": data_size,
                })
            else:
                audit.fail(f"audio container {slot} shorter than ILD header")
            cursor += size

        if descriptors:
            for slot in range(active, OG_BANK_CAPACITY):
                audit.check(descriptors[slot] == descriptors[0],
                            f"unused descriptor {slot} is not descriptor-0 padding")
        audit.check(cursor <= STREAM_HI,
                    f"active audio ends at 0x{cursor:X} beyond 0x{STREAM_HI:X}")
        if cursor <= STREAM_HI:
            fh.seek(OG_STRM + cursor)
            remaining = STREAM_HI - cursor
            nonzero = False
            while remaining:
                block = fh.read(min(4 * 1024 * 1024, remaining))
                if len(block) == 0:
                    audit.fail("audio tail is truncated")
                    break
                if any(block):
                    nonzero = True
                remaining -= len(block)
            audit.check(not nonzero, "audio tail after active ILDs is not zero-filled")

    return {
        "bank": OG_AXEL_BANK, "descriptor_capacity": OG_BANK_CAPACITY,
        "active_descriptors": active, "stream_lo": f"0x{STREAM_LO:X}",
        "stream_hi": f"0x{STREAM_HI:X}",
        "used_bytes": cursor - STREAM_LO,
        "free_bytes": STREAM_HI - cursor,
        "containers_validated": len(containers),
    }


def validate_build_report(report: dict[str, Any], actual_sha: str,
                          payload: dict[str, Any], audio: dict[str, Any],
                          audit: Audit) -> None:
    audit.check(report.get("applied") is True, "build report is not applied")
    audit.check(report.get("before_sha256") == EXPECTED_BEFORE_SHA256,
                "build report before_sha256 differs")
    audit.check(report.get("sha256") == actual_sha,
                "build report SHA-256 differs from target")
    audit.check(report.get("bank_clips") == 171 and
                report.get("mapped_used_clips") == 171,
                "build report bank clip counts differ")
    audit.check(report.get("available_candidate_clips") == 212,
                "build report candidate clip count differs")
    audit.check(report.get("audio_bytes") == audio.get("used_bytes"),
                "build report audio_bytes differs from descriptors")
    audit.check(report.get("audio_free_bytes") == audio.get("free_bytes"),
                "build report audio_free_bytes differs from descriptors")
    stats = report.get("stats", {})
    expected_stats = {
        "live_trigger_rows": 1824, "voiced_rows": 1812,
        "unique_clips": 171, "unique_texts": payload.get("unique_texts"),
        "categories": EXPECTED_CATEGORIES, "recovered_native_rows": 7,
        "mixed_speaker_rows": 16,
    }
    for field, wanted in expected_stats.items():
        audit.check(stats.get(field) == wanted,
                    f"build report stats.{field} differs")
    for field in ("relationship_leaks", "weapon_mismatches",
                  "pure_shout_weapon", "cue_opposites",
                  "selector_cross_repeats", "adjacent_duplicates",
                  "critical_group_errors"):
        audit.check(stats.get(field) == [],
                    f"build report stats.{field} is not empty")
    restored = report.get("restored", {})
    for key, chunk in CHUNKS.items():
        item = restored.get(f"0x{key:X}", {})
        audit.check(item.get("rows") == chunk["n"] - 1 and
                    item.get("physical_capacity") == chunk["n"] and
                    item.get("pool_capacity") == chunk["pool_cap"],
                    f"build report restored 0x{key:X} differs")
        audit.check(item.get("pool_used") ==
                    payload.get("per_key", {}).get(f"0x{key:X}", {}).get("pool_used"),
                    f"build report 0x{key:X} pool usage differs")


def run(args: argparse.Namespace) -> dict[str, Any]:
    audit = Audit()
    audit.check(args.iso.stat().st_size == ISO_SIZE,
                f"target ISO size {args.iso.stat().st_size} != {ISO_SIZE}")
    audit.check(args.baseline.stat().st_size == ISO_SIZE,
                f"baseline ISO size {args.baseline.stat().st_size} != {ISO_SIZE}")

    baseline_sha = sha256_file(args.baseline)
    audit.check(baseline_sha == BASELINE_SHA256,
                f"baseline SHA-256 {baseline_sha} differs")
    actual_sha = sha256_file(args.iso)
    logical_sha = actual_sha
    replacements: list[tuple[int, bytes]] = []
    followup = None
    if args.followup_manifest is not None:
        followup = load_json(args.followup_manifest)
        audit.check(followup.get("after_sha256") == actual_sha,
                    "follow-up manifest after_sha256 differs from target")
        with args.iso.open("rb") as target:
            for item in followup.get("changes", []):
                offset = int(item["absolute_offset"], 16)
                new = bytes.fromhex(item["new_hex"])
                old = bytes.fromhex(item["old_hex"])
                audit.check(len(new) == len(old),
                            f"follow-up replacement length differs at 0x{offset:X}")
                target.seek(offset)
                audit.check(target.read(len(new)) == new,
                            f"follow-up target bytes differ at 0x{offset:X}")
                replacements.append((offset, old))
        logical_sha = patched_sha256(args.iso, replacements)
        audit.check(logical_sha == followup.get("before_sha256"),
                    "follow-up virtual rollback SHA-256 differs")
    masked_sha = (patched_sha256(args.iso, replacements, MASK_RANGES)
                  if replacements else masked_sha256(args.iso, MASK_RANGES))
    audit.check(masked_sha == EXPECTED_MASKED_SHA256,
                f"masked SHA-256 {masked_sha} differs")

    baseline_entry = read_region(args.baseline, ENTRY_BASE, ENTRY_SIZE)
    target_entry = read_region(args.iso, ENTRY_BASE, ENTRY_SIZE)
    manifest = load_json(args.manifest)
    clip_slots = validate_manifest(
        manifest, args.iso, args.runtime, logical_sha, audit)
    ap_rows = validate_ap_sources(args.runtime, audit)
    allowed_clips = independent_allowed_clips(args.runtime, audit)
    native_structure = validate_native_structure(
        target_entry, baseline_entry, audit)
    payload = validate_payloads(
        target_entry, baseline_entry, manifest, clip_slots, ap_rows,
        allowed_clips, audit)
    ptbl = validate_ptbl_plot(args.iso, audit)
    audio = validate_audio(args.iso, args.baseline, clip_slots, audit)

    if args.build_report is not None:
        report = load_json(args.build_report)
        validate_build_report(report, logical_sha, payload, audio, audit)

    result = {
        "kind": "PASS35 standalone independent Axel battle rebuild audit",
        "status": "PASS" if audit.error_count == 0 else "FAIL",
        "target": str(args.iso.resolve()),
        "sha256": actual_sha,
        "validated_source_sha256": logical_sha,
        "followup_manifest": (str(args.followup_manifest.resolve())
                              if args.followup_manifest is not None else None),
        "masked_sha256": masked_sha,
        "expected_masked_sha256": EXPECTED_MASKED_SHA256,
        "baseline_sha256": baseline_sha,
        "error_count": audit.error_count,
        "errors": audit.errors,
        "errors_truncated": audit.error_count > len(audit.errors),
        "native_structure": native_structure,
        "payload": payload,
        "ptbl_plot": ptbl,
        "audio": audio,
        "manifest": {
            "state": manifest.get("state"),
            "before_sha256": manifest.get("before_sha256"),
            "after_sha256": manifest.get("after_sha256"),
            "write_ranges": len(manifest.get("ranges", [])),
            "clip_slots": len(clip_slots),
            "ap_source_sha256": manifest.get("ap_source_sha256"),
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone independent static validator for safe Axel battle rebuild")
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--build-report", type=Path)
    parser.add_argument("--followup-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = run(args)
    except Exception as exc:
        result = {
            "kind": "PASS35 standalone independent Axel battle rebuild audit",
            "status": "FAIL", "error_count": 1,
            "errors": [f"validator exception: {type(exc).__name__}: {exc}"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
