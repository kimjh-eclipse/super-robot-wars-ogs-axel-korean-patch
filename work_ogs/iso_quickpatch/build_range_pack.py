"""슈퍼로봇대전 OGs 액셀 역할 교체 — 제자리 ISO 구간 패치 리소스 생성.

D2DHD_kr/iso_quickpatch/build_range_pack.py 와 같은 방식.
기준 ISO(srwogs-v1.4.3s1)와 CURRENT ISO 크기가 완전히 동일하므로
(4,518,150,144B) 절대 오프셋 구간만 담으면 된다.

MERGE_GAP 이내로 떨어진 변경은 하나로 합쳐 런타임 복사 횟수를 줄인다.
"""
from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

import numpy as np

MAGIC = b"OGSAXLRNG"
VERSION = 1
MERGE_GAP = 64
CHUNK = 16 * 1024 * 1024

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = HERE / "OGS_ISO_ranges.bin"

SOURCE = ROOT / "baseline" / "srwogs-v1.4.3s1.iso"
TARGET = ROOT / "build" / "SRWOGS_K.iso"
TITLE = "슈퍼로봇대전 OGs 액셀 역할 교체 패치"


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb", buffering=0) as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest().upper()


def find_ranges(source: Path, target: Path):
    if source.stat().st_size != target.stat().st_size:
        raise ValueError(f"크기 불일치: {source.stat().st_size} / {target.stat().st_size}")
    size = source.stat().st_size
    parts = []
    off = 0
    with source.open("rb", buffering=0) as a, target.open("rb", buffering=0) as b:
        while off < size:
            old = a.read(min(CHUNK, size - off))
            new = b.read(len(old))
            d = np.flatnonzero(
                np.frombuffer(old, dtype=np.uint8) != np.frombuffer(new, dtype=np.uint8)
            )
            if d.size:
                parts.append(d.astype(np.int64) + off)
            off += len(old)
    if not parts:
        return []
    pos = np.concatenate(parts)
    cuts = np.flatnonzero(np.diff(pos) > MERGE_GAP + 1)
    starts = np.r_[0, cuts + 1]
    ends = np.r_[cuts, len(pos) - 1]
    return [(int(pos[s]), int(pos[e] - pos[s] + 1)) for s, e in zip(starts, ends)]


def main() -> None:
    src_hash = file_hash(SOURCE)
    dst_hash = file_hash(TARGET)
    print(f"기준본 {SOURCE.name}\n      {SOURCE.stat().st_size:,}B  {src_hash}")
    print(f"패치본 {TARGET.name}\n      {TARGET.stat().st_size:,}B  {dst_hash}")

    expected_src = "9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C"
    if src_hash != expected_src:
        raise ValueError("기준 ISO 해시가 기준본과 다릅니다")
    # CURRENT ISO 해시는 버전마다 바뀌므로 강제하지 않는다. 출력에 기록된
    # dst 해시를 릴리즈 문서와 대조하는 것으로 검증한다.

    ranges = find_ranges(SOURCE, TARGET)
    payload = sum(n for _, n in ranges)
    print(f"\n변경 구간 {len(ranges):,}개 / 페이로드 {payload:,}B "
          f"({100*payload/SOURCE.stat().st_size:.2f}%)")

    tmp = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    title = TITLE.encode("utf-8")
    with tmp.open("wb", buffering=1 << 20) as out:
        out.write(MAGIC)
        out.write(struct.pack("<I", VERSION))
        out.write(struct.pack("<H", len(title)))
        out.write(title)
        out.write(struct.pack("<Q", SOURCE.stat().st_size))
        out.write(bytes.fromhex(src_hash))
        out.write(bytes.fromhex(dst_hash))
        out.write(struct.pack("<I", len(ranges)))
        with TARGET.open("rb", buffering=0) as t:
            for off, n in ranges:
                t.seek(off)
                data = t.read(n)
                if len(data) != n:
                    raise IOError(f"짧은 읽기 @{off}")
                out.write(struct.pack("<QI", off, n))
                out.write(data)
        out.flush()
        os.fsync(out.fileno())
    tmp.replace(OUTPUT)
    print(f"\n생성: {OUTPUT.name}  {OUTPUT.stat().st_size:,}B")
    print(f"SHA256 {file_hash(OUTPUT)}")



def build_options(common_fix=False):
    """Build independent optional deltas, hash every one of the 32 profiles.

    Existing v20261026 base and upgrade range packs are preserved byte-for-byte.
    The current gameplay ISO is read-only throughout this build.
    """
    import json,concurrent.futures
    current_hash=file_hash(TARGET)
    assert current_hash==('8DE813EC3C5C75E65DD1E2B1C3B4D358B141457F1CA10754365CC0AB7634F24C' if common_fix else 'AA4AAA2FA4AB136EBA8904E7270C6623A3B0B22147C0BD96BE5630C33CC0DC77'),current_hash
    meta=json.loads((ROOT/'runtime/release_build_metadata.json').read_text(encoding='utf-8'))
    def option(name):
        with (HERE/name).open('rb') as f:
            assert f.read(8)==b'OGSHID01'
            size=struct.unpack('<Q',f.read(8))[0];src=f.read(32).hex().upper();dst=f.read(32).hex().upper()
            es=[]
            for _ in range(struct.unpack('<I',f.read(4))[0]):
                at,n=struct.unpack('<QI',f.read(12));a,b=f.read(n),f.read(n)
                assert len(a)==len(b)==n;es.append((at,a,b))
            assert not f.read(1) and size==TARGET.stat().st_size
        return src,dst,es
    hidden=option('OGS_hidden_rewards.bin');bundle=option('OGS_ouka_zengar.bin');both=option('OGS_ouka_zengar_hidden.bin')
    expected=[meta[k].upper() for k in ('default_sha256','hidden_sha256','bundle_sha256','both_sha256')]
    assert (hidden[0],hidden[1],bundle[0],bundle[1],both[0],both[1])==(expected[0],expected[1],expected[0],expected[2],expected[1],expected[3])
    def journal(name):
        m=json.loads((ROOT/'runtime'/name).read_text(encoding='utf-8'));assert m['applied']
        return [(e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits']]
    axel=journal('axel_spirits_manifest.json');seolla=journal('seolla_spirits_manifest.json')
    features={4:journal('battle_rewards_manifest.json'),8:journal('enemy_strength_manifest.json'),16:sorted(axel+seolla)}
    spans=[]
    for bit,es in features.items():
        for at,a,b in es:
            assert len(a)==len(b)>0
            for start,end in spans:assert at+len(a)<=start or at>=end,'New features overlap'
            spans.append((at,at+len(a)))
    # Gather a sparse byte map from the current all-on ISO to each requested
    # profile. Base-off bytes are recovered through guarded reverse deltas.
    off={}
    with TARGET.open('rb') as f:
        def set_edit(at,a,b):
            f.seek(at);cur=f.read(len(a))
            actual=bytes(off.get(at+j,cur[j]) for j in range(len(a)))
            assert actual==a,(hex(at),actual.hex(),a.hex())
            off.update((at+j,v) for j,v in enumerate(b))
        for es in features.values():
            for at,a,b in es:set_edit(at,b,a)
        for at,a,b in both[2]:set_edit(at,b,a)
        for at,a,b in hidden[2]:set_edit(at,b,a)
    overlays=[]
    for mask in range(32):
        profile=dict(off)
        sets=[]
        if mask&1:sets.append(hidden[2])
        if mask&2:sets.append(both[2] if mask&1 else bundle[2])
        for bit,es in features.items():
            if mask&bit:sets.append(es)
        for es in sets:
            for at,a,b in es:
                assert bytes(profile[at+j] for j in range(len(a)))==a,(mask,hex(at))
                profile.update((at+j,v) for j,v in enumerate(b))
        # Merge adjacent sparse bytes into small contiguous writes.
        merged=[]
        for at in sorted(profile):
            if merged and at==merged[-1][0]+len(merged[-1][1]):merged[-1][1].append(profile[at])
            else:merged.append([at,bytearray([profile[at]])])
        overlays.append([(at,bytes(b)) for at,b in merged])
    hs=[hashlib.sha256() for _ in range(32)];chunk_size=16<<20;done=0;last=-1
    def update(arg):
        h,es,raw,off_chunk=arg
        touched=[(a,b) for a,b in es if a<off_chunk+len(raw) and a+len(b)>off_chunk]
        if not touched:h.update(raw);return
        buf=bytearray(raw)
        for a,b in touched:
            left=max(a,off_chunk);right=min(a+len(b),off_chunk+len(raw))
            buf[left-off_chunk:right-off_chunk]=b[left-a:right-a]
        h.update(buf)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool,TARGET.open('rb') as f:
        while raw:=f.read(chunk_size):
            list(pool.map(update,[(hs[i],overlays[i],raw,done) for i in range(32)]));done+=len(raw)
            progress=int(done*100/TARGET.stat().st_size)//10
            if progress!=last:print('32 option hashes: %d%%'%(progress*10),flush=True);last=progress
    hashes=[h.hexdigest().upper() for h in hs]
    if not common_fix:assert hashes[:4]==expected,(hashes[:4],expected)
    assert hashes[31]==current_hash and len(set(hashes))==32
    def write_edits(f,es):
        f.write(struct.pack('<I',len(es)))
        for at,a,b in sorted(es):f.write(struct.pack('<QI',at,len(a)));f.write(a);f.write(b)
    if common_fix:
        previous=json.loads((ROOT/'runtime/optional_features_profiles.json').read_text(encoding='utf-8'))
        m=json.loads((ROOT/'runtime/mumei_fallback_manifest.json').read_text(encoding='utf-8'))
        assert m['applied'] and m['target_sha256'].upper()==current_hash
        assert m['source_sha256'].upper()==previous['hashes'][31]
        fixes=journal('mumei_fallback_manifest.json')
        with TARGET.open('rb') as f:
            for at,a,b in fixes:
                f.seek(at);assert f.read(len(b))==b
        dest=HERE/'OGS_common_fix.bin';tmp=dest.with_suffix('.tmp')
        with tmp.open('wb') as f:
            f.write(b'OGSFIX01');f.write(struct.pack('<Q',TARGET.stat().st_size));f.write(struct.pack('<I',32))
            for mask in range(32):
                f.write(struct.pack('<I',mask));f.write(bytes.fromhex(previous['hashes'][mask]));f.write(bytes.fromhex(hashes[mask]))
            write_edits(f,fixes);f.flush();os.fsync(f.fileno())
        tmp.replace(dest)
        report=dict(previous,version='v20261027.1',iso_unchanged_sha256=current_hash,hashes=hashes,
            previous_hashes=previous['hashes'],common_file_sha256=file_hash(dest))
        (ROOT/'runtime/common_fix_profiles.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Built common fix; 32 new hashes verified',flush=True)
        return
    dest=HERE/'OGS_optional_features.bin';tmp=dest.with_suffix('.tmp')
    with tmp.open('wb') as f:
        f.write(b'OGSOPT02');f.write(struct.pack('<Q',TARGET.stat().st_size));f.write(bytes.fromhex(expected[0]))
        f.write(struct.pack('<I',32))
        for mask,h in enumerate(hashes):f.write(struct.pack('<I',mask));f.write(bytes.fromhex(h))
        f.write(struct.pack('<I',3))
        for bit,es in features.items():f.write(struct.pack('<I',bit));write_edits(f,es)
        # Support the intermediate local ISO with only Axel spirits applied.
        f.write(struct.pack('<I',1))
        m=json.loads((ROOT/'runtime/axel_spirits_manifest.json').read_text(encoding='utf-8'))
        f.write(bytes.fromhex(m['target_sha256']));f.write(struct.pack('<I',3));write_edits(f,axel)
        f.flush();os.fsync(f.fileno())
    tmp.replace(dest)
    report=dict(version='v20261027',iso_unchanged_sha256=current_hash,
        bits={'hidden':1,'bundle':2,'rewards':4,'enemy':8,'spirits':16},
        defaults=0,hashes=hashes,features_file_sha256=file_hash(dest),profile_count=32)
    (ROOT/'runtime/optional_features_profiles.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Built '+str(dest)+'; all 32 profile hashes verified',flush=True)


def build_story_common():
    """Rebase common story additions on all four old script option profiles."""
    import sys,json,shutil,concurrent.futures
    sys.path.insert(0,str(ROOT))
    from build_hidden_rewards import wodan_survival_plan,grungust_type3_grant_plan
    from validate_hidden_rewards import validate_wodan_survival,validate_grungust_type3_grant
    current=file_hash(TARGET)
    assert current=='25CA7578DE0A2B8647B08AEB64992D404D7D304D02285BA4EDF2A87919013056'
    core=json.loads((ROOT/'runtime/optional_features_profiles.json').read_text(encoding='utf-8'))
    prior=json.loads((ROOT/'release_v20261027.1/옵션별_ISO_SHA256.json').read_text(encoding='utf-8'))
    def journal(name):
        m=json.loads((ROOT/'runtime'/name).read_text(encoding='utf-8'));assert m['applied']
        return [(e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits']]
    def option(name):
        with (HERE/name).open('rb') as f:
            assert f.read(8)==b'OGSHID01';f.read(8+64);es=[]
            for _ in range(struct.unpack('<I',f.read(4))[0]):
                at,n=struct.unpack('<QI',f.read(12));es.append((at,f.read(n),f.read(n)))
            assert not f.read(1)
        return es
    hidden=option('OGS_hidden_rewards.bin');bundle=option('OGS_ouka_zengar.bin');both=option('OGS_ouka_zengar_hidden.bin')
    features={4:journal('battle_rewards_manifest.json'),8:journal('enemy_strength_manifest.json'),16:sorted(journal('axel_spirits_manifest.json')+journal('seolla_spirits_manifest.json'))}
    mumei=journal('mumei_fallback_manifest.json');tmp=HERE/'STORY_BUILD.iso'
    assert not tmp.exists(),'Inspect existing story build ISO first'
    def apply(es,reverse=False):
        with tmp.open('r+b') as f:
            for at,a,b in reversed(es) if reverse else es:
                if reverse:a,b=b,a
                f.seek(at);assert f.read(len(a))==a,hex(at);f.seek(at);f.write(b)
    plans={};native=[];low_hashes=[]
    try:
        shutil.copyfile(TARGET,tmp)
        for name in ['grungust_type3_grant_manifest.json','wodan_survival_manifest.json','mumei_fallback_manifest.json','enemy_strength_manifest.json','battle_rewards_manifest.json','seolla_spirits_manifest.json','axel_spirits_manifest.json']:
            apply(journal(name),True)
        assert file_hash(tmp)==core['hashes'][3]
        apply(both,True);apply(hidden,True);assert file_hash(tmp)==core['hashes'][0]
        for low in range(4):
            sets=([hidden] if low&1 else [])+([both if low&1 else bundle] if low&2 else [])
            for es in sets:apply(es)
            assert file_hash(tmp)==core['hashes'][low]
            war,row,blobs,dialogue=wodan_survival_plan(tmp)
            war_checks=validate_wodan_survival(war,row,blobs,source=tmp)
            apply(war)
            tri=grungust_type3_grant_plan(tmp);tri_checks=validate_grungust_type3_grant(tri,source=tmp);apply(tri);apply(mumei)
            combined=sorted(war+tri+mumei)
            for x,y in zip(combined,combined[1:]):assert x[0]+len(x[1])<=y[0]
            plans[low]=combined;low_hashes.append(file_hash(tmp))
            native.append(dict(profile=low,wodan=war_checks,type3=tri_checks))
            apply(combined,True)
            for es in reversed(sets):apply(es,True)
            assert file_hash(tmp)==core['hashes'][0]
            print('PASS native story option profile '+str(low),flush=True)
        # Stream the all-OFF core once, applying each complete profile overlay
        # independently. New common blocks never overlap the three stat options.
        sequences=[]
        for mask in range(32):
            low=mask&3;seq=[]
            if low&1:seq+=hidden
            if low&2:seq+=both if low&1 else bundle
            for bit,es in features.items():
                if mask&bit:seq+=es
            for at,a,b in plans[low]:
                assert all(at+len(a)<=x or at>=x+len(y) for es in features.values() for x,y,z in es),'Stat/common overlap'
            seq+=plans[low];sequences.append([(at,b) for at,a,b in seq])
        hs=[hashlib.sha256() for _ in range(32)];done=0;last=-1
        def update(arg):
            h,seq,raw,off=arg;touched=[(a,b) for a,b in seq if a<off+len(raw) and a+len(b)>off]
            if not touched:h.update(raw);return
            out=bytearray(raw)
            for at,b in touched:
                left=max(at,off);right=min(at+len(b),off+len(raw));out[left-off:right-off]=b[left-at:right-at]
            h.update(out)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool,tmp.open('rb') as f:
            while raw:=f.read(16<<20):
                list(pool.map(update,[(hs[i],sequences[i],raw,done) for i in range(32)]));done+=len(raw)
                tick=int(done*100/TARGET.stat().st_size)//10
                if tick!=last:print('32 story hashes: '+str(tick*10)+'%',flush=True);last=tick
        hashes=[h.hexdigest().upper() for h in hs]
        assert hashes[:4]==low_hashes and hashes[31]==current and len(set(hashes))==32
        def write_edits(f,es):
            f.write(struct.pack('<I',len(es)))
            for at,a,b in es:f.write(struct.pack('<QI',at,len(a)));f.write(a);f.write(b)
        dest=HERE/'OGS_common_fix.bin';stage=dest.with_suffix('.tmp')
        with stage.open('wb') as f:
            f.write(b'OGSFIX02');f.write(struct.pack('<QI',TARGET.stat().st_size,32))
            for mask in range(32):
                f.write(struct.pack('<I',mask));f.write(bytes.fromhex(core['hashes'][mask]));f.write(bytes.fromhex(hashes[mask]));write_edits(f,plans[mask&3])
            for h in prior['hashes']:f.write(bytes.fromhex(h))
            write_edits(f,mumei);f.flush();os.fsync(f.fileno())
        stage.replace(dest)
        report=dict(core,version='v20261028',iso_unchanged_sha256=current,hashes=hashes,
            previous_hashes=core['hashes'],prior_release_hashes=prior['hashes'],common_file_sha256=file_hash(dest))
        (ROOT/'runtime/common_fix_profiles.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (ROOT/'runtime/story_common_edits.json').write_text(json.dumps({str(k):[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in v] for k,v in plans.items()},indent=2),encoding='utf-8')
        (ROOT/'runtime/story_native_profiles.json').write_text(json.dumps(native,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Four native profiles and 32 full story ISO hashes verified',flush=True)
    finally:tmp.unlink(missing_ok=True)


def build_maintenance_common():
    """v20261029.1 common/optional fixes, preserving all 32 legacy option profiles."""
    import sys,json,shutil,concurrent.futures
    sys.path.insert(0,str(ROOT))
    from build_hidden_rewards import relocate_ally_sladegelmir_master
    current=file_hash(TARGET)
    assert current=='98ECEB49E5928194A88F7621C91CDDBFA4AC8D48267BA82A43C07081EB23C510'
    oldmeta=json.loads((ROOT/'runtime/common_fix_profiles.json').read_text(encoding='utf-8'))
    assert oldmeta['version']=='v20261029','Do not overwrite already rebuilt metadata'
    core=json.loads((ROOT/'runtime/optional_features_profiles.json').read_text(encoding='utf-8'))
    oldplans=json.loads((ROOT/'runtime/story_common_edits.json').read_text(encoding='utf-8'))
    def unpack(es):return [(e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in es]
    def journal(name):
        m=json.loads((ROOT/'runtime'/name).read_text(encoding='utf-8'));assert m['applied'];return unpack(m['edits'])
    def option(name):
        with (HERE/name).open('rb') as f:
            assert f.read(8)==b'OGSHID01';f.read(8+64);out=[]
            for _ in range(struct.unpack('<I',f.read(4))[0]):
                at,n=struct.unpack('<QI',f.read(12));out.append((at,f.read(n),f.read(n)))
            assert not f.read(1)
        return out
    hidden=option('OGS_hidden_rewards.bin');bundle=option('OGS_ouka_zengar.bin');both=option('OGS_ouka_zengar_hidden.bin')
    features={4:journal('battle_rewards_manifest.json'),8:journal('enemy_strength_manifest.json'),16:sorted(journal('axel_spirits_manifest.json')+journal('seolla_spirits_manifest.json'))}
    tmp=HERE/'STORY_BUILD.iso';assert not tmp.exists()
    def disk_apply(es,reverse=False):
        with tmp.open('r+b') as f:
            for at,a,b in reversed(es) if reverse else es:
                if reverse:a,b=b,a
                f.seek(at);assert f.read(len(a))==a,hex(at);f.seek(at);f.write(b)
    oldwar={i:unpack(oldplans[str(i)]) for i in range(32)}
    legacy28=oldplans['legacy_v20261028']
    class View:
        def __init__(self,f,es=()):self.f=f;self.edits=list(es)
        def read(self,at,n):
            self.f.seek(at);data=bytearray(self.f.read(n));assert len(data)==n
            for p,a,b in self.edits:
                lo=max(at,p);hi=min(at+n,p+len(b))
                if lo<hi:data[lo-at:hi-at]=b[lo-p:hi-p]
            return bytes(data)
        def apply(self,es):
            for at,a,b in es:
                assert self.read(at,len(a))==a,hex(at);self.edits.append((at,a,b))
    try:
        shutil.copyfile(TARGET,tmp)
        disk_apply(journal('sladegelmir_ally_balance_manifest.json'),True)
        assert file_hash(tmp)==oldmeta['hashes'][31]
        disk_apply(oldwar[31],True)
        for es in features.values():disk_apply(es,True)
        disk_apply(both,True);disk_apply(hidden,True)
        assert file_hash(tmp)==core['hashes'][0]
        plans={};views=[];checks=[]
        with tmp.open('rb') as f:
            for mask in range(32):
                low=mask&3;v=View(f)
                if low&1:v.apply(hidden)
                if low&2:v.apply(both if low&1 else bundle)
                for bit,es in features.items():
                    if mask&bit:v.apply(es)
                start=View(f,v.edits)
                v.apply(oldwar[mask])
                for base in (0x5DA000,0x83F000):
                    master=v.read(base,0x1A5800);new=relocate_ally_sladegelmir_master(master)
                    v.apply([(base+0x11E000,master[0x11E000:len(new)],new[0x11E000:])])
                # Merge overlapping writes into guarded core-profile -> final-profile spans.
                spans=[]
                for at,a,b in sorted(v.edits[len(start.edits):]):
                    end=at+len(b)
                    if spans and at<=spans[-1][1]+64:spans[-1][1]=max(spans[-1][1],end)
                    else:spans.append([at,end])
                es=[(a,start.read(a,b-a),v.read(a,b-a)) for a,b in spans]
                es=[e for e in es if e[1]!=e[2]];plans[mask]=es
                # Use only final, non-overlapping overlays for streamed hashing.
                allspans=[]
                for at,a,b in sorted(v.edits):
                    end=at+len(b)
                    if allspans and at<=allspans[-1][1]+64:allspans[-1][1]=max(allspans[-1][1],end)
                    else:allspans.append([at,end])
                views.append([(a,v.read(a,b-a)) for a,b in allspans])
                checks.append(dict(mask=mask,enemy_HP_enabled=bool(mask&8),Ouka_route_fix_enabled=bool(mask&2),master_relocation_preserves_option_bytes=True,Beowulf_excluded=True))
            hashes=[hashlib.sha256() for _ in range(32)];pos=0;last=-1
            def update(args):
                h,es,raw,off=args;out=None
                for at,b in es:
                    lo=max(at,off);hi=min(at+len(b),off+len(raw))
                    if lo<hi:
                        if out is None:out=bytearray(raw)
                        out[lo-off:hi-off]=b[lo-at:hi-at]
                h.update(raw if out is None else out)
            f.seek(0)
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                while raw:=f.read(16<<20):
                    list(pool.map(update,[(hashes[i],views[i],raw,pos) for i in range(32)]));pos+=len(raw)
                    tick=int(pos*100/TARGET.stat().st_size)//10
                    if tick!=last:print('Maintenance 32 hashes:',tick*10,'%',flush=True);last=tick
        hashes=[h.hexdigest().upper() for h in hashes]
        assert hashes[31]==current and len(set(hashes))==32
        def write_edits(f,es):
            f.write(struct.pack('<I',len(es)))
            for at,a,b in es:f.write(struct.pack('<QI',at,len(a)));f.write(a);f.write(b)
        dest=HERE/'OGS_common_fix.bin';stage=dest.with_suffix('.tmp')
        with stage.open('wb') as f:
            f.write(b'OGSFIX02');f.write(struct.pack('<QI',TARGET.stat().st_size,32))
            for mask in range(32):
                f.write(struct.pack('<I',mask));f.write(bytes.fromhex(core['hashes'][mask]));f.write(bytes.fromhex(hashes[mask]));write_edits(f,plans[mask])
            for h in oldmeta['prior_release_hashes']:f.write(bytes.fromhex(h))
            write_edits(f,journal('mumei_fallback_manifest.json'))
            # Backward-compatible extension: previous public release profiles -> core.
            f.write(struct.pack('<I',64))
            for mask in range(32):
                f.write(struct.pack('<I',mask));f.write(bytes.fromhex(oldmeta['legacy_v20261028_hashes'][mask]));write_edits(f,unpack(legacy28[str(mask&3)]))
            for mask in range(32):
                f.write(struct.pack('<I',mask));f.write(bytes.fromhex(oldmeta['hashes'][mask]));write_edits(f,oldwar[mask])
            f.flush();os.fsync(f.fileno())
        stage.replace(dest)
        report=dict(core,version='v20261029.1',iso_unchanged_sha256=current,hashes=hashes,
            previous_hashes=core['hashes'],prior_release_hashes=oldmeta['prior_release_hashes'],legacy_v20261028_hashes=oldmeta['legacy_v20261028_hashes'],legacy_v20261029_hashes=oldmeta['hashes'],
            common_file_sha256=file_hash(dest),profile_checks=checks)
        (ROOT/'runtime/common_fix_profiles.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        data={str(k):[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in es] for k,es in plans.items()}
        data['legacy_v20261028']=legacy28
        data['legacy_v20261029']={str(i):oldplans[str(i)] for i in range(32)}
        (ROOT/'runtime/story_common_edits.json').write_text(json.dumps(data),encoding='utf-8')
        print('Maintenance common pack ready; all 32 hashes, current all-ON equality verified',flush=True)
    finally:tmp.unlink(missing_ok=True)


def build_beowulf_extension():
    """64 profiles layered on the unchanged five-option/legacy patch format."""
    import sys,json,concurrent.futures
    sys.path.insert(0,str(ROOT))
    from build_hidden_rewards import Scripts,MAP
    from build_beowulf_prototype import release_beowulf_master,beowulf_story_scenes,rebuild_beowulf_story_logo
    from validate_beowulf_prototype import validate_story_blob
    U=lambda b,p:struct.unpack_from('<I',b,p)[0]
    def readranges(f):
        rows=[]
        for _ in range(struct.unpack('<I',f.read(4))[0]):
            at,n=struct.unpack('<QI',f.read(12));a,b=f.read(n),f.read(n)
            assert len(a)==len(b)==n;rows.append((at,a,b))
        return rows
    def option(name):
        with (HERE/name).open('rb') as f:
            assert f.read(8)==b'OGSHID01';f.read(72);return readranges(f)
    hidden=option('OGS_hidden_rewards.bin');bundle=option('OGS_ouka_zengar.bin');both=option('OGS_ouka_zengar_hidden.bin')
    features={}
    with (HERE/'OGS_optional_features.bin').open('rb') as f:
        assert f.read(8)==b'OGSOPT02';f.read(40);assert U(f.read(4),0)==32;f.read(36*32)
        assert U(f.read(4),0)==3
        for _ in range(3):
            bit=U(f.read(4),0);features[bit]=readranges(f)
    anchors=[];common={}
    with (HERE/'OGS_common_fix.bin').open('rb') as f:
        assert f.read(8)==b'OGSFIX02';iso_size,count=struct.unpack('<QI',f.read(12));assert count==32
        for mask in range(32):
            assert U(f.read(4),0)==mask;f.read(32);anchors.append(f.read(32).hex().upper());common[mask]=readranges(f)
    class View:
        def __init__(self,f,es=()):
            self.f=f;self.es=[];self.bins={}
            for at,data in es:self.put(at,data)
        def read(self,at,n):
            self.f.seek(at);b=bytearray(self.f.read(n));assert len(b)==n
            indexes=set()
            for block in range(at>>16,((at+n-1)>>16)+1):indexes.update(self.bins.get(block,()))
            for index in sorted(indexes):
                p,data=self.es[index]
                lo=max(at,p);hi=min(at+n,p+len(data))
                if lo<hi:b[lo-at:hi-at]=data[lo-p:hi-p]
            return bytes(b)
        def put(self,at,data):
            data=bytes(data);index=len(self.es);self.es.append((at,data))
            for block in range(at>>16,((at+len(data)-1)>>16)+1):self.bins.setdefault(block,[]).append(index)
        def apply(self,rows,reverse=False):
            for at,a,b in reversed(rows) if reverse else rows:
                if reverse:a,b=b,a
                assert self.read(at,len(a))==a,('byte guard',hex(at));self.put(at,b)
        def clone(self):return View(self.f,self.es)
    def spans(es):
        out=[]
        for at,data in sorted(es):
            end=at+len(data)
            if out and at<=out[-1][1]+64:out[-1][1]=max(out[-1][1],end)
            else:out.append([at,end])
        return out
    def differences(before,after,regions):
        out=[]
        for a,b in regions:
            x=before.read(a,b-a);y=after.read(a,b-a)
            pos=np.flatnonzero(np.frombuffer(x,np.uint8)!=np.frombuffer(y,np.uint8))
            if not len(pos):continue
            cuts=np.flatnonzero(np.diff(pos)>65);starts=np.r_[0,cuts+1];ends=np.r_[cuts,len(pos)-1]
            for i,j in zip(starts,ends):
                lo,hi=int(pos[i]),int(pos[j])+1;out.append((a+lo,x[lo:hi],y[lo:hi]))
        return out
    current_hash=file_hash(TARGET);test=ROOT/'build/SRWOGS_BEOWULF_TEST.iso'
    scripts=Scripts(TARGET);test_scripts=Scripts(test)
    # Read actual tested graphics/animation/code additions, not its stale masters.
    excluded=[(0x5da000,0x5da000+0x1a5800),(0x83f000,0x83f000+0x1a5800),(MAP,MAP+0x9600000)]
    assetranges=[]
    for a,n in find_ranges(TARGET,test):
        parts=[(a,a+n)]
        for lo,hi in excluded:
            parts=[q for x,y in parts for q in ((x,min(y,lo)),(max(x,hi),y)) if q[0]<q[1]]
        assetranges.extend(parts)
    spawn=json.loads((ROOT/'runtime/beowulf/enemy_spawn_plan.json').read_text())
    scene_def=beowulf_story_scenes();master_test={}
    ram_fixture=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes()
    with test.open('rb') as tf:
        for base in (0x5da000,0x83f000):tf.seek(base);master_test[base]=tf.read(0x1a5800)
        assets=[]
        for a,b in assetranges:tf.seek(a);assets.append((a,tf.read(b-a)))
    proof=[];profiles=[];oldviews=[];pairplans=[];validation_cache={}
    with TARGET.open('rb') as f:
        current=View(f);old=current.clone()
        corr=json.loads((ROOT/'runtime/shadowmirror_dialogue_correction.json').read_text(encoding='utf-8'))
        rows=next(x['edits'] for x in corr['plans'] if Path(x['path']).name=='SRWOGS_K.iso')
        for e in rows:old.apply([(e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after']))],True)
        rate=json.loads((ROOT/'runtime/lucky_probability_manifest.json').read_text())
        e=next(x for x in rate['files'] if Path(x['path']).name=='SRWOGS_K.iso')
        old.apply([(e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after']))],True)
        for base in (0x5da000,0x83f000):
            b=bytearray(old.read(base,0x1a5800));h=0x11e800;pl=h+U(b,h+0x2c)+12;lv=h+U(b,h+0x44)+12
            for idx in (60,170,368):struct.pack_into('<H',b,pl+idx*148+0x1a,3)
            b[lv+119*9:lv+120*9]=bytes([1,8,20,29,38,42,0,0,0]);old.put(base,b)
        recent=differences(old,current,spans(old.es));core=old.clone();core.apply(common[31],True)
        for rows in features.values():core.apply(rows,True)
        core.apply(both,True);core.apply(hidden,True)
        for mask in range(32):
            v=core.clone()
            if mask&1:v.apply(hidden)
            if mask&2:v.apply(both if mask&1 else bundle)
            for bit,rows in features.items():
                if mask&bit:v.apply(rows)
            v.apply(common[mask]);oldviews.append(v.clone());v.apply(recent)
            off=v.clone();on=v.clone()
            for a,data in assets:on.put(a,data)
            for base in master_test:on.put(base,release_beowulf_master(on.read(base,0x1a5800),master_test[base]))
            # Rebuild each UNTD from this profile's current rows; omit episode6.
            cursor=0x8dde000;wp=0x5071000
            for table in sorted({x['table'] for x in spawn}):
                assert table!=78
                dp=wp+8+table*8;at=wp+U(scripts.data,dp);n=U(scripts.data,dp+4)
                raw=on.read(MAP+at,n);cnt=U(raw,40);assert len(raw)==44+cnt*336
                tp=wp+U(test_scripts.data,dp);tn=U(test_scripts.data,dp+4);tested=test_scripts.data[tp:tp+tn]
                added=[tested[44+i*336:44+(i+1)*336] for i in range(U(tested,40)) if U(tested,44+i*336)==0x604]
                assert len(added)==len([x for x in spawn if x['table']==table])
                new=bytearray(raw+b''.join(added));struct.pack_into('<I',new,40,cnt+len(added))
                cursor=(cursor+2047)//2048*2048;assert not any(on.read(MAP+cursor,len(new)))
                on.put(MAP+cursor,new);on.put(MAP+dp,struct.pack('<II',cursor-wp,len(new)));cursor+=len(new)
            on.put(MAP+0x800+8+13*8+4,struct.pack('<I',cursor-0x5070000))
            # New dialogue is rebuilt over each option's own scripts, not copied.
            cursor=0x8f00000
            for n,scenes in sorted(scene_def.items()):
                at,size=scripts.logos[n];raw=on.read(MAP+at,size)
                new,notes=rebuild_beowulf_story_logo(raw,scenes)
                fingerprint=hashlib.sha256(raw+new).digest()
                if fingerprint not in validation_cache:
                    validation_cache[fingerprint]=validate_story_blob(raw,new,notes,ram_fixture)
                validation=validation_cache[fingerprint]
                cursor=(cursor+2047)//2048*2048;assert not any(on.read(MAP+cursor,len(new)))
                on.put(MAP+cursor,new);on.put(MAP+0x557f800+8+n*8,struct.pack('<II',cursor-0x557f800,len(new)));cursor+=len(new)
                if mask==0:proof.append(dict(script=n,validation=validation))
            on.put(MAP+0x800+8+14*8+4,struct.pack('<I',cursor-0x557e800))
            # Test spawn is absent in either profile, including direct table data.
            dp=wp+8+78*8;at=wp+U(scripts.data,dp);raw=on.read(MAP+at,U(scripts.data,dp+4))
            assert not any(U(raw,44+i*336)==0x604 for i in range(U(raw,40)))
            for profile in (off,on):
                pairs=differences(oldviews[mask],profile,spans(profile.es+oldviews[mask].es))
                pairplans.append((mask,profile,pairs))
            print('Prepared Beowulf profiles',mask*2+2,'/64',flush=True)
        # Reorder to low 5 option bits plus Beowulf bit32.
        ordered=[None]*64
        for i,(mask,v,es) in enumerate(pairplans):ordered[mask+(32 if i%2 else 0)]=(v,es)
        allviews=oldviews+[v for v,es in ordered]
        overlays=[[(a,v.read(a,b-a)) for a,b in spans(v.es)] for v in allviews]
        hashes=[hashlib.sha256() for _ in allviews];pos=0;last=-1
        def update(args):
            h,es,raw,offset=args;out=None
            for at,data in es:
                lo=max(at,offset);hi=min(at+len(data),offset+len(raw))
                if lo<hi:
                    if out is None:out=bytearray(raw)
                    out[lo-offset:hi-offset]=data[lo-at:hi-at]
            h.update(raw if out is None else out)
        f.seek(0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            while raw:=f.read(16<<20):
                list(pool.map(update,[(h,es,raw,pos) for h,es in zip(hashes,overlays)]));pos+=len(raw)
                tick=int(pos*100/iso_size)//10
                if tick!=last:print('Verify 96 full ISO hashes:',tick*10,'%',flush=True);last=tick
        digests=[x.hexdigest().upper() for x in hashes]
        assert digests[:32]==anchors,'Legacy profile reconstruction mismatch'
        hashes=digests[32:];assert hashes[31]==current_hash and len(set(hashes))==64
        # Deduplicate blobs so common new artwork is stored only once.
        pool=[];ids={}
        def ident(data):
            k=hashlib.sha256(data).digest()
            if k not in ids:ids[k]=len(pool);pool.append(data)
            else:assert pool[ids[k]]==data
            return ids[k]
        entries=[]
        for mask,(v,es) in enumerate(ordered):
            entries.append([(at,len(a),ident(a),ident(b)) for at,a,b in es])
        dest=HERE/'OGS_beowulf_options.bin';tmp=dest.with_suffix('.tmp')
        with tmp.open('wb') as out:
            out.write(b'OGSBEO01');out.write(struct.pack('<QII',iso_size,64,len(pool)))
            for data in pool:out.write(struct.pack('<I',len(data)));out.write(data)
            for mask,es in enumerate(entries):
                out.write(struct.pack('<I',mask));out.write(bytes.fromhex(anchors[mask&31]));out.write(bytes.fromhex(hashes[mask]));out.write(struct.pack('<I',len(es)))
                for row in es:out.write(struct.pack('<QIII',*row))
            out.flush();os.fsync(out.fileno())
        tmp.replace(dest)
        report=dict(version='v20261101',bits=dict(hidden=1,bundle=2,rewards=4,enemy=8,spirits=16,beowulf=32),
            defaults=0,hashes=hashes,anchors=anchors,profile_count=64,story_validation=proof,
            episode6_test_excluded=True,production_master_records_preserved=True,
            gameplay_ISO_read_only=True,production_sha256=current_hash,pack_sha256=file_hash(dest),pack_size=dest.stat().st_size,
            unique_blobs=len(pool),legacy_32_full_hashes_verified=True)
        (ROOT/'runtime/beowulf_options_profiles.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Six-option pack ready:',dest,report['pack_size'],flush=True)

def package_beowulf_options():
    import json,zipfile
    profiles=json.loads((ROOT/'runtime/beowulf_options_profiles.json').read_text(encoding='utf-8'))
    checks=json.loads((ROOT/'runtime/beowulf_patcher_validation.json').read_text(encoding='utf-8'))
    assert checks['passed'] and len(checks['actual_iso_cases'])==4
    assert file_hash(TARGET).lower()==profiles['production_sha256'].lower()
    assert file_hash(HERE/'OGS_beowulf_options.bin').lower()==profiles['pack_sha256'].lower()
    required=['OGS_AxelSwap_QuickPatch.exe','OGS_ISO_ranges.bin','OGS_hidden_rewards.bin',
        'OGS_ouka_zengar.bin','OGS_ouka_zengar_hidden.bin','OGS_optional_features.bin',
        'OGS_common_fix.bin','OGS_beowulf_options.bin']
    files=[HERE/n for n in required]+sorted(HERE.glob('OGS_ISO_ranges_upgrade*.bin'))
    assert all(p.exists() for p in files)
    readme=HERE/'읽어주세요.txt'
    readme.write_text('''슈퍼로봇대전 OGs 액셀 역할 교체 빠른 패처 v20261101

OGs 한글패치 v1.4.3s1 적용 ISO 또는 지원되는 이전 액셀 패치 ISO를 선택하고
원하는 옵션을 체크한 뒤 [패치 적용]을 누르세요.
기준 ISO 크기: 4,518,150,144바이트
기준 SHA256: 9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C

선택 옵션 (모두 기본 해제)
1. 숨겨진 요소 자동 습득 (OG2)
2. 오우카 생존 + 젠가 밸런스
3. 자금 +20% · PP 2배
4. 적 강화: 파일럿 능력치 +5, 기본 개조 +1단,
   기본 HP 20,000 미만인 적의 HP +10% (개조 상한 유지)
5. 액셀·제오라 정신기 변경
   액셀: 불굴→철벽(SP20), 트윈 예측→혼(SP50), 각성 SP50
   제오라: 저격→번뜩임(SP10), 철벽→가속(SP10)
6. 베어울프 등장 (추가 시나리오)
   알피미가 적으로 등장하는 본편 전투에 베어울프와 게슈펜스트 Mk-Ⅲ를 추가합니다.
   전용 초상화·컷인·기체 이미지 및 추가 대사를 포함하며, 전투 음성은 쿄스케의 것을 사용합니다.
   6화 아군 시험 배치는 포함하지 않습니다. HD팩 없이도 기본 그래픽으로 표시됩니다.

여섯 옵션은 각각 켜고 끌 수 있습니다. 이미 패치한 ISO에서도 체크를 바꿔 다시 적용하세요.
체크를 해제하면 해당 옵션의 ISO 데이터가 복원됩니다.
게임 내 세이브에 이미 기록된 보유품·자금·PP와 진행 상황은 되돌리지 않습니다.
이미 지나간 화의 합류·보상은 소급 지급되지 않습니다.

공통 변경
· 47화의 레몬·라미아 관련 화자/호칭 및 대사 교정
· 럭키 발동률: 스킬 레벨당 3% (9레벨 27%), 기존 에이스 보정 +10%p 유지
· 타스크·아라드의 럭키 성장: 레벨 1/8/15/23/30/38/45/53/60에서 스킬 1~9레벨
· 기존 무명·슬레이드겔미르 등 아군 추가 기체 데이터 유지
기존 역할 교체·무장별 전투 대사·보상 및 밸런스 변경은 유지합니다.

ISO를 직접 수정하며 작업 직전 구간을 <ISO명>.ogsbak으로 백업합니다.
[백업으로 되돌리기]는 마지막 패치 직전 상태로 복원합니다.
실행 파일과 옆의 모든 .bin 파일을 함께 두세요.

에뮬레이터를 완전히 종료한 뒤 패치하세요.
패치 후에는 새로 부팅하고 게임 내 메모리카드 세이브로 불러오세요.
이전 세이브 스테이트는 구 코드와 데이터를 복원하므로 사용하지 마세요.

검증: 기존 32개 배포 조합의 해시, 신규 64개 조합의 전체 ISO 해시,
기존 옵션 5,120개 바이트 전환, 베어울프 포함 4,096개 전환 경로,
실제 ISO 기본 설치·전체 옵션 켜기/끄기·백업 복원 확인.
새 시나리오 전체의 실기 플레이 검증을 뜻하지는 않습니다.

ISO는 포함하지 않습니다. 이 파일은 로컬 배포 준비본이며 GitHub 공개 릴리즈는 별도입니다.
''',encoding='utf-8-sig')
    files.append(readme)
    sums=HERE/'SHA256SUMS.txt'
    sums.write_text(''.join(file_hash(p)+'  '+p.name+'\n' for p in files),encoding='utf-8-sig')
    files.append(sums)
    out=ROOT/'dist/OGS_AxelSwap_QuickPatch_v20261101.zip'
    out.parent.mkdir(exist_ok=True);tmp=out.with_suffix('.tmp')
    prefix='OGS_AxelSwap_QuickPatch_v20261101/'
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:z.write(p,prefix+p.name)
    tmp.replace(out)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for p in files:assert hashlib.sha256(z.read(prefix+p.name)).hexdigest().upper()==file_hash(p)
    result=dict(zip=str(out),sha256=file_hash(out),size=out.stat().st_size,files=len(files),options=6,defaults=0)
    (ROOT/'runtime/beowulf_patcher_package.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


def package_options():
    import json,zipfile
    report=json.loads((ROOT/'runtime/optional_features_patcher_e2e.json').read_text(encoding='utf-8'))
    profiles=json.loads((ROOT/'runtime/common_fix_profiles.json').read_text(encoding='utf-8'))
    assert report['passed'] and len(report['real_iso_transitions'])==32
    assert report['production_composition_selftest']==5120
    assert report['current_gameplay_iso_unchanged']==profiles['iso_unchanged_sha256']
    assert file_hash(TARGET)==profiles['iso_unchanged_sha256'],'Gameplay ISO changed during patcher build'
    assert file_hash(HERE/'OGS_optional_features.bin')==profiles['features_file_sha256']
    assert file_hash(HERE/'OGS_common_fix.bin')==profiles['common_file_sha256']
    required=['OGS_AxelSwap_QuickPatch.exe','OGS_ISO_ranges.bin','OGS_hidden_rewards.bin',
        'OGS_ouka_zengar.bin','OGS_ouka_zengar_hidden.bin','OGS_optional_features.bin','OGS_common_fix.bin']
    files=[HERE/name for name in required]+sorted(HERE.glob('OGS_ISO_ranges_upgrade*.bin'))
    assert all(p.exists() for p in files)
    text="""슈퍼로봇대전 OGs 액셀 역할 교체 빠른 패처 v20261029.1

OGs 한글패치 v1.4.3s1 적용 ISO 또는 이전 액셀 패치 적용 ISO를 선택합니다.
OGS_AxelSwap_QuickPatch.exe를 실행하고 원하는 옵션을 체크한 뒤 [패치 적용]을 누르세요.
기준 ISO: 4,518,150,144바이트
기준 SHA256: 9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C

무명은 6화 종료 후 기체만 지급합니다. 5화 지급 삽입을 제거해 진행 문제에 대응했습니다. 이미 보유했다면 중복 지급하지 않습니다. 아군 무명 HP6300, 시시오 블레이드4600, 필살무장5600으로 조정했으며 적 무라타는 유지합니다. 무기 개조비용은 최저 등급을 제외하고20% 낮췄습니다.

아군 슬레이드겔미르는 HP8300·장갑2100, 여섯 무장 공격력+200입니다. 성체의태도는 이동 후 공격 가능·사거리1~2·배리어 관통으로 변경했습니다. 적 슬레이드겔미르는 유지합니다.

워단은 44화 마지막 결전 후 생환하여 기존 슬레이드겔미르에 합류합니다. 오우카 생존 옵션과 별개로 기본 적용됩니다.
37화 클리어 후 젠가의 참식참함도 장착형 그룬거스트 삼식을 기체만 추가 지급합니다. 기존 다른 삼식은 유지합니다.
이미 지급 시점이 지난 저장에는 소급 적용하지 않습니다.

선택 옵션 (모두 기본 해제)
1. 숨겨진 요소 자동 습득 (OG2): 기존 숨겨진 보상 자동 획득 옵션.
2. 오우카 생존 + 젠가 밸런스: 44화 양쪽 루트 오우카 합류·45화 후속 대사 및 다이젠가 강화 묶음.
3. 자금 +20% · PP 2배: 적 격추 보상에 적용. 이벤트 지급은 변경하지 않습니다.
4. 적 강화: 적 파일럿 격투·사격·기량·방어·명중·회피 각 +5,
   적 기체·무기 기본 개조 +1단, 기본 HP20,000미만 적의 기본HP10% 추가. 원래 개조 상한은 유지합니다.
5. 액셀·제오라 정신기 변경:
   액셀 불굴 → 철벽(SP20), 트윈 예측 → 혼(SP50), 각성 SP50.
   제오라 저격 → 번뜩임(SP10), 철벽 → 가속(SP10).
   습득 레벨 및 그 외 정신기는 유지합니다.

다섯 옵션은 각각 독립적으로 켜고 끌 수 있습니다.
이미 적용된 ISO를 다시 선택하고 체크를 바꾸면 선택한 조합으로 전환합니다.
체크를 해제하면 그 옵션의 패치 데이터만 원래대로 되돌립니다.
세이브에 이미 쌓인 자금·PP·보유품은 회수하지 않습니다.
숨겨진 보상은 지나간 화에 소급 지급되지 않으며, 적 기본 개조는 적 생성 시 적용됩니다.

패치 전 ISO 구간을 같은 경로의 <ISO명>.ogsbak으로 백업합니다.
[백업으로 되돌리기]는 마지막 패치 작업 직전 상태로 복원합니다.
패처 옆 .bin 파일은 모두 함께 두세요. 실행 파일만 옮기면 작동하지 않습니다.

PCSX2를 완전히 종료한 뒤 패치하세요.
패치 후 에뮬레이터를 새로 실행하고 게임 내 메모리카드 세이브로 불러오세요.
이전 세이브 스테이트는 이전 코드와 데이터를 복원하므로 사용하지 마세요.

검증: 전체 32개 조합의 ISO SHA256, 패처 내 전환 5,120가지,
실제 ISO 32개 조합 적용 및 대표 조합 백업 복원 검증 통과.
게임 플레이 전체를 새로 검증한 것은 아닙니다.

이 ZIP은 패처 배포용 파일이며 ISO는 포함하지 않습니다.
공개 GitHub 릴리즈는 별도로 갱신하지 않았습니다.
"""
    readme=HERE/'읽어주세요.txt';readme.write_text(text,encoding='utf-8-sig');files.append(readme)
    sums=HERE/'SHA256SUMS.txt'
    sums.write_text(''.join(file_hash(p)+'  '+p.name+'\n' for p in files),encoding='utf-8-sig');files.append(sums)
    out=ROOT/'dist/OGS_AxelSwap_QuickPatch_v20261029.1.zip';out.parent.mkdir(exist_ok=True)
    tmp=out.with_suffix('.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:z.write(p,'OGS_AxelSwap_QuickPatch_v20261029.1/'+p.name)
    tmp.replace(out)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for p in files:
            assert hashlib.sha256(z.read('OGS_AxelSwap_QuickPatch_v20261029.1/'+p.name)).hexdigest().upper()==file_hash(p)
    result=dict(zip=str(out),sha256=file_hash(out),files=len(files),size=out.stat().st_size)
    (ROOT/'runtime/optional_features_package.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    import sys
    if "--package-beowulf" in sys.argv:package_beowulf_options()
    elif "--beowulf-options" in sys.argv:build_beowulf_extension()
    elif "--maintenance-common" in sys.argv:build_maintenance_common()
    elif "--story-common" in sys.argv:build_story_common()
    elif "--package-options" in sys.argv:package_options()
    elif "--common-fix" in sys.argv:build_options(common_fix=True)
    elif "--options" in sys.argv:build_options()
    else:main()
