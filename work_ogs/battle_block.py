# -*- coding: utf-8 -*-
"""BATTLE.BIN(LICE) 엔트리 #5 전투대사 블록 해석 공용 모듈.

블록 구조(캐릭터 raw키 하나당 1블록, 파일 내 raw키 오름차순 정렬):
    f1  u16[N]  문맥 ID (무기 ID / 상대 캐릭터 raw키 등)
    f2  u16[N]  (플래그 & 0xF800) | (캐릭터 raw키 & 0x07FF)
    f3  u16[N]  텍스트 풀 상대 오프셋
    f4  u32[N]  음성 ID
    pool        NUL 종료 문자열 풀 (OGs 한국어 코덱)

f2 의 하위 11비트가 PTbl 과 동일한 raw키 공간이라는 사실이 블록 신원을 준다.
베이스는 f2 로부터 f3=f2+2N, f4=f2+4N, pool=f2+8N 로 유도되며,
(f2, N) 후보를 실제 디코드 성공률로 검증해 확정한다.
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field
from pathlib import Path

from ogs_korean_codec import decode

BATTLE_LBA = 303679
SECTOR = 2048
BATTLE_BASE = BATTLE_LBA * SECTOR
LICE_DIR = 0x800          # "Wpbb" 디렉터리
ENTRY5_OFF = 0x6062E800   # 대사 블록 아카이브 엔트리
ENTRY5_SIZE = 0x2A8000

VOICE_LO = 0x0F0000
VOICE_HI = 0x0130000


@dataclass
class Block:
    key: int
    n: int
    f1: int
    f2: int
    f3: int
    f4: int
    pool: int
    score: float = 0.0
    records: list = field(default_factory=list)

    @property
    def start(self) -> int:
        return self.f1

    @property
    def pool_used(self) -> int:
        """풀에서 실제로 참조되는 마지막 바이트까지의 길이."""
        return max((r["off"] + r["len"] + 1 for r in self.records), default=0)


def read_entry5(iso: Path) -> bytes:
    with iso.open("rb") as fh:
        fh.seek(BATTLE_BASE)
        if fh.read(4) != b"LICE":
            raise SystemExit("LICE 매직 불일치 — BATTLE.BIN LBA 확인 필요")
        fh.seek(BATTLE_BASE + ENTRY5_OFF)
        d = fh.read(ENTRY5_SIZE)
    if len(d) != ENTRY5_SIZE:
        raise SystemExit("엔트리 #5 읽기 부족")
    return d


def scan_key_runs(d: bytes, min_len: int = 32) -> list[tuple[int, int, int]]:
    """f2 후보: 같은 raw키가 min_len개 이상 연속되는 u16 구간."""
    n = len(d) // 2
    u = struct.unpack("<%dH" % n, d[: n * 2])
    runs, i = [], 0
    while i < n:
        k = u[i] & 0x7FF
        if k == 0 or k == 0x7FF:
            i += 1
            continue
        j = i
        while j < n and (u[j] & 0x7FF) == k:
            j += 1
        if j - i >= min_len:
            runs.append((i * 2, j - i, k))
        i = max(j, i + 1)
    return runs


def _zlen(d: bytes, o: int, limit: int = 0x200) -> int:
    e = d.find(b"\x00", o, o + limit)
    return -1 if e < 0 else e - o


def _evaluate(d: bytes, key: int, f2: int, n: int) -> Block | None:
    f3, f4, pool = f2 + 2 * n, f2 + 4 * n, f2 + 8 * n
    if pool + 0x40 > len(d) or f2 < 2 * n:
        return None
    keyed = voiced = bounded = 0
    recs = []
    for k in range(n):
        c = struct.unpack_from("<H", d, f2 + k * 2)[0]
        if c == 0:
            recs.append(None)
            continue
        if (c & 0x7FF) != key:
            return None                      # 다른 캐릭터가 섞이면 후보 탈락
        keyed += 1
        v = struct.unpack_from("<I", d, f4 + k * 4)[0]
        if VOICE_LO <= v < VOICE_HI:
            voiced += 1
        off = struct.unpack_from("<H", d, f3 + k * 2)[0]
        # 정렬 검증: 참조 문자열은 풀 선두이거나 직전 바이트가 NUL이어야 한다
        if pool + off >= len(d):
            return None
        if off == 0 or d[pool + off - 1] == 0:
            bounded += 1
        ln = _zlen(d, pool + off)
        try:
            txt = decode(d[pool + off: pool + off + ln]) if ln > 0 else None
        except Exception:
            txt = None
        recs.append({
            "i": k,
            "trig": struct.unpack_from("<H", d, f1_of(f2, n) + k * 2)[0],
            "flag": c & 0xF800,
            "off": off, "len": max(ln, 0), "vid": v, "txt": txt,
        })
    if keyed == 0:
        return None
    # 경계 정합이 유일한 정렬 판정 기준 — ±2/±4 오정렬을 확실히 떨어뜨린다.
    # 음성ID 비율은 동점 시 보조 지표로만 쓴다.
    bounded_ratio = bounded / keyed
    score = bounded_ratio + 0.001 * (voiced / keyed)
    b = Block(key=key, n=n, f1=f1_of(f2, n), f2=f2, f3=f3, f4=f4, pool=pool,
              score=score, records=[r for r in recs if r])
    return b


def f1_of(f2: int, n: int) -> int:
    return f2 - 2 * n


def merge_runs(runs: list[tuple[int, int, int]],
               max_gap: int = 0x100) -> list[tuple[int, int, int]]:
    """블록 내부 0x0000 패딩 때문에 쪼개진 런을 하나로 합친다.

    간격이 max_gap 이상이면 같은 키라도 서로 다른 블록으로 본다.
    """
    out: list[list[int]] = []
    for start, cnt, key in sorted(runs):
        end = start + cnt * 2
        if out and start - (out[-1][0] + out[-1][1] * 2) < max_gap:
            prev = out[-1]
            prev[1] = (end - prev[0]) // 2
        else:
            out.append([start, cnt, key])
    return [tuple(x) for x in out]


def locate_block(d: bytes, key: int, runs) -> Block:
    """스캔 런들을 씨앗으로 (f2, N)을 확정한다."""
    if isinstance(runs, tuple):
        runs = [runs]
    best = None
    for start, cnt, _ in merge_runs(list(runs)):
        for f2 in range(start - 8, start + 12, 2):
            for n in range(max(cnt - 8, 8), cnt + 16):
                b = _evaluate(d, key, f2, n)
                if b and (best is None or b.score > best.score
                          or (b.score == best.score and b.n > best.n)):
                    best = b
    if best is None or best.score < 0.98:
        raise SystemExit(f"raw키 0x{key:X} 블록 확정 실패"
                         + (f" (최고 점수 {best.score:.3f})" if best else ""))
    return best


def blocks_by_key(d: bytes) -> dict[int, list[tuple[int, int, int]]]:
    out: dict[int, list] = {}
    for r in scan_key_runs(d):
        out.setdefault(r[2], []).append(r)
    return out


def pick_run(runs: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    """같은 키에 런이 여러 개면 가장 긴 것을 쓴다."""
    return max(runs, key=lambda r: r[1])
