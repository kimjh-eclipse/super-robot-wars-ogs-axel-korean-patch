# -*- coding: utf-8 -*-
"""A Portable 아군 액셀 대사·음성을 OGs 액셀 bank 1046에 정적으로 이식한다.

원본 ISO는 읽기 전용이며, --target 으로 지정한 복사본만 --apply 때 수정한다.
이 도구는 OGs 원본 액셀 청크(0x416/0x417)를 먼저 갱신한다. 그 다음 기존
apply_battle_chunk_content_swap.py 를 실행하면 플레이어 청크로 내용이 복사된다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

import battle_block as bb
from ogs_korean_codec import decode as korean_decode


# A Portable [K] ISO extents / SSTM
AP_DUMMY = 0x06D50000
AP_SHARED = 0x01C090000
AP_SNDSTRM = 0x024790000
AP_SSTM = 0x3800
AP_BANK_DIR = 0x350
AP_AXEL_BANK = 212
AP_KR_CHUNKS = (0x7C0000, 0x800000)

# OGs ISO extents / SSTM
OG_SHARED = 0x005DA000
OG_STRM = 0x087D1F800
OG_BANK_TABLE = 0xD0820
OG_AXEL_BANK = 1046
OG_BANK_CAPACITY = 194
OG_SHARED_SIZE = 0x265000

SAMPLE_RATE = 32000
SECTOR = 0x800


@dataclass(frozen=True)
class ARow:
    index: int
    trig: int
    voice_id: int
    text: bytes

    @property
    def clip(self) -> int:
        bank, clip = divmod(self.voice_id, 1000)
        if bank != AP_AXEL_BANK:
            raise ValueError(f"unexpected A Portable bank {bank} at row {self.index}")
        return clip


def align(value: int, unit: int) -> int:
    return (value + unit - 1) & -unit


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while d := fh.read(8 << 20):
            h.update(d)
    return h.hexdigest().upper()


def find_a_rows(iso: Path, key: int) -> list[ARow]:
    lo, hi = AP_KR_CHUNKS
    with iso.open("rb") as fh:
        fh.seek(AP_DUMMY + lo)
        d = fh.read(hi - lo)
    for o in range(0, len(d) - 0x40, 0x800):
        t = struct.unpack_from("<4H", d, o + 0x18)
        if not all(t[i] < t[i + 1] for i in range(3)):
            continue
        if t[1] - t[0] != t[2] - t[1]:
            continue
        n = (t[1] - t[0]) // 2
        if not (1 <= n <= 1000) or abs(t[3] - t[2] - 4 * n) > 8:
            continue
        if (struct.unpack_from("<H", d, o + t[0])[0] & 0x7FF) != key:
            continue
        out = []
        f1 = o + t[0] - 2 * n
        for i in range(n):
            tag = struct.unpack_from("<H", d, o + t[0] + i * 2)[0]
            if (tag & 0x7FF) != key:
                continue
            off = struct.unpack_from("<H", d, o + t[1] + i * 2)[0]
            end = d.find(b"\0", o + t[3] + off)
            voice = struct.unpack_from("<I", d, o + t[2] + i * 4)[0]
            out.append(ARow(i, struct.unpack_from("<H", d, f1 + i * 2)[0],
                            voice, d[o + t[3] + off:end]))
        return out
    raise ValueError(f"A Portable chunk 0x{key:X} not found")


def make_pools(rows: list[ARow], awakened: bool) -> dict[str, list[ARow]]:
    if not awakened:
        spans = {
            "general": range(0, 9),
            "damage": range(9, 29),
            "defense": range(29, 53),
            "assist": range(53, 68),
            "weapon": range(68, 150),
        }
    else:
        # W17·레몬·빈델을 직접 부르는 적대 전용 문장은 제외한다.
        damage_ex = {28, 29, 30, 31, 37, 38, 39, 40, 48, 49, 50}
        defense_ex = set(range(59, 61)) | set(range(67, 77))
        spans = {
            "general": range(0, 10),
            "damage": [i for i in range(20, 51) if i not in damage_ex],
            "defense": [i for i in range(51, 87) if i not in defense_ex],
            "assist": range(87, 104),
            "weapon": range(108, 193),
        }
    pools = {}
    for name, indices in spans.items():
        pools[name] = [rows[i] for i in indices if i < len(rows) and rows[i].voice_id]
        if not pools[name]:
            raise ValueError(f"empty pool: {name}")
    # 이름이 명시된 무기는 서로 섞지 않는다. 한 레코드가 복수 키워드를
    # 포함할 수 있으므로 첫 일치 키워드를 대표 그룹으로 쓴다.
    weapon_words = {
        "matrix": ("매트릭스",),
        "halbert": ("할버트", "할버드"),
        "sword_breaker": ("소드", "브레이커"),
        "rekkajin": ("열화인",),
        "suiryuso": ("수류조아",),
        "shippudo": ("질공도",),
        "fujinsen": ("풍인섬", "광인섬"),
        "seiryurin": ("청룡린",),
        "genbugodan": ("현무강탄",),
        "byakkoko": ("백호교",),
        "maishujaku": ("무주작",),
        "kirin": ("코드", "기린", "소울게인", "파이널"),
    }
    for group, words in weapon_words.items():
        selected = []
        for row in pools["weapon"]:
            text = korean_decode(row.text).replace("　", "")
            if any(word in text for word in words):
                selected.append(row)
        if selected:
            pools[f"weapon:{group}"] = selected
    return pools


WEAPON_WORDS = {
    "matrix": ("매트릭스", "マトリクス"),
    "halbert": ("할버트", "할버드", "ハルバート"),
    "sword_breaker": ("소드", "브레이커", "ソードブレイカー"),
    "rekkajin": ("열화인", "烈火刃"),
    "suiryuso": ("수류조아", "水流爪牙"),
    "shippudo": ("질공도", "疾空刀"),
    "fujinsen": ("풍인섬", "광인섬", "風刃閃", "光刃閃"),
    "seiryurin": ("청룡린", "青龍鱗"),
    "genbugodan": ("현무강탄", "玄武剛弾"),
    "byakkoko": ("백호교", "白虎咬"),
    "maishujaku": ("무주작", "舞朱雀"),
    "kirin": ("코드기린", "코드麒麟", "コード麒麟", "소울게인", "ソウルゲイン",
              "파이널코드", "기린", "麒麟"),
}


def _semantic_text(raw: bytes) -> str:
    kr = korean_decode(raw).replace("　", "").replace(" ", "")
    jp = raw.decode("shift_jis", "replace").replace("　", "").replace(" ", "")
    return kr + "|" + jp


def category(flag: int, raw_text: bytes) -> str:
    text = _semantic_text(raw_text)
    for group, words in WEAPON_WORDS.items():
        if any(word.replace(" ", "") in text for word in words):
            return f"weapon:{group}"
    damage_words = ("크윽", "으아", "아악", "여기까지", "한계", "장갑", "피격",
                    "くっ", "ぐう", "うぐ", "ここまで", "装甲", "被弾", "ぬかった")
    defense_words = ("회피", "피할", "소용없", "안통", "맞아주", "못맞",
                     "回避", "かわせ", "かわし", "当たっては", "通じん", "無駄")
    assist_words = ("원호", "사거리", "범위밖", "놓쳐", "편승", "지원",
                    "援護", "射程", "範囲外", "逃げら", "便乗")
    if any(word in text for word in damage_words):
        return "damage"
    if any(word in text for word in defense_words):
        return "defense"
    if any(word in text for word in assist_words):
        return "assist"
    if flag == 0x1800:
        return "damage"
    if flag in (0x2000, 0x3800):
        return "defense"
    if flag == 0x7000:
        return "weapon"
    # 0x0800에는 범용 공격·피격·상대 전용 문장이 혼재한다. 위의 문장
    # 판별에 걸리지 않은 경우에는 이름 없는 범용 공격으로 취급한다.
    return "general"


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


def plan_chunk(d: bytes, c: dict, key: int, pools: dict[str, list[ARow]]):
    n = c["n"]
    f1 = c["f2"] - 2 * n
    counters = {name: 0 for name in pools}
    chosen: list[tuple[int, int, ARow]] = []
    for i in range(n):
        tag = struct.unpack_from("<H", d, c["f2"] + i * 2)[0]
        if (tag & 0x7FF) != key:
            continue
        flag = tag & 0xF800
        text_off = struct.unpack_from("<H", d, c["f3"] + i * 2)[0]
        text_end = d.find(b"\0", c["pool"] + text_off)
        raw_text = d[c["pool"] + text_off:text_end]
        name = category(flag, raw_text)
        if name not in pools:
            name = "weapon" if name.startswith("weapon:") else "general"
        pool = pools[name]
        row = pool[counters[name] % len(pool)]
        counters[name] += 1
        chosen.append((i, flag, row))
    if not chosen:
        raise ValueError(f"OGs source chunk 0x{key:X} has no valid records")
    return chosen, f1


def build_chunk_writes(d: bytes, c: dict, key: int, chosen, clip_slots):
    n = c["n"]
    f1o = c["f2"] - 2 * n
    a1, a2, a3, a4 = bytearray(2*n), bytearray(2*n), bytearray(2*n), bytearray(4*n)
    pool = bytearray()
    strings: dict[bytes, int] = {}
    for out_i, (_old_i, flag, row) in enumerate(chosen):
        if row.text in strings:
            off = strings[row.text]
        else:
            off = len(pool)
            strings[row.text] = off
            pool += row.text + b"\0"
        struct.pack_into("<H", a1, out_i*2,
                         struct.unpack_from("<H", d, f1o + _old_i*2)[0])
        struct.pack_into("<H", a2, out_i*2, flag | key)
        struct.pack_into("<H", a3, out_i*2, off)
        struct.pack_into("<I", a4, out_i*4,
                         OG_AXEL_BANK * 1000 + clip_slots[row.clip])
    if len(pool) > c["pool_cap"]:
        raise ValueError(f"chunk 0x{key:X} pool overflow: {len(pool)}>{c['pool_cap']}")
    return [(f1o, bytes(a1)), (c["f2"], bytes(a2)), (c["f3"], bytes(a3)),
            (c["f4"], bytes(a4)), (c["pool"], bytes(pool))], len(pool)


def a_riff(iso: Path, clip: int) -> bytes:
    with iso.open("rb") as fh:
        sstm = AP_SHARED + AP_SSTM
        fh.seek(sstm + AP_BANK_DIR + AP_AXEL_BANK * 8)
        ptr, count_flags = struct.unpack("<II", fh.read(8))
        count = count_flags & 0xFFFF
        if not 0 <= clip < count:
            raise ValueError(f"A Portable clip {clip} outside 0..{count-1}")
        fh.seek(sstm + AP_BANK_DIR + ptr + clip * 16)
        enabled, off, size, _volume = struct.unpack("<IIII", fh.read(16))
        if not enabled:
            raise ValueError(f"A Portable clip {clip} disabled")
        fh.seek(AP_SNDSTRM + off)
        riff = fh.read(size)
    if riff[:4] != b"RIFF" or riff[8:12] != b"WAVE":
        raise ValueError(f"A Portable clip {clip} is not RIFF/WAVE")
    return riff


def riff_samples(riff: bytes) -> int:
    pos = riff.find(b"fact")
    if pos < 0:
        raise ValueError("ATRAC RIFF has no fact chunk")
    return struct.unpack_from("<I", riff, pos + 8)[0]


FILTERS = ((0, 0), (60, 0), (115, -52), (98, -55), (122, -60))


def encode_psx_adpcm(pcm: bytes) -> bytes:
    samples = list(struct.unpack(f"<{len(pcm)//2}h", pcm))
    samples.extend([0] * ((28 - len(samples) % 28) % 28))
    out = bytearray()
    hist1 = hist2 = 0
    for base in range(0, len(samples), 28):
        frame = samples[base:base+28]
        # Filter selection uses the unquantized frame with the current history.
        best_filter, best_peak = 0, None
        for fi, (c1, c2) in enumerate(FILTERS):
            s1, s2, peak = hist1, hist2, 0
            for sample in frame:
                pred = (s1*c1 + s2*c2 + 32) >> 6
                peak = max(peak, abs(sample - pred))
                s2, s1 = s1, sample
            if best_peak is None or peak < best_peak:
                best_filter, best_peak = fi, peak
        shift = 0
        while shift < 12 and best_peak < (7 << (12-shift-1)):
            shift += 1
        c1, c2 = FILTERS[best_filter]
        step = 1 << (12-shift)
        nibbles = []
        for sample in frame:
            pred = (hist1*c1 + hist2*c2 + 32) >> 6
            q = int(round((sample - pred) / step))
            q = max(-8, min(7, q))
            recon = max(-32768, min(32767, pred + q*step))
            hist2, hist1 = hist1, recon
            nibbles.append(q & 0xF)
        out += bytes([(best_filter << 4) | shift, 0x02])
        out += bytes(nibbles[i] | (nibbles[i+1] << 4) for i in range(0, 28, 2))
    return bytes(out)


def decode_atrac(ffmpeg: Path, riff: bytes) -> bytes:
    cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
           "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1"]
    proc = subprocess.run(cmd, input=riff, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace"))
    return proc.stdout


def make_ild(vag: bytes) -> bytes:
    data_size = len(vag)
    total = align(0x810 + data_size, SECTOR)
    out = bytearray(total)
    struct.pack_into("<4sIIII", out, 0, b"ILD\0", 1, 0x800, total-0x800, 0x10)
    struct.pack_into("<IIIIIII", out, 0x18, 0x20, data_size+0x10,
                     0x10, 1, SAMPLE_RATE, 0, data_size)
    out[0x800:0x810] = b"\x00\x02" + b"\0"*14
    out[0x810:0x810+data_size] = vag
    return bytes(out)


def og_bank_region(iso: Path):
    with iso.open("rb") as fh:
        fh.seek(OG_SHARED + OG_BANK_TABLE + OG_AXEL_BANK*8)
        ptr, count = struct.unpack("<II", fh.read(8))
        if count != OG_BANK_CAPACITY:
            raise ValueError(f"OGs bank {OG_AXEL_BANK} count {count} != {OG_BANK_CAPACITY}")
        fh.seek(OG_SHARED + OG_BANK_TABLE + ptr)
        recs = [struct.unpack("<III", fh.read(12)) for _ in range(count)]
    starts = [sector*SECTOR for sector, _size, magic in recs if magic == 0x13FFF]
    ends = [sector*SECTOR+size for sector, size, magic in recs if magic == 0x13FFF]
    if len(starts) != count or any(ends[i] != starts[i+1] for i in range(count-1)):
        raise ValueError("OGs bank 1046 STRM region is not contiguous")
    return ptr, starts[0], ends[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aportable", type=Path, required=True)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--chunks", type=Path, default=Path("runtime/entry5_chunks.json"))
    ap.add_argument("--ffmpeg", type=Path, default=Path(
        "ffmpeg"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", type=Path, default=Path("runtime/aportable_voice_port_backup.bin"))
    ap.add_argument("--manifest", type=Path, default=Path("runtime/aportable_voice_port.json"))
    args = ap.parse_args()

    a4, a5 = find_a_rows(args.aportable, 0xD4), find_a_rows(args.aportable, 0xD5)
    pools4, pools5 = make_pools(a4, False), make_pools(a5, True)
    entry = bb.read_entry5(args.target)
    chunks = load_chunks(args.chunks)
    chosen4, _ = plan_chunk(entry, chunks[0x416], 0x416, pools4)
    chosen5, _ = plan_chunk(entry, chunks[0x417], 0x417, pools5)
    clips = sorted({row.clip for _i, _flag, row in chosen4 + chosen5})
    if len(clips) > OG_BANK_CAPACITY:
        raise ValueError(f"selected {len(clips)} unique clips > {OG_BANK_CAPACITY}")
    clip_slots = {clip: i for i, clip in enumerate(clips)}
    writes4, pool4 = build_chunk_writes(entry, chunks[0x416], 0x416, chosen4, clip_slots)
    writes5, pool5 = build_chunk_writes(entry, chunks[0x417], 0x417, chosen5, clip_slots)
    ptr, stream_lo, stream_hi = og_bank_region(args.target)

    estimate = 0
    for clip in clips:
        samples = riff_samples(a_riff(args.aportable, clip))
        out_samples = math.ceil(samples * SAMPLE_RATE / 44100)
        estimate += align(0x810 + math.ceil(out_samples/28)*16, SECTOR)
    print(f"A rows: D4={len(a4)}, D5={len(a5)}")
    print(f"OG source records: 0x416={len(chosen4)}, 0x417={len(chosen5)}")
    print(f"unique transplanted clips: {len(clips)}/{OG_BANK_CAPACITY}")
    print(f"pools: 0x416=0x{pool4:X}/{chunks[0x416]['pool_cap']:X}, "
          f"0x417=0x{pool5:X}/{chunks[0x417]['pool_cap']:X}")
    print(f"STRM capacity=0x{stream_hi-stream_lo:X}, estimated=0x{estimate:X}, "
          f"margin=0x{stream_hi-stream_lo-estimate:X}")
    if estimate > stream_hi-stream_lo:
        raise ValueError("selected audio does not fit OGs bank 1046 region")
    if not args.apply:
        print("(--apply 없음: 파일 미수정)")
        return

    containers = []
    for pos, clip in enumerate(clips, 1):
        pcm = decode_atrac(args.ffmpeg, a_riff(args.aportable, clip))
        containers.append(make_ild(encode_psx_adpcm(pcm)))
        if pos % 20 == 0 or pos == len(clips):
            print(f"encode {pos}/{len(clips)}")
    packed = b"".join(containers)
    if len(packed) > stream_hi-stream_lo:
        raise ValueError("encoded audio exceeds OGs bank region")

    desc = bytearray()
    cursor = stream_lo
    for ild in containers:
        desc += struct.pack("<III", cursor//SECTOR, len(ild), 0x13FFF)
        cursor += len(ild)
    first_desc = bytes(desc[:12])
    while len(desc) < OG_BANK_CAPACITY*12:
        desc += first_desc

    ranges = []
    entry_base = bb.BATTLE_BASE + bb.ENTRY5_OFF
    for off, data in writes4 + writes5:
        ranges.append((entry_base + off, data, "battle"))
    ranges.append((OG_SHARED + OG_BANK_TABLE + ptr, bytes(desc), "descriptors"))
    ranges.append((OG_STRM + stream_lo,
                   packed + b"\0"*((stream_hi-stream_lo)-len(packed)), "strm"))

    backup = bytearray()
    meta = []
    with args.target.open("r+b") as fh:
        for off, data, kind in ranges:
            fh.seek(off)
            old = fh.read(len(data))
            meta.append({"iso_offset": off, "length": len(data),
                         "backup_pos": len(backup), "kind": kind})
            backup += old
        for off, data, _kind in ranges:
            fh.seek(off)
            fh.write(data)
    args.backup.parent.mkdir(parents=True, exist_ok=True)
    args.backup.write_bytes(backup)
    args.manifest.write_text(json.dumps({
        "kind": "aportable-axel-voice-port-to-ogs",
        "target": str(args.target.resolve()),
        "target_sha256_after": sha256_file(args.target),
        "sample_rate": SAMPLE_RATE,
        "a_bank": AP_AXEL_BANK, "og_bank": OG_AXEL_BANK,
        "clips": clips, "clip_slots": {str(k): v for k, v in clip_slots.items()},
        "packed_size": len(packed), "stream_capacity": stream_hi-stream_lo,
        "ranges": meta,
        "backup_sha256": hashlib.sha256(backup).hexdigest().upper(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"applied: {args.target}")
    print(f"backup: {args.backup} ({len(backup)} bytes)")
    print(f"manifest: {args.manifest}")


if __name__ == "__main__":
    main()
