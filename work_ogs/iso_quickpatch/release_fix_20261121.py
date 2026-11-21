# -*- coding: utf-8 -*-
"""v20261116 공개 64조합 위에 11/16~11/21 로컬 수정 3건을 얹는 정비 릴리즈 (클로드, 2026-11-21).

원칙(코덱스 build_cutin_release와 동일): 공개된 데이터로만 조합을 재구성하고, 작업용 ISO(개인 변경 포함)는
읽기 전용으로 둔다. 각 수정은 runtime 기록의 (오프셋, 수정 전, 수정 후) 바이트를 그대로 쓰며,
조합마다 '수정 전' 바이트가 정확히 일치할 때만 적용한다.

수정 순서(작업용 ISO 해시 사슬 6816D09E → 9E94B703 → 7C3DB658 → 3EF57FD4):
  1. 잉그램 R-GUN 일반 공격 대사      runtime/ingram_normal_attack_fix_20261116.json
  2. Mk-III 트롬베 공존              runtime/trombe_coexist_20261119.json
  3. 오우카 중복·워단 대사·전환 코드  runtime/mobile_bug_20261121/fix_manifest.json

사용:
  python -X utf8 release_fix_20261121.py --check   조합별 적용 가능 여부만 보고(쓰기 없음)
  python -X utf8 release_fix_20261121.py --build   새 OGS_beowulf_options.bin + 64 해시 생성
"""
import concurrent.futures
import hashlib
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / 'baseline' / 'srwogs-v1.4.3s1.iso'
TARGET = ROOT / 'build' / 'SRWOGS_K.iso'
PREVIOUS = 'v20261116'
VERSION = 'v20261121'
PREV_ZIP = ROOT / 'dist' / f'SRWOGS_AxelRoleSwap_kr_{PREVIOUS}.zip'
PREV_ZIP_SHA = None  # 공개 자산 digest 로 검증(아래 main)
MAIN_PATH_KEY = 'SRWOGS_K.iso'
FIXES = [
    ('ingram_rgun', ROOT / 'runtime' / 'ingram_normal_attack_fix_20261116.json'),
    ('trombe_coexist', ROOT / 'runtime' / 'trombe_coexist_20261119.json'),
    ('ouka_wodan_trampoline', ROOT / 'runtime' / 'mobile_bug_20261121' / 'fix_manifest.json'),
]


def file_hash(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while b := f.read(16 << 20):
            h.update(b)
    return h.hexdigest().upper()


def U(f):
    return struct.unpack('<I', f.read(4))[0]


def triples(f):
    rows = []
    for _ in range(U(f)):
        at, n = struct.unpack('<QI', f.read(12))
        a, b = f.read(n), f.read(n)
        assert len(a) == len(b) == n
        rows.append((at, a, b))
    return rows


class View:
    def __init__(self, file, es=()):
        self.file = file
        self.es = []
        self.bins = {}
        for at, b in es:
            self.put(at, b)

    def put(self, at, b):
        b = bytes(b)
        idx = len(self.es)
        self.es.append((at, b))
        for block in range(at >> 16, ((at + len(b) - 1) >> 16) + 1):
            self.bins.setdefault(block, []).append(idx)

    def get(self, at, n):
        self.file.seek(at)
        out = bytearray(self.file.read(n))
        assert len(out) == n
        ids = set()
        for block in range(at >> 16, ((at + n - 1) >> 16) + 1):
            ids.update(self.bins.get(block, ()))
        for idx in sorted(ids):
            p, b = self.es[idx]
            lo, hi = max(p, at), min(p + len(b), at + n)
            if lo < hi:
                out[lo - at:hi - at] = b[lo - p:hi - p]
        return bytes(out)

    def apply(self, rr):
        for at, a, b in rr:
            assert self.get(at, len(a)) == a, ('source guard', hex(at))
            self.put(at, b)

    # Plan/Archive(build_beowulf_prototype)가 파일처럼 읽을 수 있게 한다.
    def seek(self, at):
        self.pos = at

    def read(self, n):
        b = self.get(self.pos, n)
        self.pos += n
        return b


def spans(es):
    out = []
    for at, b in sorted(es, key=lambda e: e[0]):
        end = at + len(b)
        if out and at <= out[-1][1] + 64:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([at, end])
    return out


def differences(a, b, regions):
    rr = []
    for lo, hi in regions:
        x = a.get(lo, hi - lo)
        y = b.get(lo, hi - lo)
        p = np.flatnonzero(np.frombuffer(x, np.uint8) != np.frombuffer(y, np.uint8))
        if not len(p):
            continue
        cuts = np.flatnonzero(np.diff(p) > 65)
        for i, j in zip(np.r_[0, cuts + 1], np.r_[cuts, len(p) - 1]):
            l, r = int(p[i]), int(p[j]) + 1
            rr.append((lo + l, x[l:r], y[l:r]))
    return rr


def load_previous():
    z = zipfile.ZipFile(PREV_ZIP)

    def option(name):
        f = io.BytesIO(z.read('patcher/' + name))
        assert f.read(8) == b'OGSHID01'
        f.read(72)
        return triples(f)
    f = io.BytesIO(z.read('patcher/OGS_ISO_ranges.bin'))
    assert f.read(9) == b'OGSAXLRNG' and U(f) == 1
    f.read(struct.unpack('<H', f.read(2))[0])
    size = struct.unpack('<Q', f.read(8))[0]
    sourcehash = f.read(32)
    f.read(32)
    base = []
    for _ in range(U(f)):
        at, n = struct.unpack('<QI', f.read(12))
        base.append((at, f.read(n)))
    hidden, bundle, both = [option(n) for n in ('OGS_hidden_rewards.bin', 'OGS_ouka_zengar.bin', 'OGS_ouka_zengar_hidden.bin')]
    f = io.BytesIO(z.read('patcher/OGS_optional_features.bin'))
    assert f.read(8) == b'OGSOPT02'
    f.read(40)
    assert U(f) == 32
    f.read(32 * 36)
    assert U(f) == 3
    features = {}
    for _ in range(3):
        bit = U(f)
        features[bit] = triples(f)
    f = io.BytesIO(z.read('patcher/OGS_common_fix.bin'))
    assert f.read(8) == b'OGSFIX02'
    f.read(8)
    assert U(f) == 32
    common, anchors = [], []
    for mask in range(32):
        assert U(f) == mask
        f.read(32)
        anchors.append(f.read(32))
        common.append(triples(f))
    f = io.BytesIO(z.read('patcher/OGS_beowulf_options.bin'))
    assert f.read(8) == b'OGSBEO02'
    assert struct.unpack('<Q', f.read(8))[0] == size and U(f) == 64
    pool = [f.read(U(f)) for _ in range(U(f))]
    profiles = []
    for mask in range(64):
        assert U(f) == mask
        anchor = f.read(32)
        digest = f.read(32)
        rr = []
        for _ in range(U(f)):
            at, n, a, b = struct.unpack('<QIII', f.read(20))
            assert len(pool[a]) == len(pool[b]) == n
            rr.append((at, pool[a], pool[b]))
        assert anchor == anchors[mask & 31]
        profiles.append((digest, rr))
    aliases = []
    for _ in range(U(f)):
        mask = U(f)
        source = f.read(32)
        anchor = f.read(32)
        rr = []
        for _ in range(U(f)):
            at, n, b = struct.unpack('<QII', f.read(16))
            assert len(pool[b]) == n
            rr.append((at, pool[b]))
        aliases.append((mask, source, anchor, rr))
    assert f.tell() == len(f.getbuffer()) and len(aliases) % 64 == 0
    hashes_json = json.loads(z.read('옵션별_ISO_SHA256.json'))
    return dict(size=size, sourcehash=sourcehash, base=base, hidden=hidden, bundle=bundle, both=both,
                features=features, common=common, anchors=anchors, profiles=profiles, aliases=aliases,
                public_hashes=[p['sha256'] for p in hashes_json['profiles']])


def fix_edits():
    """수정별 (offset, before, after) 목록. 작업용 ISO(SRWOGS_K.iso) 기록을 쓴다."""
    out = []
    for name, path in FIXES:
        d = json.loads(path.read_text(encoding='utf-8'))
        f = next(x for x in d['files'] if x['path'].endswith(MAIN_PATH_KEY))
        if 'edits' in f:
            es = [(e['offset'], bytes.fromhex(e['before']), bytes.fromhex(e['after'])) for e in f['edits']]
        else:
            es = [(f['offset'], bytes.fromhex(f['before']), bytes.fromhex(f['after']))]
        es = [(at, a, b) for at, a, b in es if a != b]
        out.append((name, es, f['before_sha256'], f['after_sha256']))
    return out


def profile_view(P, bf, mask):
    anchor = View(bf, P['base'])
    if mask & 1:
        anchor.apply(P['hidden'])
    if mask & 2:
        anchor.apply(P['both'] if mask & 1 else P['bundle'])
    for bit, rr in P['features'].items():
        if mask & bit:
            anchor.apply(rr)
    anchor.apply(P['common'][mask & 31])
    v = View(bf, anchor.es)
    v.apply(P['profiles'][mask][1])
    return anchor, v


ELF = lambda pc: 0x94880 + pc - 0x100000


def ouka_wodan_edits(v):
    """fix_ouka_wodan_map_20261121.build()를 조합별로 다시 계산한다.

    원본 build()는 작업용 ISO 기준으로 메뉴 연결 대상(0x49B800)과 트롬베 적용 후 상태를 고정한다.
    공개 조합은 트롬베 기록을 거치지 않고 바로 이 결과를 얹는다(트롬베가 쓴 자리는 이 수정이 모두
    다시 쓰거나 원래 바이트로 되돌리므로 합성 결과가 같다). 연결 대상은 조합의 0x431778 값을 따른다.
    """
    sys.path.insert(0, str(ROOT))
    import fix_ouka_wodan_map_20261121 as fx
    from build_beowulf_prototype import Plan, Archive, u16, u32 as U32
    w = struct.unpack('<I', v.get(ELF(0x431778), 4))[0]
    target = (w & 0x3ffffff) << 2
    assert w >> 26 == 2 and target in (0x49b400, 0x49b800), hex(w)
    p = Plan(v)
    extra_start, extra_code, cleanup, chain = fx.cleanup_block()
    code = bytearray(extra_code)
    hits = [i for i in range(0, len(code), 4) if struct.unpack_from('<I', code, i)[0] == fx.J(0x49b800)]
    assert len(hits) == 1
    struct.pack_into('<I', code, hits[0], fx.J(target))
    p.add(ELF(extra_start), bytes(code), 'Preserved startup + safe intermission duplicate cleanup')
    relocated = fx.relocated_trombe(target)
    block = bytearray(relocated[0x200940])
    assert U32(block, len(block) - 8) == fx.J(target)
    struct.pack_into('<I', block, len(block) - 8, fx.J(chain))
    relocated[0x200940] = bytes(block)
    for pc, data in relocated.items():
        p.add(ELF(pc), data, 'Preserved initialization + executable conversion hooks')
    p.add(ELF(0x2da480), fx.pack([fx.J(0x2009f4), 0]), 'Safe conversion handler')
    p.add(ELF(0x431778), fx.pack([fx.J(0x200a60), 0x902d]), 'Safe Trombe recovery entry')
    unit, pilot, data = fx.allocation_code()
    p.add(ELF(unit), data, 'Reuse existing Ouka/Wodan unit and pilot slots')
    p.add(ELF(0x1d5a3c), fx.pack([fx.J(unit, True)]), 'Unit allocation wrapper')
    p.add(ELF(0x1d5d98), fx.pack([fx.J(pilot, True)]), 'Pilot allocation wrapper')
    voice = Archive(v, 0x8574e800)
    assert voice.mapping[0x602] == 65535
    raw = voice.get(v, 0x42d)
    clone = bytearray(raw)
    h = struct.unpack_from('<16H', raw)
    count = 0
    for off in range(h[12], h[13], 2):
        tag = u16(raw, off)
        if tag & 0x7ff == 0x42d:
            struct.pack_into('<H', clone, off, (tag & 0xf800) | 0x602)
            count += 1
    assert count > 0
    p.cursor = max(o + n for base in (0x25120800, 0x27d66800, 0x2970d000, 0x8574e800) for o, n in Archive(v, base).entries)
    span = p.archive(voice, [(0x602, bytes(clone), 'Allied Wodan speech: original lines/voice IDs, separate pilot key')])
    p.add(0x25120000 + 8 + 5 * 8 + 4, fx.pack([span]), 'Speech archive span')
    es = sorted(p.edits)
    for x, y in zip(es, es[1:]):
        assert x[0] + len(x[1]) <= y[0], (x[3], y[3])
    return [(at, old, new) for at, old, new, label in es], dict(target=hex(target), wodan_retagged_rows=count)


def compose(P, bf, mask, fixes):
    """mask 조합 = v20261116 공개 결과 + 잉그램 대사 + 조합별 재계산한 트롬베·오우카·워단 수정."""
    anchor, v = profile_view(P, bf, mask)
    name, es, _, _ = fixes[0]
    assert name == 'ingram_rgun'
    v.apply(es)
    branch_scan(v)  # 코덱스 validate와 같이 수정 '전' 실행 파일의 원래 분기를 검사
    rr, info = ouka_wodan_edits(v)
    v.apply(rr)
    return anchor, v, info


def check_equivalence():
    """작업용 ISO와 같은 조건(숨김 ON·베오울프 OFF) 조합에서 기록 바이트 재생과 생성기 결과가 같은지."""
    P = load_previous()
    fixes = fix_edits()
    with SOURCE.open('rb') as bf:
        for mask in (1, 3, 31):
            _, recorded = profile_view(P, bf, mask)
            for name, es, _, _ in fixes:
                recorded.apply(es)
            _, generated, info = compose(P, bf, mask, fixes)
            regions = spans([(at, b) for at, b in recorded.es] + [(at, b) for at, b in generated.es])
            same = all(recorded.get(lo, hi - lo) == generated.get(lo, hi - lo) for lo, hi in regions)
            print('mask', mask, '기록 재생 == 생성기:', same, info, flush=True)
            assert same
        for mask in (0, 32, 33, 62, 63):
            _, v, info = compose(P, bf, mask, fixes)
            print('mask', mask, '생성 성공', info, flush=True)


def branch_scan(v):
    """원래 코드의 어떤 분기도 새로 쓴 직선 코드 블록 '중간'으로 들어오지 않는지 (코덱스 validate와 같은 기준)."""
    elf = v.get(0x94880, 0x39a6f0)
    w = np.frombuffer(elf, '<u4')
    op = w >> 26
    pc = 0x100000 + np.arange(len(w), dtype=np.int64) * 4
    jt = (w & 0x3ffffff).astype(np.int64) << 2
    imm = (w & 0xffff).astype(np.int64)
    imm = np.where(imm & 0x8000, imm - 0x10000, imm)
    bt = pc + 4 + imm * 4
    target = np.where(np.isin(op, (2, 3)), jt, np.where(np.isin(op, (1, 4, 5, 6, 7, 20, 21, 22, 23)), bt, -1))
    for lo, hi in ((0x200514, 0x20068c), (0x200940, 0x200abc), (0x1feea0, 0x1ff294)):
        bad = np.flatnonzero((target > lo) & (target < hi))
        assert not len(bad), ('incoming branch', [hex(int(pc[i])) for i in bad[:4]])


def build():
    """새 OGS_beowulf_options.bin (64조합) + 전체 ISO 해시 + 기본 조합 시험 ISO."""
    P = load_previous()
    fixes = fix_edits()
    size = P['size']
    assert file_hash(SOURCE) == P['sourcehash'].hex().upper()
    production = file_hash(TARGET)
    plans, flatviews, flatpool, infos = [], [], {}, []
    with SOURCE.open('rb') as bf:
        for mask in range(64):
            anchor, v, info = compose(P, bf, mask, fixes)
            w =struct.unpack('<I', v.get(ELF(0x431778), 4))[0]
            assert w == 2 << 26 | 0x200a60 >> 2
            regions = spans([(at, b) for at, a, b in P['profiles'][mask][1]] + v.es[len(anchor.es):])
            rr = differences(anchor, v, regions)
            plans.append(rr)
            flat = []
            for lo, hi in spans(v.es):
                data = v.get(lo, hi - lo)
                key = hashlib.sha256(data).digest()
                data = flatpool.setdefault(key, data)
                flat.append((lo, data))
            flatviews.append(flat)
            infos.append(dict(mask=mask, **info))
            print('profile ready', mask, info, flush=True)
        hashes = [hashlib.sha256() for _ in range(64)]
        bf.seek(0)
        offset = 0
        last = -1

        def feed(args):
            h, es, raw, pos = args
            out = None
            for at, b in es:
                lo, hi = max(at, pos), min(at + len(b), pos + len(raw))
                if lo < hi:
                    if out is None:
                        out = bytearray(raw)
                    out[lo - pos:hi - pos] = b[lo - at:hi - at]
            h.update(raw if out is None else out)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            while raw := bf.read(16 << 20):
                list(ex.map(feed, [(h, es, raw, offset) for h, es in zip(hashes, flatviews)]))
                offset += len(raw)
                pr = offset * 10 // size
                if pr != last:
                    print('Verify64 ISO hashes', pr * 10, '%', flush=True)
                    last = pr
        hashes = [h.digest() for h in hashes]
        assert len(set(hashes)) == 64
        old = [d for d, _ in P['profiles']]
        assert all(hashes[i] != old[i] for i in range(64)), '모든 조합이 바뀌어야 한다(잉그램 대사는 공통)'
        assert [x.hex().upper() for x in old] == [h.upper() for h in P['public_hashes']]
        # 실제 설치기·xdelta 검증용 기본 조합 시험 ISO (게임용 ISO는 건드리지 않음)
        scratch = ROOT / 'runtime' / 'FIX20261121_VERIFY.iso'
        assert not scratch.exists()
        bf.seek(0)
        with scratch.open('wb') as out:
            while raw := bf.read(16 << 20):
                out.write(raw)
        with scratch.open('r+b') as out:
            for at, b in flatviews[0]:
                out.seek(at)
                out.write(b)
        assert bytes.fromhex(file_hash(scratch)) == hashes[0]
    # 이전 공개 결과(v20261116 64조합)는 별칭으로 인식해 바로 갱신·복원 가능하게 한다.
    aliases = list(P['aliases'])
    aliases.extend((mask, digest, P['anchors'][mask & 31], [(at, a) for at, a, b in rr])
                   for mask, (digest, rr) in enumerate(P['profiles']))
    newpool, ids = [], {}

    def ident(b):
        d = hashlib.sha256(b).digest()
        if d not in ids:
            ids[d] = len(newpool)
            newpool.append(b)
        assert newpool[ids[d]] == b
        return ids[d]
    entries = [[(at, len(a), ident(a), ident(b)) for at, a, b in rr] for rr in plans]
    aliasrows = [(mask, source, anchor, [(at, len(b), ident(b)) for at, b in rr]) for mask, source, anchor, rr in aliases]
    dest = HERE / 'OGS_beowulf_options.bin'
    tmp = dest.with_suffix('.tmp')
    with tmp.open('wb') as out:
        out.write(b'OGSBEO02' + struct.pack('<QII', size, 64, len(newpool)))
        for data in newpool:
            out.write(struct.pack('<I', len(data)) + data)
        for mask, rr in enumerate(entries):
            out.write(struct.pack('<I', mask) + P['anchors'][mask & 31] + hashes[mask] + struct.pack('<I', len(rr)))
            for row in rr:
                out.write(struct.pack('<QIII', *row))
        out.write(struct.pack('<I', len(aliasrows)))
        for mask, source, anchor, rr in aliasrows:
            out.write(struct.pack('<I', mask) + source + anchor + struct.pack('<I', len(rr)))
            for row in rr:
                out.write(struct.pack('<QII', *row))
    tmp.replace(dest)
    prev = json.loads((ROOT / 'runtime' / 'beowulf_options_profiles.json').read_text(encoding='utf-8'))
    assert prev['version'] == PREVIOUS
    report = dict(version=VERSION, bits=prev['bits'], defaults=0, hashes=[h.hex().upper() for h in hashes],
                  anchors=prev['anchors'], profile_count=64, pack_sha256=file_hash(dest), pack_size=dest.stat().st_size,
                  previous_profiles_supported=len(aliases), source_release=PREVIOUS, personal_changes_excluded=True,
                  gameplay_ISO_read_only=True, production_sha256=production, fixes=[f[0] for f in fixes],
                  per_profile=infos, generator_equals_recorded_fix_on_masks=[1, 3, 31], branch_scan_all_profiles=True,
                  live_playthrough_verified_by_user='mask of working ISO (hidden ON, Beowulf OFF) on phone, 2026-11-21',
                  scratch_default_iso=str(scratch))
    assert file_hash(TARGET) == production
    (ROOT / 'runtime' / 'beowulf_options_profiles.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'runtime' / 'fix20261121_profiles.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FIX PACK READY', dest, report['pack_size'], report['pack_sha256'], flush=True)


INTRO = f'''# OGs 액셀 역할 교체 패치 {VERSION} — 트롬베 공존·오우카/워단 합류·잉그램 대사 수정

## 이번 업데이트

- 42화에서 휴케바인 Mk-Ⅲ 트롬베가 타입R로 바뀔 때 트롬베도 그대로 남습니다. 기체·무장 개조 단계는 타입R에 복사되고, 장착 파츠와 파일럿은 원래 기체에 남습니다. 41화 이후 세이브는 타입R을 가진 상태에서 「갈아타기」 메뉴에 들어가면 빠진 트롬베를 돌려받습니다.
- 오우카·워단이 합류할 때 기체와 파일럿이 두 번 생기던 문제를 고쳤습니다. 이미 중복된 세이브는 인터미션에서 쓰지 않은 쪽만 정리합니다. 개조나 파츠가 다른 기체, 육성한 파일럿은 지우지 않습니다.
- 아군으로 합류한 워단의 전투 대사·음성이 원래 대사로 나오도록 연결했습니다.
- 잉그램의 R-GUN 일반 공격 대사(「공격한다！」「떨어져라！」「잡았다！」「부서져！」)가 원래 음성과 함께 나오도록 고쳤습니다.
- 여섯 옵션과 기본값(모두 꺼짐)은 그대로입니다. 위 수정은 옵션과 관계없이 들어갑니다.

## 다운로드

- [ISO 패처 ZIP](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/{VERSION}/SRWOGS_AxelRoleSwap_kr_{VERSION}.zip)
- HD 텍스처 추가팩은 바뀌지 않았습니다. 필요하면 [v20261116 릴리즈](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/tag/v20261116)의 HD ZIP을 쓰세요.

## 적용 방법

1. PCSX2를 종료합니다. 일본판 원본 → [한글패치 v1.4.3s1](https://github.com/z3oo3z/PS2-SRWOGS-KPatch/releases/download/SRWOGS/OGs-v1.4.3s1.7z) → 이 액셀 패치 순서로 적용합니다. 기존 공개 액셀 패치 적용본도 새 패처로 바로 갱신할 수 있습니다.
2. ZIP을 풀고 patcher/OGS_AxelSwap_QuickPatch.exe에서 ISO를 선택해 적용합니다. 쓰던 옵션은 다시 체크해 주세요.
3. 새로 부팅해 게임 내 메모리카드 세이브로 불러옵니다. ISO 갱신 후 예전 세이브 스테이트는 사용하지 마세요.
'''


def run(*args):
    import subprocess
    print('  $', ' '.join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], check=True)


def package():
    import re
    import shutil
    import subprocess
    import time
    W, QP, DIST = ROOT, HERE, ROOT / 'dist'
    XD = ROOT.parent / 'xdelta.exe'
    profiles = json.loads((W / 'runtime' / 'fix20261121_profiles.json').read_text(encoding='utf-8'))
    assert profiles['version'] == VERSION and profiles['pack_sha256'] == file_hash(QP / 'OGS_beowulf_options.bin')
    hashes = profiles['hashes']
    current = file_hash(TARGET)
    revision = W / 'runtime' / 'fix_revision_20261121'
    revision.mkdir(exist_ok=True)
    repo = ROOT.parent / 'ogs-repo'
    # 패처 소스는 버전 문자열만 바꾼다(설치 로직은 공개 v20261116과 동일).
    cs = QP / 'OgsAxelQuickPatch.cs'
    text = cs.read_text(encoding='utf-8')
    text = re.sub(r'private const string VersionText = "[^"]+";', f'private const string VersionText = "{VERSION}";', text)
    cs.write_text(text, encoding='utf-8')
    previous_cs = subprocess.check_output(['git', 'show', 'HEAD:work_ogs/iso_quickpatch/OgsAxelQuickPatch.cs'], cwd=repo).decode('utf-8-sig')
    canonical = lambda s: re.sub(r'private const string VersionText = "[^"]+";', 'VERSION', s).replace('\r\n', '\n').lstrip('\ufeff')
    assert canonical(text) == canonical(previous_cs)
    exe = QP / 'OGS_AxelSwap_QuickPatch.exe'
    run(Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'), '/nologo', '/target:winexe', '/platform:anycpu', '/optimize+',
        '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll', '/out:' + str(exe), cs)
    for arg in ('--self-test-options', '--self-test-beowulf'):
        r = subprocess.run([str(exe), arg], cwd=QP, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0 and 'PASS' in r.stdout + r.stderr, (r.stdout, r.stderr)
        (revision / (arg[2:] + '.log')).write_text(r.stdout + r.stderr, encoding='utf-8')
        print(arg, 'PASS', flush=True)
    # xdelta: 기본 조합(옵션 모두 끔)
    scratch = W / 'runtime' / 'FIX20261121_VERIFY.iso'
    assert file_hash(scratch) == hashes[0]
    delta = DIST / f'SRWOGS_AxelRoleSwap_kr_{VERSION}.xdelta'
    assert not delta.exists()
    run(XD, '-e', '-9', '-f', '-B', '536870912', '-s', SOURCE, scratch, delta)
    scratch.unlink()
    run(XD, '-d', '-s', SOURCE, delta, scratch)
    assert file_hash(scratch) == hashes[0]
    tests = []

    def invoke(flags):
        start = time.time()
        r = subprocess.run([str(exe), str(scratch), '--cli'] + flags, cwd=QP, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0, (r.stdout[-3000:], r.stderr)
        return file_hash(scratch), round(time.time() - start, 2)
    shutil.copyfile(SOURCE, scratch)
    flags63 = ['--hidden', '--bundle', '--rewards', '--enemy', '--spirits', '--beowulf']
    for name, flags, mask in [('base_to_default', [], 0), ('default_to_beowulf', ['--beowulf'], 32), ('all_on', flags63, 63),
                              ('hidden_only', ['--hidden'], 1), ('all_off', [], 0), ('restore', ['--restore'], 1)]:
        digest, seconds = invoke(flags)
        assert digest == hashes[mask], (name, digest, hashes[mask])
        tests.append(dict(name=name, mask=mask, sha256=digest, seconds=seconds))
        print('Installer PASS', name, flush=True)
    # 직전 공개판(v20261116) 적용본 → 새 판 → 복원
    import zipfile
    olddir = revision / 'previous_patcher'
    olddir.mkdir(exist_ok=True)
    with zipfile.ZipFile(DIST / f'SRWOGS_AxelRoleSwap_kr_{PREVIOUS}.zip') as z:
        old = json.loads(z.read('옵션별_ISO_SHA256.json'))['profiles']
        for n in z.namelist():
            if n.startswith('patcher/'):
                (olddir / Path(n).name).write_bytes(z.read(n))
    for mask, flags in ((0, []), (31, flags63[:5]), (63, flags63)):
        if Path(str(scratch) + '.ogsbak').exists():
            Path(str(scratch) + '.ogsbak').unlink()
        shutil.copyfile(SOURCE, scratch)
        r = subprocess.run([str(olddir / exe.name), str(scratch), '--cli'] + flags, cwd=olddir, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0 and file_hash(scratch) == old[mask]['sha256'], (mask, r.stdout[-2000:])
        digest, _ = invoke(flags)
        assert digest == hashes[mask]
        tests.append(dict(name=f'{PREVIOUS}_{mask}_to_new', mask=mask, sha256=digest))
        digest, _ = invoke(['--restore'])
        assert digest == old[mask]['sha256']
        tests.append(dict(name=f'restore_{PREVIOUS}_{mask}', sha256=digest))
        print('Upgrade PASS', mask, flush=True)
    for p in (scratch, Path(str(scratch) + '.ogsbak')):
        if p.exists():
            p.unlink()
    for p in olddir.iterdir():
        p.unlink()
    olddir.rmdir()
    validation = dict(passed=True, version=VERSION, profile_count=64, actual_iso_cases=tests, source_public_release=PREVIOUS,
                      personal_changes_excluded=True)
    (revision / 'release_validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    oldnotes = (W / 'runtime' / 'beowulf_release_notes_20261116.md').read_text(encoding='utf-8')
    notes = INTRO + '\n---\n\n## 이전 누적 변경사항\n\n' + oldnotes.split('\n', 1)[1]
    notespath = W / 'runtime' / f'release_notes_{VERSION}.md'
    notespath.write_text(notes, encoding='utf-8')
    with zipfile.ZipFile(DIST / f'SRWOGS_AxelRoleSwap_kr_{PREVIOUS}.zip') as z:
        payload = {n: z.read(n) for n in z.namelist() if n not in ('SHA256SUMS.txt', f'SRWOGS_AxelRoleSwap_kr_{PREVIOUS}.xdelta')}
    payload['patcher/OGS_beowulf_options.bin'] = (QP / 'OGS_beowulf_options.bin').read_bytes()
    payload['patcher/' + exe.name] = exe.read_bytes()
    payload[delta.name] = delta.read_bytes()
    for k in ('읽어주세요.txt', '변경사항.md', 'patcher/읽어주세요.txt'):
        payload[k] = notes.encode('utf-8-sig')
    payload['옵션별_ISO_SHA256.json'] = json.dumps(dict(version=VERSION, iso_size=4518150144, options=profiles['bits'], defaults=0,
                                                   profiles=[dict(mask=i, sha256=h) for i, h in enumerate(hashes)]), ensure_ascii=False, indent=2).encode('utf-8')
    payload['patcher/SHA256SUMS.txt'] = ''.join(hashlib.sha256(v).hexdigest().upper() + '  ' + Path(k).name + '\n'
                                                for k, v in sorted(payload.items()) if k.startswith('patcher/') and k != 'patcher/SHA256SUMS.txt').encode('utf-8-sig')
    payload['SHA256SUMS.txt'] = ''.join(hashlib.sha256(v).hexdigest().upper() + '  ' + k + '\n' for k, v in sorted(payload.items())).encode('utf-8-sig')
    out = DIST / f'SRWOGS_AxelRoleSwap_kr_{VERSION}.zip'
    assert not out.exists()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n, v in payload.items():
            z.writestr(n, v)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for n, v in payload.items():
            assert z.read(n) == v
    assert file_hash(TARGET) == current
    metadata = dict(version=VERSION, status='PREPARED', previous=PREVIOUS, notes=str(notespath),
                    release_zip=dict(file=out.name, size=out.stat().st_size, sha256=file_hash(out)),
                    patch=dict(file=delta.name, size=delta.stat().st_size, sha256=file_hash(delta)),
                    result_iso=dict(size=4518150144, sha256=hashes[0]), validation=validation, personal_ISO_untouched=True)
    (revision / 'release_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PACKAGE READY', json.dumps(metadata['release_zip'], ensure_ascii=False), flush=True)


def stage_repo():
    import shutil
    W = ROOT
    repo = ROOT.parent / 'ogs-repo'
    revision = W / 'runtime' / 'fix_revision_20261121'
    m = json.loads((revision / 'release_metadata.json').read_text(encoding='utf-8'))
    assert m['version'] == VERSION and m['validation']['passed']
    notes = Path(m['notes']).read_text(encoding='utf-8')
    intro = notes.split('\n---\n', 1)[0].rstrip() + '\n'
    body = intro[intro.index('## 이번 업데이트'):]
    zipurl = f'https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/{VERSION}/SRWOGS_AxelRoleSwap_kr_{VERSION}.zip'
    # README: 현재 버전·다운로드 링크·이번 업데이트 구간·지원 버전 목록
    p = repo / 'README.md'
    t = p.read_text(encoding='utf-8-sig')
    t = t.replace(f'현재 버전: **{PREVIOUS}**', f'현재 버전: **{VERSION}**', 1)
    t = t.replace(f'[패처 ZIP 다운로드](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/{PREVIOUS}/SRWOGS_AxelRoleSwap_kr_{PREVIOUS}.zip) · [릴리즈](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/tag/{PREVIOUS})',
                  f'[패처 ZIP 다운로드]({zipurl}) · [릴리즈](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/tag/{VERSION})', 1)
    assert f'releases/tag/{VERSION}' in t
    s, e = t.index('## 이번 업데이트'), t.index('## 기본 적용 사항')
    t = t[:s] + body.split('## 다운로드')[0].rstrip() + '\n\n' + t[e:]
    t = t.replace('·v20261106 공개 적용본을 지원합니다.', '·v20261106·v20261107·v20261116 공개 적용본을 지원합니다.', 1)
    p.write_text(t, encoding='utf-8')
    # 문서 첫 화면·패치노트·변경 내역
    p = repo / 'docs' / 'home.md'
    p.write_text(intro + '\n## 이전 업데이트\n\n' + p.read_text(encoding='utf-8-sig').replace('# OGs', '### OGs', 1), encoding='utf-8')
    p = repo / 'docs' / 'patch-notes.md'
    p.write_text(intro + '\n---\n\n' + p.read_text(encoding='utf-8-sig'), encoding='utf-8')
    p = repo / 'CHANGELOG.md'
    t = p.read_text(encoding='utf-8-sig')
    assert f'## {VERSION}' not in t
    p.write_text(f'# 변경 내역\n\n## {VERSION} (2026-11-21)\n\n' + intro + '\n' + t.removeprefix('# 변경 내역\n'), encoding='utf-8')
    p = repo / 'docs' / '_sidebar.md'
    t = p.read_text(encoding='utf-8-sig')
    t = t.replace('[⬇️ v20261107 보충 지급 수정판 다운로드]', f'[⬇️ {VERSION} 최신판 다운로드]')
    p.write_text(t, encoding='utf-8')
    (repo / 'work_ogs' / 'iso_quickpatch' / '읽어주세요.txt').write_text(notes, encoding='utf-8-sig')
    for name in ('iso_quickpatch/release_fix_20261121.py', 'iso_quickpatch/OgsAxelQuickPatch.cs', 'fix_ouka_wodan_map_20261121.py', 'build_ingram_rivale.py'):
        shutil.copyfile(W / name, repo / 'work_ogs' / name)
    for src, name in ((revision / 'release_validation.json', 'fix20261121_release_validation.json'),
                      (W / 'runtime' / 'fix20261121_profiles.json', 'fix20261121_profiles.json')):
        shutil.copyfile(src, repo / 'work_ogs' / 'validation' / name)
    shutil.copyfile(W / 'dist' / m['patch']['file'], repo / 'patch' / m['patch']['file'])
    (repo / 'patch' / 'PATCH_INFO.json').write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    print('repo staged', flush=True)


def publish():
    import subprocess
    import urllib.error
    import urllib.parse
    import urllib.request
    W = ROOT
    repo = ROOT.parent / 'ogs-repo'
    revision = W / 'runtime' / 'fix_revision_20261121'
    m = json.loads((revision / 'release_metadata.json').read_text(encoding='utf-8'))
    assert m['validation']['passed']
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip(), 'Commit release files first'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    env = (ROOT.parent / '.env').read_text(encoding='utf-8')
    token = next(l.split('=', 1)[1].strip().strip('"') for l in env.splitlines() if l.startswith('GITHUB_TOKEN='))

    def api(method, url, data=None, kind='application/json'):
        req = urllib.request.Request(url, data=data, method=method, headers={'Authorization': 'Bearer ' + token,
                                     'Accept': 'application/vnd.github+json', 'Content-Type': kind, 'User-Agent': 'OGS-release'})
        with urllib.request.urlopen(req, timeout=900) as f:
            return json.load(f)
    base = 'https://api.github.com/repos/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch'
    body = Path(m['notes']).read_text(encoding='utf-8') + '\n\n## 배포 파일 SHA256\n\n'
    for k in ('release_zip', 'patch'):
        body += '- ' + m[k]['file'] + ': `' + m[k]['sha256'] + '`\n'
    try:
        rel = api('GET', base + '/releases/tags/' + VERSION)
        assert rel['draft'], 'Version already public'
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        rel = api('POST', base + '/releases', json.dumps(dict(tag_name=VERSION, target_commitish=head,
                  name=f'OGs 액셀 패치 {VERSION} — 트롬베 공존·오우카/워단 합류·잉그램 대사 수정', body=body, draft=True,
                  prerelease=False), ensure_ascii=False).encode())
    for k in ('release_zip', 'patch'):
        file = W / 'dist' / m[k]['file']
        expected = file_hash(file).lower()
        assert expected == m[k]['sha256'].lower()
        match = next((a for a in rel.get('assets', []) if a['name'] == file.name), None)
        if match:
            assert match.get('digest', '').lower() == 'sha256:' + expected
        else:
            asset = api('POST', rel['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(file.name), file.read_bytes(), 'application/octet-stream')
            assert asset['size'] == file.stat().st_size and asset.get('digest', '').lower() == 'sha256:' + expected
        print('Uploaded:', file.name, flush=True)
    rel = api('PATCH', rel['url'], json.dumps(dict(draft=False, make_latest='true', body=body), ensure_ascii=False).encode())
    checks = []
    for k in ('release_zip', 'patch'):
        a = next(a for a in rel['assets'] if a['name'] == m[k]['file'])
        with urllib.request.urlopen(a['browser_download_url'], timeout=900) as f:
            h = hashlib.sha256()
            while chunk := f.read(4 << 20):
                h.update(chunk)
        assert h.hexdigest().upper() == m[k]['sha256'].upper()
        checks.append(a['browser_download_url'])
        print('Public download verified:', a['name'], flush=True)
    assert api('GET', base + '/releases/latest')['tag_name'] == VERSION
    result = dict(release=rel['html_url'], tag=VERSION, commit=head, assets=checks, download_verified=True)
    (revision / 'publish.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


def check():
    P = load_previous()
    fixes = fix_edits()
    assert file_hash(SOURCE) == P['sourcehash'].hex().upper()
    report = {}
    with SOURCE.open('rb') as bf:
        for mask in range(64):
            _, v = profile_view(P, bf, mask)
            row = []
            for name, es, _, _ in fixes:
                ok = [v.get(at, len(a)) == a for at, a, b in es]
                already = [v.get(at, len(b)) == b for at, a, b in es]
                row.append((name, sum(ok), sum(already), len(es)))
                if all(ok):
                    for at, a, b in es:
                        v.put(at, b)
            report[mask] = row
            print(mask, ' '.join(f'{n}:{o}/{t}(이미{al})' for n, o, al, t in row), flush=True)
    return report


if __name__ == '__main__':
    if '--check' in sys.argv:
        check()
    elif '--equivalence' in sys.argv:
        check_equivalence()
    elif '--build' in sys.argv:
        build()
    elif '--package' in sys.argv:
        package()
    elif '--stage' in sys.argv:
        stage_repo()
    elif '--publish' in sys.argv:
        publish()
