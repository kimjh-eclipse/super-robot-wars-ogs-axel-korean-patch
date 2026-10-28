"""Guarded OG2 optional reward patch; LOGO offsets are relative to Wpbb.

Analysis uses the current ISO, never rebuilds dialogue or unit master data.
"""
from pathlib import Path
import struct, json, hashlib, argparse
from ogs_korean_codec import decode
import sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent
ISO=ROOT/'build/SRWOGS_K.iso'
MAP=0xC10800
EXPECTED='5432a2f5066db50e54511ab2c3a0744a56911fa4510a519ab65fb803ce7114a8'
DEAD=0xDEADDEAD
def u32(b,p): return struct.unpack_from('<I',b,p)[0]
class Scripts:
    def __init__(self,path=ISO):
        with open(path,'rb') as f:
            f.seek(MAP); self.data=f.read(0x9600000)
        self.logos=[]
        wp=0x557F800
        assert self.data[wp:wp+4]==b'Wpbb'
        for n in range(u32(self.data,wp+4)):
            o,s=struct.unpack_from('<II',self.data,wp+8+n*8)
            at=wp+o
            assert self.data[at:at+4]==b'LOGO',(n,hex(at))
            self.logos.append((at,s))
    def records(self,n):
        at,_=self.logos[n]; count,off=struct.unpack_from('<II',self.data,at+0x28)
        return [(at+off+i*0x60,struct.unpack_from('<24I',self.data,at+off+i*0x60)) for i in range(count)]
    def dump(self,n,start=0,end=None):
        rs=self.records(n)
        for i in range(start,min(len(rs),end or len(rs))):
            at,r=rs[i]; last=max(j for j,v in enumerate(r) if v!=DEAD)
            print(f'{n}:{i} {at:08X} '+ ' '.join('_' if v==DEAD else f'{v:X}' for v in r[:last+1]))
    def texts(self,n):
        at,_=self.logos[n]; count,table=struct.unpack_from('<II',self.data,at+0x50); pool=u32(self.data,at+0x4C)
        out=[]
        for i in range(count):
            p=at+pool+u32(self.data,at+table+i*4)
            end=self.data.find(b'\0',p)
            out.append((p,decode(self.data[p:end])))
        return out
def command(op,*args):
    return [op,DEAD,*args]+[DEAD]*(22-len(args))

def plan(s):
    blobs={}; notes=[]
    def get(n):
        if n not in blobs:
            at,size=s.logos[n];blobs[n]=bytearray(s.data[at:at+size])
        return blobs[n]
    def replace(n,i,new,reason,expect=None):
        b=get(n);off=u32(b,0x2C)+i*0x60
        old=list(struct.unpack_from('<24I',b,off))
        if expect is not None:assert old[0]==expect,(n,i,hex(old[0]),hex(expect))
        struct.pack_into('<24I',b,off,*new)
        notes.append(dict(script=n,record=i,reason=reason,before=old,after=new))
    def cond(n,i,truth,reason):
        r=list(s.records(n)[i][1]);assert r[0] in [0x8B,0x8C]
        r[2:5]=[1 if truth else 0,0x8000,1]
        replace(n,i,r,reason,r[0])
    # Remove only the failure branch which confiscates the starting weapon.
    cond(88,68,False,'22화 그라비톤 런처 조건 실패 시 제거를 생략')
    cond(89,1183,True,'23화 클리어 부스트 해머')
    cond(90,922,True,'24화 클리어 시시오 블레이드')
    cond(100,89,True,'34화 마이 빌트뷔르거 L 출격 선택')
    cond(100,1766,True,'34화 클리어 빌트뷔르거 L 분기 선택')
    cond(100,1768,False,'34화 클리어 빌트뷔르거 L 회수 방지 및 획득 메시지')
    # Move just the equipment command out of Easy's three stat adjustments.
    r=list(s.records(101)[505][1]);assert r[0]==0x8C and r[7]==6;r[7]=5
    replace(101,505,r,'35화 쉬움 능력치 조정은 유지하고 부메랑만 공통 지급',0x8C)
    equip=list(s.records(101)[509][1]);assert equip[:5]==[0x21,DEAD,0x100B9,0x532,0xDBA]
    replace(101,509,list(s.records(101)[510][1]),'35화 난이도 분기 종료를 지급 앞으로 이동',0x21)
    replace(101,510,equip,'35화 길리엄 스텔스 부메랑 모든 난이도 지급',0x85)
    cond(105,187,False,'39화 카라 스텔스 부메랑 제거 방지')
    cond(106,1844,True,'40화 클리어 강철의 혼/용자의 증표 회차 조건 해제')
    cond(118,44,True,'42화 카이 레벨 조건 해제')
    cond(118,46,True,'42화 카이 격추수 조건 해제')
    cond(119,42,True,'42화 휴케바인 R 사전 플래그 조건 해제')
    cond(119,54,True,'42화 휴케바인 R 레벨 합계 조건 해제')
    # All downstream reads use the success value, including alternate-route
    # rejoin scripts. Keep original branch bodies and spawn groups intact.
    for n in range(65,138):
        for i,(at,r) in enumerate(s.records(n)):
            if r[0]!=0x8E or r[2]!=0x100BD:continue
            group,bit,dst=r[3:6]
            reward=None
            if n>=105 and group==0x13 and bit in (0,1,2):reward='39화 레이븐 두 기체 및 이후 합류 유지'
            if n>=106 and group==0xC and bit in (6,7):reward='게슈펜스트 S/휴케바인 R 양쪽 루트 합류 유지'
            if n==119 and (group,bit)==(0xF,3):reward='42화 G 임팩트 스테이크/네오 차크람 슈터'
            if reward:replace(n,i,command(0x95,1,dst),reward,0x8E)
    # Inspector grants occur once at scenario clear. Reuse original item IDs
    # and localized messages; remove the original optional boss-death grants.
    n=88;rs=s.records(n)
    start=next(i for i,(at,r) in enumerate(rs) if at==0x5FC8680)
    moved=[list(rs[i][1]) for i in range(start,start+7)]
    assert [r[0] for r in moved]==[0x5B]*3+[0x5F]*2+[0x33]*2
    for i in range(start,start+7):replace(n,i,command(0x85),'22화 보상 중복 지급/중복 안내 방지',rs[i][1][0])
    b=get(n);insert=812;amount=len(moved);co=u32(b,0x2C);pos=co+insert*0x60
    # Branch spans are relative command counts. This insertion is in the
    # unconditional clear block; reject unexpected branches crossing it.
    for i,(at,r) in enumerate(rs):
        if r[0] in (0x8B,0x8C):
            for j in ([6,7] if r[0]==0x8B else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j],(i,j,r[j])
    b[pos:pos]=b''.join(struct.pack('<24I',*r) for r in moved)
    for off in [4,0x6C]:struct.pack_into('<I',b,off,u32(b,off)+amount*0x60)
    struct.pack_into('<I',b,0x28,u32(b,0x28)+amount)
    for off in [0x34,0x3C,0x44,0x4C,0x54,0x5C]:
        assert u32(b,off)>=pos
        struct.pack_into('<I',b,off,u32(b,off)+amount*0x60)
    notes.append(dict(script=88,insert_before=insert,records=moved,reason='22화 인스펙터 5종 보상과 기존 안내를 클리어 시점으로 이동'))
    edits=[]
    for n,b in sorted(blobs.items()):
        at,size=s.logos[n];cap=s.logos[n+1][0]-at
        assert len(b)<=cap,(n,len(b),cap)
        if len(b)>size:
            pad=s.data[at+size:at+len(b)];assert set(pad)<={0},(n,pad.hex())
            # Directory lengths describe the child payload; offsets stay fixed.
            dp=0x557F800+8+n*8+4
            edits.append((MAP+dp,s.data[dp:dp+4],struct.pack('<I',len(b))))
        old=s.data[at:at+len(b)]
        # Tight contiguous diffs for guards, backup and the optional pack.
        j=0
        while j<len(b):
            if b[j]==old[j]:j+=1;continue
            k=j+1
            while k<len(b) and b[k]!=old[k]:k+=1
            edits.append((MAP+at+j,old[j:k],bytes(b[j:k])));j=k
    return sorted(edits),notes,blobs

def sha(path):
    with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def build(apply=False):
    before=sha(ISO)
    assert before==EXPECTED,('Current ISO changed; audit first',before)
    s=Scripts();edits,notes,blobs=plan(s)
    # Hash the entire prospective output without modifying any file.
    h=hashlib.sha256();cursor=0
    with open(ISO,'rb') as f:
        for off,old,new in edits:
            while cursor<off:
                b=f.read(min(4<<20,off-cursor));assert b;h.update(b);cursor+=len(b)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while b:=f.read(4<<20):h.update(b)
    after=h.hexdigest()
    report=dict(source_sha256=before,target_sha256=after,edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits],decisions=notes,applied=False)
    out=ROOT/'runtime/hidden_rewards_manifest.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        assert sha(ISO)==before
        with open(ISO,'r+b') as f:
            for off,old,new in edits:f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
            f.flush()
        assert sha(ISO)==after
        report['applied']=True;out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(applied=apply,source=before,target=after,ranges=len(edits),bytes=sum(len(a) for _,_,a in edits),decisions=len(notes)),indent=2))

def grant_mumei(apply=False):
    """Independent episode-5 robot-only reward; preserve the installed option.

    Alias 0x600 avoids enemy key 0x52A removal/spawn events. A narrowly
    keyed wrapper makes only this grant affiliation 1, instead of reserve 31.
    The original opcode still performs allocation and duplicate detection.
    """
    expected='687397fa1e1b57cb6fd547b3d6a23701b7ae529c500b491360b6b69566eb1735'
    before=sha(ISO)
    assert before==expected,('Audit changed ISO before applying',before)
    s=Scripts();n=138;insert=626;at,size=s.logos[n]
    rs=s.records(n);assert len(rs)==803 and rs[insert][1][:4]==(0x9C,DEAD,1,0)
    assert rs[insert-4][1][:4]==(0xC5,DEAD,5,0)
    b=bytearray(s.data[at:at+size]);original=bytes(b)
    co=u32(b,0x2C);pos=co+insert*96
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8B,0x8C):
            for j in ([6,7] if r[0]==0x8B else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j],(i,j)
    b[pos:pos]=struct.pack('<24I',*command(0x5A,0x600))
    for off in [4,0x6C]:struct.pack_into('<I',b,off,u32(b,off)+96)
    struct.pack_into('<I',b,0x28,u32(b,0x28)+1)
    for off in [0x34,0x3C,0x44,0x4C,0x54,0x5C]:
        assert u32(b,off)>=pos
        struct.pack_into('<I',b,off,u32(b,off)+96)
    assert len(b)<=s.logos[n+1][0]-at and not any(s.data[at+size:at+len(b)])
    # Removing the inserted command and undoing header fields must reproduce
    # every old record, auxiliary table and encoded dialogue byte exactly.
    restored=bytearray(b);del restored[pos:pos+96];restored[:0x70]=original[:0x70]
    assert restored==original
    edits=[]
    def add(off,old,new):
        assert len(old)==len(new)
        with ISO.open('rb') as f:f.seek(off);assert f.read(len(old))==old,hex(off)
        edits.append((off,old,new))
    add(MAP+at,s.data[at:at+len(b)],bytes(b))
    add(MAP+0x557F800+12+n*8,struct.pack('<I',size),struct.pack('<I',len(b)))
    for base in [0x5DA000,0x83F000]:
        add(base+0x11E88C+12+0x600*2,b'\xff\xff',struct.pack('<H',0x15C))
        add(base+0x11F898+12+0x15C*100+0x22,b'\0\0',b'\xff\xff')
    cave=0x114F88
    words=[0x8E280008,0x39080600,0x15000002,0,0x24070001,
           0x08000000|(0x1AF000>>2),0x0000402D]
    code=struct.pack('<7I',*words)
    elf=lambda va:0x94880+va-0x100000
    add(elf(cave),bytes(len(code)),code)
    add(elf(0x2D0F90),struct.pack('<I',0x0C000000|(0x1AF000>>2)),
        struct.pack('<I',0x0C000000|(cave>>2)))
    edits.sort()
    for x,y in zip(edits,edits[1:]):assert x[0]+len(x[1])<=y[0]
    from validate_hidden_rewards import validate_mumei
    checks=validate_mumei(edits,code)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='OG2 episode 5 clear: Mumei robot only, no Murata pilot',
        checks=checks,edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/mumei_grant_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import subprocess,os
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        with ISO.open('r+b') as f:
            for off,old,new in edits:
                f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
            f.flush();os.fsync(f.fileno())
        assert sha(ISO)==report['target_sha256']
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def episode6_bonus(apply=False):
    """Six additive grants at OG2 episode 6 clear; no dialogue/master edits."""
    expected='7d3e4cf7598d2b45ea138852bbd1dde59b6ca37790944c55d997038d267a7eaf'
    before=sha(ISO)
    assert before==expected,('Audit changed ISO before applying',before)
    s=Scripts();n=74;insert=526;at,size=s.logos[n];rs=s.records(n)
    assert len(rs)==529 and rs[insert][1][:4]==(0x9C,DEAD,2,0)
    # Reuse native reward identifiers verified against episodes 22/23/24.
    assert s.records(89)[1184][1][:4]==(0x5F,DEAD,0xDCA,0)
    assert s.records(90)[923][1][:4]==(0x5F,DEAD,0xDB9,0)
    assert s.records(88)[816][1][:4]==(0x5F,DEAD,0xDAC,0)
    grants=[command(0x5F,k,0) for k in (0xDCA,0xDB9,0xDAC)]
    grants += [command(0x5B,k,0) for k in (0x1F,0x20,0x21)]
    original=s.data[at:at+size];b=bytearray(original)
    pos=u32(b,0x2C)+insert*96;amount=len(grants)*96
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8B,0x8C):
            for j in ([6,7] if r[0]==0x8B else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j],(i,j)
    # No text-bearing command follows this clear point: lookup values remain valid.
    lookup=struct.unpack_from('<%dI'%u32(b,0x38),b,u32(b,0x3C))
    assert max(lookup)<insert+u32(b,0x20)
    b[pos:pos]=b''.join(struct.pack('<24I',*r) for r in grants)
    for off in (4,0x6C):struct.pack_into('<I',b,off,u32(b,off)+amount)
    struct.pack_into('<I',b,0x28,len(rs)+len(grants))
    for off in (0x34,0x3C,0x44,0x4C,0x54,0x5C):
        assert u32(b,off)>=pos
        struct.pack_into('<I',b,off,u32(b,off)+amount)
    restored=bytearray(b);del restored[pos:pos+amount];restored[:0x70]=original[:0x70]
    assert restored==original,'Existing commands, tables and dialogue must remain byte-identical'
    assert len(b)<=s.logos[n+1][0]-at and not any(s.data[at+size:at+len(b)])
    dp=0x557F800+12+n*8
    edits=sorted([(MAP+dp,s.data[dp:dp+4],struct.pack('<I',len(b))),
                  (MAP+at,s.data[at:at+len(b)],bytes(b))])
    from validate_hidden_rewards import validate_episode6_bonus
    checks=validate_episode6_bonus(grants)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='OG2 episode 6 clear: Boost Hammer, Shishio Blade, G Impact Stake, Steel Soul, Hero Mark, High Performance Electronic Brain; +1 each',
        script=n,insert_before=insert,grants=grants,checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/episode6_bonus_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import subprocess,os
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('edits','grants')},ensure_ascii=False,indent=2))

def daizengar_durability(apply=False):
    """User-requested +1000 HP/+200 armor in all three Daizengar variants."""
    expected='1cd99b938c23ee0806effaabe11aad2dc79055bd5b2d96d0a312f6982623850f'
    before=sha(ISO)
    assert before==expected,('Audit changed ISO before applying',before)
    edits=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            for idx in (0xD0,0xD1,0x176):
                p=base+0x11F8A4+idx*100;f.seek(p);r=f.read(100)
                assert struct.unpack_from('<H',r,0x0C)[0]==0x150
                assert u32(r,0)==7800 and struct.unpack_from('<H',r,0x1A)[0]==1900
                edits.extend([(p,r[:4],struct.pack('<I',8800)),
                              (p+0x1A,r[0x1A:0x1C],struct.pack('<H',2100))])
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Daizengar all three variants, SHARED/IM: HP 7800 -> 8800; armor 1900 -> 2100',
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/daizengar_durability_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import subprocess,os
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def daizengar_refit(apply=False):
    """Restore the native DT type-7 refit between sword and built-in weapons."""
    before=sha(ISO)
    assert before=='dd7d0d59bd4a3f47ce61d5d55232ff87d8f491b1bad881c76da1de520a90155e',before
    edits=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            for rel,old,new in [
                # DTS[60] already points at DT[111]: return to built-in 0x49A.
                (0x11F8A4+0xD0*100+0x5E,b'\0',b'\x3c'),
                # Built-in DTS[33] -> DT[110]. Use normal acquired sword form,
                # rather than unused 0x543, and remove required unit 0x56E.
                (0x1492BC+110*12+2,b'\x43\x05\x6e\x05',b'\x99\x04\xff\xff')]:
                f.seek(base+rel);assert f.read(len(old))==old,(hex(base+rel),old)
                edits.append((base+rel,old,new))
        # The stock preview builder only creates a refit row after finding
        # an equipment-unit record. Add its no-equipment case in place.
        # Reusing the first computed UI pointer saves two instructions;
        # the branch enters the existing preview allocation path once.
        va=0x42DEB4;off=0x94880+va-0x100000
        old=struct.pack('<5I',0x3C010001,0x7FA200B0,0x342156E4,0x02E11021,0x7FA200A0)
        new=struct.pack('<5I',0x7FA200B0,0x244205F4,0x7FA200A0,0x8FA300FC,0x04600014)
        f.seek(off);assert f.read(len(old))==old
        edits.append((off,old,new))
    from validate_hidden_rewards import validate_daizengar_refit
    checks=validate_daizengar_refit(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Daizengar normal 0x499 <-> built-in 0x49A through native refit menu',checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/daizengar_refit_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import subprocess,os
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def melee_range_two(apply=False):
    """Requested melee weapons: range 1 -> 1-2 in both master copies."""
    before=sha(ISO)
    assert before=='0f03d735593756d080f009816e8566ea4e396a38e6e3f88a8642ef300cae25b4',before
    targets={0x1D5:'계도나후검・암검살',0x1D9:'계도나후검・암검살',
             0x1DD:'계도나후검・암검살',0x1E1:'계도나후검・암검살',
             0x30F:'참함도・운요의태도',0x578:'참함도・운요의태도',
             0x3C5:'스태그비틀크래셔',0x3CA:'스태그비틀크래셔',
             0x60B:'시시오블레이드',0x639:'시시오블레이드'}
    edits=[];records={}
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            f.seek(base);blob=f.read(0x190000)
            assert blob[0x12BF7C:0x12BF80]==b'Weap'
            for idx,name in targets.items():
                rel=0x12BF88+idx*36;r=blob[rel:rel+36]
                sid=struct.unpack_from('<H',r,4)[0]
                p=0x155BFC+u32(blob,0x155C08+sid*4)
                # IM retains Japanese strings; its weapon record must still
                # match the localized SHARED record byte for byte below.
                if base==0x5DA000:assert decode(blob[p:blob.index(0,p)])==name
                assert r[0x17:0x19]==b'\1\1',(idx,r.hex())
                if idx in records:assert records[idx]==r
                records[idx]=r
                edits.append((base+rel+0x18,b'\1',b'\2'))
            # Mumei's fixed Shishio weapons already have range 1-3.
            for idx in (0x528,0x5F4):
                assert blob[0x12BF88+idx*36+0x17:0x12BF88+idx*36+0x19]==b'\1\3'
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Requested melee weapons: maximum range 1 -> 2; minimum remains 1',
        weapons={hex(i):n for i,n in targets.items()},
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/melee_range_two_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import subprocess,os
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def weapon_balance(apply=False):
    """DGG attack/upgrade changes and DGG + Riese barrier penetration."""
    before=sha(ISO)
    assert before=='9ef321ab5af7e5f25df9a96904e793fd09797995d8cc48b452320175144b20bd',before
    dai=set(range(0x30C,0x314))|set(range(0x575,0x57A))
    aus=set(range(0xA8,0xAE));riese=set(range(0xDC,0xE2))
    targets=dai|aus|riese;edits=[];records={};weapons=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            f.seek(base);blob=f.read(0x190000)
            assert blob[0x12BF7C:0x12BF80]==b'Weap'
            assert blob[0x12BF88+0x609*36+3]&0x3F==0
            for idx in sorted(targets):
                rel=0x12BF88+idx*36;old=blob[rel:rel+36];new=bytearray(old)
                if idx in records:assert records[idx]==old
                records[idx]=old
                power=struct.unpack_from('<H',old,8)[0]
                # Zero-power combination attacks use Tagg constituent attacks;
                # do not replace their computed power with a fixed 200.
                if idx in dai|aus and power:
                    struct.pack_into('<H',new,8,power+200)
                if idx in dai and power:new[3]&=0xC0
                # Native getter 1A4CB0: Weap+15 bits4..5; 2 is penetration,
                # 1 is weakening. Preserve every unrelated flag.
                new[0x15]=(new[0x15]&0xCF)|0x20
                if base==0x5DA000:
                    sid=struct.unpack_from('<H',old,4)[0]
                    p=0x155BFC+u32(blob,0x155C08+sid*4)
                    weapons.append(dict(index=hex(idx),name=decode(blob[p:blob.index(0,p)]),
                        power_before=power,power_after=struct.unpack_from('<H',new,8)[0],
                        combined=not power,upgrade_before=old[3]&0x3F,upgrade_after=new[3]&0x3F,
                        barrier_before=(old[0x15]>>4)&3,barrier_after=2))
                for j,(a,b) in enumerate(zip(old,new)):
                    if a!=b:edits.append((base+rel+j,bytes([a]),bytes([b])))
    from validate_hidden_rewards import validate_weapon_balance
    checks=validate_weapon_balance(edits,targets,dai,aus)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        checks=checks,weapons=weapons,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/weapon_balance_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import subprocess,os
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('edits','weapons')},ensure_ascii=False,indent=2))

def grant_sladegelmir(apply=False):
    """Add one independent robot at OG2 episode 37 clear."""
    before=sha(ISO)
    assert before=='2ba436de324d215ed070cae45ed1c103feba29123514cf2dd5d3d9d6b07b1da2',before
    s=Scripts();n=103;insert=1463;at,size=s.logos[n];rs=s.records(n)
    assert len(rs)==1466 and rs[insert][1][:4]==(0x9C,DEAD,0x1D,0)
    original=s.data[at:at+size];b=bytearray(original);co=u32(b,0x2C);pos=co+insert*96
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8B,0x8C):
            for j in ([6,7] if r[0]==0x8B else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j],(i,j)
    assert max(u32(b,u32(b,0x3C)+i*4) for i in range(u32(b,0x38)))<insert+u32(b,0x20)
    b[pos:pos]=struct.pack('<24I',*command(0x5A,0x601))
    for off in (4,0x6C):struct.pack_into('<I',b,off,u32(b,off)+96)
    struct.pack_into('<I',b,0x28,len(rs)+1)
    for off in (0x34,0x3C,0x44,0x4C,0x54,0x5C):
        assert u32(b,off)>=pos;struct.pack_into('<I',b,off,u32(b,off)+96)
    assert len(b)<=s.logos[n+1][0]-at and not any(s.data[at+size:at+len(b)])
    restored=bytearray(b);del restored[pos:pos+96];restored[:0x70]=original[:0x70]
    assert restored==original
    edits=[]
    def add(off,old,new):
        assert len(old)==len(new)
        with ISO.open('rb') as f:f.seek(off);assert f.read(len(old))==old,hex(off)
        if old!=new:edits.append((off,old,new))
    add(MAP+at,s.data[at:at+len(b)],bytes(b))
    add(MAP+0x557F800+12+n*8,struct.pack('<I',size),struct.pack('<I',len(b)))
    for base in (0x5DA000,0x83F000):
        with ISO.open('rb') as f:f.seek(base);master=f.read(0x190000)
        assert struct.unpack_from('<H',master,0x11E898+0x490*2)[0]==0xC8
        assert struct.unpack_from('<H',master,0x11F8A4+0xC8*100+0x0C)[0]==0x144
        # Only player key469 points at OG2 Sanger A3. Reserve an unused pilot
        # category so he can leave AND return to his otherwise dedicated Dai.
        assert [k for k in range(2048) if struct.unpack_from('<H',master,0x13A484+k*2)[0]==0xA3]==[0x469]
        assert all(not struct.unpack_from('<H',master,0x13B490+i*148+0x12)[0]&0x8000 for i in range(382))
        add(base+0x11E898+0x601*2,b'\xff\xff',struct.pack('<H',0xC8))
        add(base+0x11F8A4+0xC8*100+0x22,b'\0\0',b'\xff\xff')
        add(base+0x13B490+0xA3*148+0x12,b'\0\0',b'\0\x80')
        for idx in (0xD0,0xD1,0x176):
            add(base+0x11F8A4+idx*100+0x22,b'\0\0',b'\0\x80')
    # Extend the existing Mumei wrapper: only reward aliases600/601 get
    # owned affiliation1. All ordinary grants retain the original argument.
    old=struct.pack('<8I',0x8E280008,0x39080600,0x15000002,0,0x24070001,0x0806BC00,0x0000402D,0)
    code=struct.pack('<8I',0x8E280008,0x39080600,0x2D080002,0x11000002,0,0x24070001,0x0806BC00,0x0000402D)
    add(0x94880+0x114F88-0x100000,old,code)
    from validate_hidden_rewards import validate_sladegelmir
    checks=validate_sladegelmir(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            assert cursor<=off
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='OG2 episode37 clear Sladegelmir robot only; native stats retained',checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/sladegelmir_grant_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import subprocess,os
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def daizengar_refit_labels(apply=False):
    """Name the two refit choices without renaming the robot or global strings."""
    from ogs_korean_codec import encode
    before=sha(ISO)
    assert before=='5b7958c7299ef20f8cee17f211f03ce5d29e2247505d8fdbba9dbb9455e6fa1b',before
    cave=0x499D38;strings=0x114FA8
    words=[0x3C080001,0x02E84021,0x950955C6,0x2529FB67,
           0x2D2A0002,0x11400008,0x000948C0,
           0x3C0A0011,0x254A4FA8,0x01495821,0xAD0B56E4,
           0x39290008,0x01495821,0xAD0B56E8,
           0xDFBF0090,0x7BBE0080,0x0810B8B2,0]
    code=struct.pack('<18I',*words)
    names=encode('참함도').ljust(8,b'\0')+encode('기본').ljust(8,b'\0')
    assert len(names)==16
    elf=lambda va:0x94880+va-0x100000
    edits=[(elf(cave),bytes(len(code)),code),(elf(strings),bytes(16),names),
           (elf(0x42E2C0),struct.pack('<2I',0xDFBF0090,0x7BBE0080),struct.pack('<2I',0x08000000|(cave>>2),0))]
    with ISO.open('rb') as f:
        for off,old,new in edits:f.seek(off);assert f.read(len(old))==old,hex(off)
    from validate_hidden_rewards import validate_refit_labels
    checks=validate_refit_labels(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/daizengar_refit_labels_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import os,subprocess
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def daizengar_refit_visibility(apply=False):
    """Fix DT110's scenario lock in the refit eligibility scan, plus row0 label."""
    before=sha(ISO)
    assert before=='285fd41ad2df72317995c827587b4d67b1c297543db4245eeefb0e2b01653e1f',before
    elf=lambda va:0x94880+va-0x100000
    pack=lambda words:struct.pack('<%dI'%len(words),*words)
    # DT110 is referenced ONLY by built-in Daizengar Unit D1. Keep the stored
    # scenario flag intact; bypass only this menu's type7 eligibility query.
    # 12-byte function-alignment padding immediately before the stock getter.
    # DT110 returns zero through a native jr ra/nop; all others fall through
    # to the untouched getter. Neither global data nor runtime state is used.
    wrapper=[0x24A1FF92,0x10200000|(((0x1985E8-0x19A0BC)//4)&0xFFFF),0x0000102D]
    oldlabel=[0x3C080001,0x02E84021,0x950955C6,0x2529FB67,
        0x2D2A0002,0x11400008,0x000948C0,0x3C0A0011,0x254A4FA8,
        0x01495821,0xAD0B56E4,0x39290008,0x01495821,0xAD0B56E8,
        0xDFBF0090,0x7BBE0080,0x0810B8B2,0]
    # Clear row0 for ordinary refits, even after visiting Daizengar in same UI.
    newlabel=oldlabel[:5]+[0x11400009,0xAD0056E4,0x000948C0]+oldlabel[7:14]+[0xDFBF0090,0x0810B8B2,0x7BBE0080]
    assert len(newlabel)==18
    edits=[(elf(0x19A0B4),bytes(12),pack(wrapper)),
        (elf(0x44D424),bytes(12),pack([0x00E7300B,0x08060D34,0x0000382D])),
        (elf(0x43EAA0),pack([0x0C066830]),pack([0x0C000000|(0x19A0B4>>2)])),
        (elf(0x499D38),pack(oldlabel),pack(newlabel)),
        (elf(0x44EEC4),pack([0x0C060D34,0x0000382D]),pack([0x0C000000|(0x44D424>>2),0x8E0705F4]))]
    with ISO.open('rb') as f:
        for off,old,new in edits:f.seek(off);assert f.read(len(old))==old,hex(off)
        # Guard return stub and alignment gaps on both ends.
        f.seek(elf(0x1985E8));assert f.read(8)==pack([0x03E00008,0])
        for gap in (0x19A0B4,0x44D424):
            f.seek(elf(gap-8));assert u32(f.read(4),0)==0x03E00008
            f.seek(elf(gap+12));assert u32(f.read(4),0)>>16==0x27BD
        f.seek(0x5DA000);b=f.read(0x190000)
    refs=[]
    for idx in range(427):
        dts=struct.unpack_from('<H',b,0x11F8A4+idx*100+0x5E)[0]
        if dts<63 and 110 in b[0x149174+dts*5:0x149179+dts*5]:refs.append(idx)
    assert refs==[0xD1],refs
    from validate_hidden_rewards import validate_refit_visibility
    checks=validate_refit_visibility(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/daizengar_refit_visibility_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import os,subprocess
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def daizengar_builtin_weapons(apply=False):
    """General Blaster ALL; Guardian Sword range1-2. Four ISO bytes only."""
    before=sha(ISO)
    assert before=='2c28ac820bfb2d410c67569166a531a5d423c32aecefa54dc2c969403f752041',before
    edits=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            for idx,field,old,new in ((0x312,0x14,b'\0',b'\x80'),(0x313,0x18,b'\1',b'\2')):
                off=base+0x12BF88+idx*36+field
                f.seek(off);assert f.read(1)==old
                edits.append((off,old,new))
    from validate_hidden_rewards import validate_builtin_weapons
    checks=validate_builtin_weapons(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/daizengar_builtin_weapons_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import os,subprocess
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def release_preflight(apply=False):
    """Relocate existing LOGO lookup entries alongside inserted reward commands."""
    before=sha(ISO)
    assert before=='1a46685f9bf38766e29893e4264225d334477138d5b949cfd7496c68458050bd',before
    s=Scripts();base=Scripts(ROOT/'baseline/srwogs-v1.4.3s1.iso');edits=[];counts={}
    for n in (138,88):
        at,size=s.logos[n];b=s.data[at:at+size]
        ba,bs=base.logos[n];original=base.data[ba:ba+bs]
        actors=u32(b,0x20);assert actors==u32(original,0x20)
        count=u32(b,0x38);assert count==u32(original,0x38)
        fixed=0
        for i in range(count):
            pos=u32(b,0x3C)+i*4;old=u32(b,pos)
            assert old==u32(original,u32(original,0x3C)+i*4)
            record=old-actors;target=record
            if n==138 and record>=626:target+=1
            if n==88:
                if 681<=record<688:target=812+record-681
                elif record>=812:target+=7
            new=target+actors
            # Every entry still resolves to the original opcode, including
            # the two Inspector reward-message entries moved to scenario clear.
            def opcode(blob,index):
                if index<actors:return u32(blob,u32(blob,0x24)+index*96)
                return u32(blob,u32(blob,0x2C)+(index-actors)*96)
            assert opcode(b,new)==opcode(original,old),(n,i,old,new)
            if new!=old:
                edits.append((MAP+at+pos,struct.pack('<I',old),struct.pack('<I',new)));fixed+=1
        counts[n]=fixed
    assert counts=={138:41,88:3},counts
    checks=dict(lookup_entries_corrected=counts,all_lookup_opcodes_match_original=True,
        encoded_dialogue_bytes_unchanged=True,live_playthrough=False)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/release_preflight_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import os,subprocess
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def ouka_route_fix_plan(path=ISO):
    from ogs_korean_codec import encode
    s=Scripts(path);edits=[];blobs={};dialogue=[]
    def add(at,new):
        with Path(path).open('rb') as f:f.seek(at);old=f.read(len(new))
        assert len(old)==len(new)
        if old!=new:edits.append((at,old,bytes(new)))
    n=131;at,size=s.logos[n];b=bytearray(s.data[at:at+size]);rs=s.records(n)
    insert=next(i for i,(_,r) in enumerate(rs) if r[:4]==(0x9C,DEAD,0x22,0))
    assert insert==1188 and len(rs)==1191
    co=u32(b,0x2C);pos=co+insert*96
    assert max(u32(b,u32(b,0x3C)+i*4) for i in range(u32(b,0x38)))<insert+u32(b,0x20)
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8B,0x8C):
            for j in ([6,7] if r[0]==0x8B else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j]
    b[pos:pos]=struct.pack('<24I',*command(0x5E,0x26))
    struct.pack_into('<I',b,0x28,len(rs)+1)
    for off in (0x34,0x3C,0x44,0x4C,0x54,0x5C):
        assert u32(b,off)>=pos;struct.pack_into('<I',b,off,u32(b,off)+96)
    blobs[n]=b
    changes={
        41:'브릿트：그래……너희들의　누나는@무사히　돌아왔구나。',
        42:'라투니：응……。@지금은　치료를　받고　있어。',
        43:'쿠스하：정말　다행이야……。',
        44:'아라드：하지만……@방심하고　있을　순　없어요。',
        45:'아라드：누나와　함께　살아가기　위해서도、@앞으로의　싸움에서　살아남아야죠。',
        46:'제오라：언니가　회복하면、@다시　함께　싸울　수　있을　거예요。',
        47:'아이비스：그래、제오라……。',
        48:'아이비스：이제　다시는@소중한　사람을　잃지　않도록@모두　함께　힘내자。'}
    n=110;at,size=s.logos[n];b=bytearray(s.data[at:at+size])
    for i,new in changes.items():
        p,old=s.texts(n)[i];raw=encode(new)
        assert decode(raw)==new and all(len(encode(x))<=54 for x in new.split('@'))
        assert old.split('：')[0]==new.split('：')[0]
        if len(raw)<=len(encode(old)):b[p-at:p-at+len(encode(old))]=raw.ljust(len(encode(old)),b'\0')
        else:
            if b[-1]!=0:b.append(0)
            struct.pack_into('<I',b,u32(b,0x54)+i*4,len(b)-u32(b,0x4C));b.extend(raw+b'\0')
        dialogue.append(dict(script=n,text=i,before=old,after=new))
    blobs[n]=b
    for n,b in blobs.items():
        at,size=s.logos[n];assert len(b)<=s.logos[n+1][0]-at
        assert not any(s.data[at+size:at+len(b)])
        for off in (4,0x6C):struct.pack_into('<I',b,off,len(b))
        add(MAP+at,b);add(MAP+0x557F800+12+n*8,struct.pack('<I',len(b)))
    wp=0x5071000;src=wp+u32(s.data,wp+8+110*8);count=u32(s.data,src+40)
    rows=[s.data[src+44+i*336:src+44+(i+1)*336] for i in range(count) if u32(s.data,src+44+i*336+4)==0x24]
    assert len(rows)==1;row=bytearray(rows[0]);struct.pack_into('<I',row,4,0x26);row=bytes(row)
    assert (u32(row,0),u32(row,8),u32(row,32))==(0x4E4,0,0x43A)
    dp=wp+8+127*8;at=wp+u32(s.data,dp);size=u32(s.data,dp+4)
    count=u32(s.data,at+40);assert s.data[at+24:at+32].split(b'\0')[0]==b'01146' and count==228
    assert all(u32(s.data,at+44+i*336+4)!=0x26 for i in range(count))
    data=bytearray(s.data[at:at+size])+row;struct.pack_into('<I',data,40,count+1)
    assert len(data)<=wp+u32(s.data,dp+8)-at and not any(s.data[at+size:at+len(data)])
    add(MAP+at,data);add(MAP+dp+4,struct.pack('<I',len(data)))
    return sorted(edits),row,blobs,dialogue


def ouka_route_fix(apply=False):
    import os,subprocess
    before=sha(ISO);assert before=='0223afbcc85d13d8f0ae36eb55b269f9a2de7ef61babcd292aa52b0f199cceae',before
    edits,row,blobs,dialogue=ouka_route_fix_plan()
    from validate_hidden_rewards import validate_ouka_route_fix
    checks=validate_ouka_route_fix(row,blobs)
    h=hashlib.sha256();pos=0
    with ISO.open('rb') as f:
        for at,a,b in edits:
            while pos<at:
                raw=f.read(min(4<<20,at-pos));assert raw;h.update(raw);pos+=len(raw)
            assert f.read(len(a))==a;h.update(b);pos+=len(a)
        while raw:=f.read(4<<20):h.update(raw)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,dialogue=dialogue,
        edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/ouka_route_fix_manifest.json';journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        assert subprocess.check_output(['powershell','-NoProfile','-Command',"@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True).strip()=='0'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for at,a,b in edits:f.seek(at);assert f.read(len(a))==a;f.seek(at);f.write(b)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for at,a,b in edits:f.seek(at);f.write(a)
                f.flush();os.fsync(f.fileno())
            raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('edits','dialogue')},indent=2))


class NativeHookAsm:
    def __init__(self,start):self.start=start;self.words=[];self.labels={};self.fix=[]
    def emit(self,*w):self.words.extend(w)
    def i(self,op,rs,rt,imm):self.emit(op<<26|rs<<21|rt<<16|(imm&0xffff))
    def label(self,n):self.labels[n]=len(self.words)
    def branch(self,op,rs,rt,label):self.fix.append((len(self.words),label));self.i(op,rs,rt,0)
    def jump(self,pc,link=False):self.emit((3 if link else 2)<<26|pc>>2)
    def move(self,rd,rs):self.emit(rs<<21|rd<<11|0x2d)
    def data(self):
        w=list(self.words)
        for pos,label in self.fix:w[pos]|=(self.labels[label]-pos-1)&0xffff
        return struct.pack('<%dI'%len(w),*w)


def compact_descriptor_initializer():
    """Equivalent startup descriptor writes; no battle/test dependencies."""
    start,end=0x200104,0x200270
    a=NativeHookAsm(start)
    a.i(15,0,8,0x54);a.i(0x39,8,0,-0x74a4)
    a.i(9,8,9,-0x744c);a.i(9,0,10,3)
    a.label('constant_rows')
    for fp,off in ((2,0),(1,4),(0,8)):a.i(0x39,9,fp,off)
    a.i(9,9,9,16);a.i(9,10,10,-1);a.branch(7,10,0,'constant_rows');a.emit(0)
    a.i(15,0,8,0x4a)
    for fp,off in ((5,0x3410),(4,0x3414),(3,0x3418)):a.i(0x31,8,fp,off)
    a.i(15,0,9,0x54)
    for fp,off in ((5,-0x749c),(4,-0x7498),(3,-0x7494)):a.i(0x39,9,fp,off)
    a.i(13,8,8,0x3420);a.i(9,9,9,-0x741c);a.i(9,0,10,5)
    a.label('source_rows')
    for fp,off in ((5,0),(4,4),(3,8)):a.i(0x31,8,fp,off)
    for fp,off in ((5,0),(4,4),(3,8)):a.i(0x39,9,fp,off)
    a.i(9,8,8,16);a.i(9,9,9,16);a.i(9,10,10,-1)
    a.branch(7,10,0,'source_rows');a.emit(0)
    for reg,constant in ((7,0x4a),(6,0x4a),(5,0x4a),(2,0x4a),(4,0x54),(3,0x4a),(10,0x54),(9,0x54),(8,0x54)):
        a.i(15,0,reg,constant)
    a.jump(end);a.emit(0)
    return a.data(),start+len(a.words)*4


def small_enemy_hp_boost(apply=False):
    """Add 10% of base HP below 20000 only for map-hostile actors."""
    import os,subprocess
    elf=lambda pc:0x94880+pc-0x100000
    J=lambda pc:2<<26|pc>>2
    before=sha(ISO)
    assert before=='b7a13214dcc6feb0f9c8f7fee91047b1f0b9eadcbac60b282f07152a27cb83a1',before
    start,end=0x200104,0x200270
    with ISO.open('rb') as f:
        compact,helper=compact_descriptor_initializer()
        # Reuse only the verified equivalent startup prefix, not its TEST retreat hook.
        f.seek(elf(start));old=f.read(end-start)
        a=NativeHookAsm(helper)
        a.i(9,29,29,-0x20);a.i(0x3F,29,31,8)
        a.i(0x2B,29,4,0);a.i(0x2B,29,5,4)
        a.i(0x23,4,2,0x10);a.branch(4,2,0,'done');a.i(0x24,4,3,0x74)
        a.i(12,3,3,7);a.emit(2<<21|3<<16|2<<11|0x21)
        a.i(15,0,3,0x17);a.emit(2<<21|3<<16|2<<11|0x21)
        a.i(0x24,2,2,0x608C);a.i(12,2,2,1)
        a.branch(4,2,0,'done');a.i(0x23,4,6,0x18)
        a.i(0x23,4,4,4);a.i(9,0,5,0x14)
        a.jump(0x1B01D0,True);a.move(7,0)
        a.branch(6,2,0,'done');a.i(10,2,3,20000)
        a.branch(4,3,0,'done');a.i(9,0,3,10)
        a.emit(2<<21|3<<16|0x1A);a.emit(2<<11|0x12)
        a.i(0x23,29,5,4);a.emit(5<<21|2<<16|5<<11|0x21);a.i(0x2B,29,5,4)
        a.label('done');a.i(0x23,29,4,0);a.i(0x23,29,5,4)
        a.i(0x37,29,31,8);a.i(9,29,29,0x20)
        # Replay displaced native frame setup and continue its normal modifiers/caps.
        a.i(9,29,29,-0x30);a.i(0x3F,29,31,0x10)
        a.jump(0x1FE868);a.emit(0)
        assert helper+len(a.data())<=end
        code=(compact[:helper-start]+a.data()).ljust(end-start,b'\0')
        f.seek(elf(0x1FE860));site=f.read(8)
        assert site==struct.pack('<2I',0x27BDFFD0,0xFFBF0010)
    edits=[(elf(start),old,code),(elf(0x1FE860),site,struct.pack('<2I',J(helper),0))]
    edits.sort()
    from validate_hidden_rewards import validate_small_enemy_hp_boost
    checks=validate_small_enemy_hp_boost(edits,helper)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for offset,old,new in edits:
            while cursor<offset:
                b=f.read(min(4<<20,offset-cursor));assert b;h.update(b);cursor+=len(b)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while b:=f.read(4<<20):h.update(b)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Hostile actors only: base HP 1..19999 gains floor(base HP / 10), upgrades and difficulty additions unchanged',
        helper=hex(helper),checks=checks,edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/small_enemy_hp_boost_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for o,x,y in edits:f.seek(o);assert f.read(len(x))==x;f.seek(o);f.write(y)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for o,x,y in edits:f.seek(o);f.write(x)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


def global_weapon_upgrade_discount(apply=False):
    """Reduce weapon cost tiers 1..4 to 80 percent; cheapest tier unchanged."""
    import os,subprocess
    before=sha(ISO)
    assert before=='fd33867136341030272832d5591164d65180bca71355e7f1cc8639410988d3b6',before
    offset=0x94880+0x534E30-0x100000
    with ISO.open('rb') as f:f.seek(offset);old=f.read(5*64)
    values=struct.unpack('<80I',old)
    for tier,step in enumerate((2000,3000,5000,6500,7500)):
        assert values[tier*16:(tier+1)*16]==tuple(step*i for i in range(16))
    assert all(v%5==0 for v in values)
    new=struct.pack('<80I',*(v if i<16 else v*4//5 for i,v in enumerate(values)))
    from validate_hidden_rewards import validate_global_weapon_upgrade_discount
    checks=validate_global_weapon_upgrade_discount(old,new)
    target=hashlib.sha256()
    with ISO.open('rb') as f:
        remaining=offset
        while remaining:
            b=f.read(min(4<<20,remaining));assert b;remaining-=len(b);target.update(b)
        assert f.read(len(old))==old;target.update(new)
        while b:=f.read(4<<20):target.update(b)
    report=dict(source_sha256=before,target_sha256=target.hexdigest(),applied=False,
                feature='Weapon upgrade tiers 1..4 reduced by 20%; cheapest tier0 and all tier assignments preserved',
                checks=checks,edits=[dict(offset=offset,before=old.hex(),after=new.hex())])
    journal=ROOT/'runtime/global_weapon_upgrade_discount_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                f.seek(offset);assert f.read(len(old))==old;f.seek(offset);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                f.seek(offset);f.write(old);f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


def daizengar_upgrade_cost(apply=False):
    """Raise Daizengar weapon cost tier0 to tier1; preserve attack growth."""
    before=sha(ISO)
    assert before=='7dd4b260f47249fba54f25ae76bd10b6b5ec9270e72a30d949bd432a4d0cec2a',before
    targets=set(range(0x30C,0x314))|set(range(0x575,0x57A))
    edits=[];changed=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            for idx in sorted(targets):
                off=base+0x12BF88+idx*36
                f.seek(off);record=f.read(36)
                if not struct.unpack_from('<H',record,8)[0]:continue
                assert record[3]&0x3F==0,(hex(idx),record[3])
                edits.append((off+3,record[3:4],bytes([record[3]|1])))
                if base==0x5DA000:changed.append(idx)
    from validate_hidden_rewards import validate_daizengar_upgrade_cost
    checks=validate_daizengar_upgrade_cost(edits,changed)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/daizengar_upgrade_cost_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import os,subprocess
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def weapon_consumption(apply=False):
    """Requested weapon EN and morale reductions; all other fields unchanged."""
    before=sha(ISO)
    assert before=='41cd9c59f56db24fc9ae89709da27dc0f2c388253c08eff74ba514f986271b53',before
    edits=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            for idx,field,old,new in ((0x312,0x1A,bytes([40]),bytes([20])),(0x313,0x1A,bytes([50]),bytes([30])),(0x2A3,0x1B,bytes([125]),bytes([115])),(0x1D5,0x1A,bytes([70]),bytes([60])),(0x1D9,0x1A,bytes([50]),bytes([40]))):
                off=base+0x12BF88+idx*36+field
                f.seek(off);assert f.read(1)==old
                edits.append((off,old,new))
    from validate_hidden_rewards import validate_weapon_consumption
    checks=validate_weapon_consumption(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/weapon_consumption_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        import os,subprocess
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

OUKA_SURVIVAL_TEXT = {
    109: {
        760:'오우카：도망치게　하지　않아……！@리미터　해제……！',
        761:'아기라：너、너　이년！@그　몸으로　출력을　올릴　셈이냐！？',
        762:'오우카：머신셀도　남김없이@태워버리면……재생할　수　없겠지！',
        764:'오우카：아라드……제오라……라트……。@너희들을　다시는　저　사람의@인형으로　만들지　않겠어……！',
        767:'아라드：혼자　떠안지　마！@우리도　함께　싸우겠어！！',
        768:'오우카：안돼、가까이　오지　마！！',
        770:'오우카：머신셀이……@너희들까지　삼키고　말아……！',
        771:'제오라：그럼　여기서　엄호할게요！',
        772:'오우카：게임・시스템　때문에……@몸이　말을　듣지　않아……。@이대로는……',
        773:'아라드：누나、포기하지　마！！',
        775:'오우카：놓치지　않겠어요……！@여기서　끝을　내겠습니다！',
        776:'라투니：언니、무장에　출력을　모아！',
        777:'오우카：……라트……。@그래、아직　할　수　있어……！',
        778:'오우카：아라드……도와줘……',
        779:'아라드：맡겨줘！！',
        780:'오우카：제오라……엄호를……',
        781:'제오라：네、언니！！',
        782:'오우카：너희들과……@함께　돌아가기　위해서……！',
        783:'오우카：이　일격에……@남은　출력을　전부　쏟겠어……！',
        785:'아라드：지금이야！！',
        786:'제오라：아라드、언니를　부탁해！！',
        787:'아라드：누나、기체를　잡았어！！',
        788:'라투니：언니、대답해……！',
        789:'라투니：생체　반응……있어！',
        790:'라투니：살아있어……언니가……！',
        791:'아라드：쿠로가네로　데려갈게！！',
        792:'샤인：의료반에　연락하겠어요！',
        845:'에이타：다이젠가가　미귀환……！@오우카는　의료반에　인계했습니다！',
        881:'라다：오우카는　고비를　넘겼어。@하지만　쿠엘보는……@돌아오지　못했어。',
        882:'제오라：언니가……살았군요……！',
        883:'라다：라피에사쥬도　회수했어。@위험한　시스템은　제거하고、@오우카는　치료를　계속할　거야。',
        884:'아라드：세로　박사님……。',
        885:'아라드：……누나를　구해주셨는데……。',
        886:'제오라：……박사님……。',
        887:'아라드：누나의　기억을……@우리의　누나를　되찾아주셨는데……。',
        889:'아라드：제오라……。@이번에는　누나와　함께　살아가자。',
        890:'아라드：박사님이　지켜준　목숨이야。@누구도　쉽게　버려서는　안돼。',
        892:'아라드：이제　누나　혼자@모든　걸　짊어지게　하지　말자。',
        893:'아라드：우리、모두　살아남는　거야。',
        898:'라다（쿠엘보……오우카는　살았어요……）',
        899:'라다（이　애들이　앞으로　살아갈　날들을@　지켜보겠어요……。@　당신이　바랐던　대로……）',
        902:'샤인：의무실에　다녀온　뒤、@잠시　혼자　있고　싶다며……',
        905:'마이：많이　놀랐을　거야……。',
        906:'샤인：네……。@줄곧　언니를　잃을까　걱정했으니까요。',
        909:'마이：나도……알　것　같아。@아야가　그렇게　다쳤다면……',
        921:'라투니：언니를……@또　잃는　줄　알았어……。',
        922:'라투니：아라드와　제오라가……@류세이들이　도와주지　않았다면……',
        923:'라투니：나　혼자서는……',
        924:'류세이：너도　언니를　구한　거야。',
        926:'류세이：너희　목소리가@그　사람의　기억을　되찾아준　거야。',
        927:'류세이：그리고　이번엔@모두　함께　돌아왔어。@그걸　잊지　마。',
        930:'라투니：응……。@앞으로는　언니와　함께　살아갈래。',
        931:'라투니：추억뿐만　아니라……@앞으로의　날들도　함께……。',
    },
    151: {
        587:'아라드：……혼자서는　안돼。@오우카　누나도　모두　힘을　합쳐서@구했어。　이번에도　함께　구하자。',
        742:'라투니：오우카　언니와@함께　되찾은　날들을……。@소중한　사람들과의　기억을　지우지　마。',
    },
}

def ouka_survival(apply=False):
    """Preserve the memory recovery; replace the later sacrifice with rescue."""
    from ogs_korean_codec import encode
    import re,os,subprocess
    expected='8499be55449d6026831df7697185ba12e5009492ed584b21b645d3dafe7ad3fb'
    before=sha(ISO);assert before==expected,('Changed ISO; audit first',before)
    s=Scripts();edits=[];decisions=[];blobs={}
    def add(off,old,new):
        assert len(old)==len(new)
        with ISO.open('rb') as f:f.seek(off);assert f.read(len(old))==old,hex(off)
        if old!=new:edits.append((off,old,new))
    for n,changes in OUKA_SURVIVAL_TEXT.items():
        at,size=s.logos[n];b=bytearray(s.data[at:at+size]);ts=s.texts(n)
        for i,new in changes.items():
            p,old_text=ts[i];old=encode(old_text);raw=encode(new)
            assert b[p-at:p-at+len(old)]==old
            assert old_text.split('：')[0].split('（')[0]==new.split('：')[0].split('（')[0]
            assert decode(raw)==new and new.count('@')<=2
            assert all(len(encode(line))<=54 for line in new.split('@')),(n,i,new)
            assert not any(ord(c)<128 and c!='@' for c in new)
            assert not re.search('[\u3040-\u30fa\u4e00-\u9fff]',new)
            if len(raw)<=len(old):b[p-at:p-at+len(old)]=raw.ljust(len(old),b'\0')
            else:
                # Original LOGO may end without its final NUL (sector padding
                # supplies it). Preserve that terminator before appending.
                if b[-1]!=0:b.append(0)
                struct.pack_into('<I',b,u32(b,0x54)+i*4,len(b)-u32(b,0x4C))
                b.extend(raw+b'\0')
            decisions.append(dict(script=n,text=i,before=old_text,after=new))
        blobs[n]=b
    b=blobs[109];rs=s.records(109);co=u32(b,0x2C)
    # Keep the blast and Agilla's removal, but aim the effects at Agilla.
    # Reuse a movement/wait pair already used by this scene to withdraw Ouka
    # toward the Kurogane. Do not execute Ouka's original death command.
    for i in [2147,2148,2149,2154]:
        r=list(rs[i][1]);assert r[3]==0x43A;r[3]=0x415
        struct.pack_into('<24I',b,co+i*96,*r)
    assert rs[2163][1][:5]==(0x81,DEAD,0x100A5,0x43A,0)
    retreat=list(rs[2111][1]);assert retreat[4]==0x43A and retreat[9]==0x415
    retreat[9]=0x471
    struct.pack_into('<24I',b,co+2163*96,*retreat)
    assert rs[2164][1][:6]==(0x9D,DEAD,0x100A5,0x43A,1,0x3E)
    wait=list(rs[2112][1]);assert wait[3]==0x43A and wait[5]==0x415
    wait[5]=0x471
    struct.pack_into('<24I',b,co+2164*96,*wait)
    assert rs[2165][1][:5]==(0x81,DEAD,0x100A5,0x415,0x3F)
    insert=2572;pos=co+insert*96
    assert rs[insert][1][:4]==(0x9C,DEAD,0x22,0)
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8B,0x8C):
            for j in ([6,7] if r[0]==0x8B else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j]
    # Text-command lookup contains combined actor/main command indices.
    # No text command follows this final clear insertion.
    assert max(u32(b,u32(b,0x3C)+i*4) for i in range(u32(b,0x38)))<insert+u32(b,0x20)
    b[pos:pos]=struct.pack('<24I',*command(0x5E,0x24))
    struct.pack_into('<I',b,0x28,u32(b,0x28)+1)
    for off in [0x34,0x3C,0x44,0x4C,0x54,0x5C]:
        assert u32(b,off)>=pos;struct.pack_into('<I',b,off,u32(b,off)+96)
    for n,b in blobs.items():
        at,size=s.logos[n]
        cap=(s.logos[n+1][0]-at) if n+1<len(s.logos) else (size+2047)//2048*2048
        assert len(b)<=cap,(n,len(b),cap)
        assert not any(s.data[at+size:at+len(b)])
        for off in [4,0x6C]:struct.pack_into('<I',b,off,len(b))
        add(MAP+at,s.data[at:at+len(b)],bytes(b))
        add(MAP+0x557F800+12+n*8,struct.pack('<I',size),struct.pack('<I',len(b)))
    # A new reserved group uses the original recovered ally row, invoked by
    # native roster-grant opcode 5E after all existing post-clear setup.
    wp=0x5071000;dp=wp+8+110*8;off,size=struct.unpack_from('<II',s.data,dp);at=wp+off
    count=u32(s.data,at+0x28);assert count==202 and size==44+count*336
    old=s.data[at:at+size];row=bytearray(old[44:380])
    assert struct.unpack_from('<3I',row)==(0x4E4,0xE,0) and u32(row,0x20)==0x43A
    assert all(u32(old,44+j*336+4)!=0x24 for j in range(count))
    struct.pack_into('<I',row,4,0x24)
    ub=bytearray(old);struct.pack_into('<I',ub,0x28,count+1);ub.extend(row)
    assert len(ub)<=wp+u32(s.data,dp+8)-at
    assert not any(s.data[at+size:at+len(ub)])
    add(MAP+at,s.data[at:at+len(ub)],bytes(ub))
    add(MAP+dp+4,struct.pack('<I',size),struct.pack('<I',len(ub)))
    for base in [0x5DA000,0x83F000]:
        add(base+0x13B490+96*148+0x12,b'\0\0',b'\1\0')
        add(base+0x11F8A4+295*100+0x22,b'\0\0',b'\1\0')
    from validate_hidden_rewards import validate_ouka
    checks=validate_ouka(row,blobs,s,edits)
    edits.sort()
    for x,y in zip(edits,edits[1:]):assert x[0]+len(x[1])<=y[0]
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        checks=checks,dialogue=decisions,
        edits=[dict(offset=o,before=x.hex(),after=y.hex()) for o,x,y in edits])
    journal=ROOT/'runtime/ouka_survival_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('edits','dialogue')},ensure_ascii=False,indent=2))

def daizengar_combined_arsenal(apply=False):
    """Basic keeps three built-ins; sword form gains those same weapons."""
    import os,subprocess
    before=sha(ISO)
    assert before=='5bc30bb635ea895a04a3e2c1f713f91c54f78cf802d1d48a33f53bd77aeba1f1',before
    edits=[];builtins=[0xA6A,0xA6B,0xA6C];swords=list(range(0xA65,0xA6A))
    merged=builtins+swords
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            f.seek(base+0x11F8A4+0xD1*100+0x24)
            assert list(struct.unpack('<16H',f.read(32)))==builtins+[0xFFFF]*13
            at=base+0x11F8A4+0xD0*100+0x24;f.seek(at);old=f.read(32)
            assert list(struct.unpack('<16H',old))==swords+[0xFFFF]*11
            new=struct.pack('<16H',*(merged+[0xFFFF]*8))
            edits.append((at,old,new))
    from validate_hidden_rewards import validate_daizengar_combined_arsenal
    checks=validate_daizengar_combined_arsenal(edits)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for at,old,new in edits:
            while cursor<at:
                chunk=f.read(min(4<<20,at-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Basic: built-ins only; Zankantou: three built-ins plus four sword attacks and Tornado Zankantou',
        checks=checks,edits=[dict(offset=at,before=old.hex(),after=new.hex()) for at,old,new in edits])
    journal=ROOT/'runtime/daizengar_combined_arsenal_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for at,old,new in edits:
                    f.seek(at);assert f.read(len(old))==old;f.seek(at);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for at,old,new in edits:f.seek(at);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def daizengar_unified(apply=False):
    """One full arsenal, no refit; old Basic saves resolve to the same master."""
    import os,subprocess
    before=sha(ISO)
    assert before=='994f35f4197318ce3f06b4953dae3ae44130d56621e19d470f90ad6bdf24e311',before
    overlay={}
    with ISO.open('rb') as f:
        def change(at,expected,replacement):
            assert len(expected)==len(replacement)
            f.seek(at);raw=f.read(len(expected))
            actual=bytes(overlay.get(at+i,value) for i,value in enumerate(raw))
            assert actual==expected,('Changed refit bytes; audit first',hex(at))
            overlay.update((at+i,value) for i,value in enumerate(replacement))
        # Reverse only the guarded Daizengar refit additions, newest first.
        for name in ('daizengar_refit_visibility_manifest.json',
                     'daizengar_refit_labels_manifest.json','daizengar_refit_manifest.json'):
            m=json.loads((ROOT/'runtime'/name).read_text(encoding='utf-8'));assert m['applied']
            for e in reversed(m['edits']):
                change(e['offset'],bytes.fromhex(e['after']),bytes.fromhex(e['before']))
        for base in (0x5DA000,0x83F000):
            # Keep the persistent raw key of an old Basic-form save intact;
            # its lookup now resolves to the same complete Daizengar master.
            change(base+0x11E898+0x49A*2,b'\xd1\x00',b'\xd0\x00')
        addresses=sorted(overlay);groups=[]
        for at in addresses:
            if not groups or at!=groups[-1][-1]+1:groups.append([])
            groups[-1].append(at)
        edits=[]
        for group in groups:
            at=group[0];f.seek(at);old=f.read(len(group));new=bytes(overlay[p] for p in group)
            if old!=new:edits.append((at,old,new))
    from validate_hidden_rewards import validate_daizengar_unified
    checks=validate_daizengar_unified(edits)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for at,old,new in edits:
            while cursor<at:
                chunk=f.read(min(4<<20,at-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Unified Daizengar arsenal, no refit, existing Basic save compatibility',
        checks=checks,edits=[dict(offset=at,before=old.hex(),after=new.hex()) for at,old,new in edits])
    journal=ROOT/'runtime/daizengar_unified_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for at,old,new in edits:
                    f.seek(at);assert f.read(len(old))==old;f.seek(at);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for at,old,new in edits:f.seek(at);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def daizengar_animation_links(apply=False):
    """Fix the renderer's (unit animation bank, weapon motion) lookup."""
    import os,subprocess
    before=sha(ISO)
    assert before=='37a78a5ad4a632e4ac8734bd56e3b4bc3883a9d552f1b8d4368f451786e17385',before
    edits=[];builtin_keys=(0xA6A,0xA6B,0xA6C)
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            f.seek(base);master=f.read(0x190000)
            consumers=[]
            for unit in range(427):
                keys=struct.unpack_from('<16H',master,0x11F8A4+unit*100+0x24)
                if any(k!=0xFFFF and struct.unpack_from('<H',master,0x129F7C+k*2)[0] in (0x311,0x312,0x313) for k in keys):
                    consumers.append(unit)
            assert consumers==[0xD0,0xD1],consumers
            for i,key in enumerate(builtin_keys):
                idx=struct.unpack_from('<H',master,0x129F7C+key*2)[0];assert idx==0x311+i
                off=base+0x12BF88+idx*36+0x21
                f.seek(off);assert f.read(1)==bytes([i])
                edits.append((off,bytes([i]),bytes([5+i])))
        # Wpbb offsets are relative to their directory, not the LICE file.
        battle_wp=0x2511F800+0x800;f.seek(battle_wp);assert f.read(8)==b'Wpbb'+struct.pack('<I',12)
        f.seek(battle_wp+8+7*8);entry,size=struct.unpack('<II',f.read(8))
        nested=battle_wp+entry+0x800;f.seek(nested);assert f.read(8)==b'Wpbb'+struct.pack('<I',1)
        child,length=struct.unpack('<II',f.read(8));table=nested+child
        assert length==300*144
        f.seek(table);data=f.read(length)
        assert u32(data,108*144)==u32(data,179*144)==26
        assert struct.unpack_from('<5H',data,108*144+4)==tuple(range(0x783,0x788))
        original=bytes(data[179*144+4:179*144+10]);assert original==struct.pack('<3H',0xC19,0xC1A,0xC1B)
        for bank in (108,179):
            off=table+bank*144+4+5*2
            assert data[bank*144+14:bank*144+20]==b'\xff'*6
            edits.append((off,b'\xff'*6,original))
    edits.sort()
    from validate_hidden_rewards import validate_daizengar_animation_links
    checks=validate_daizengar_animation_links(edits,table,data)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Daizengar built-in attacks resolve their original separated-form animation assets',
        checks=checks,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/daizengar_animation_links_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def daizengar_arsenal_balance(apply=False):
    """Agreed unified-arsenal costs/power; penetration only on sword attacks."""
    import os,subprocess
    before=sha(ISO)
    assert before=='461d74f3794a3b4cf8cadb6c8d92c951158f0e99ef87c1faa5ea03304e8c8a51',before
    edits=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            f.seek(base);blob=f.read(0x190000)
            for idx in range(1628):
                rel=0x12BF88+idx*36;old=blob[rel:rel+36];new=bytearray(old)
                if idx==0x311:struct.pack_into('<H',new,8,4000)
                if idx==0x313:
                    struct.pack_into('<H',new,8,5000);new[0x1A]=20;new[0x1B]=110
                if idx in (0x30E,0x577):new[0x1A]=30
                if idx in (0x30F,0x578):new[0x1A]=50
                if idx in (0x311,0x312,0x313):new[0x15]&=0xCF
                if idx in set(range(0x30C,0x311))|set(range(0x575,0x57A)):
                    assert (old[0x15]>>4)&3==2
                if idx==0x312:
                    assert struct.unpack_from('<H',old,8)[0]==5200 and old[0x1A]==20
                    assert old[0x14]&0x80 and not(old[0x15]&1)
                for j,(a,b) in enumerate(zip(old,new)):
                    if a!=b:edits.append((base+rel+j,bytes([a]),bytes([b])))
    from validate_hidden_rewards import validate_daizengar_arsenal_balance
    checks=validate_daizengar_arsenal_balance(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/daizengar_arsenal_balance_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def axel_spirits(apply=False):
    """Axel only: Iron Wall 20, twin Soul 50, Awakening 50."""
    import os,subprocess
    before=sha(ISO)
    assert before=='c3a1525f4754ec88dd5812cb52e3c563a30558ee50e6b43a212b881e94924753',before
    edits=[]
    for base in (0x5DA000,0x83F000):
        with ISO.open('rb') as f:
            f.seek(base);blob=f.read(0x190000)
        assert blob[0x13B484:0x13B488]==b'Plot'
        for idx in (53,54):
            p=0x13B490+idx*0x94;r=blob[p:p+0x94]
            assert struct.unpack_from('<H',r,0x48)[0]==0x14
            assert r[0x6C:0x80]==bytes([7,4,17,2,21,10,10,10,45,40,15,55,1,1,8,20,23,31,35,40])
            for rel,old,new in ((0x6D,4,5),(0x73,10,20),(0x77,55,50),(0x7E,35,37),(0x7F,40,50)):
                edits.append((base+p+rel,bytes([old]),bytes([new])))
    from validate_hidden_rewards import validate_axel_spirits
    checks=validate_axel_spirits(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Axel Iron Wall SP20, twin Soul SP50, Awakening SP50; levels unchanged',
        checks=checks,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/axel_spirits_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
            assert validate_axel_spirits([],applied=True)==checks
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def seolla_spirits(apply=False):
    """Seolla: Snipe -> Flash (10), Iron Wall -> Accel (10)."""
    import os,subprocess
    before=sha(ISO)
    assert before=='91ba9d6b623a2e74eae3a4bbbc4754c34e0ce6e973a05b7be4327fcc6d24389e',before
    edits=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            f.seek(base);blob=f.read(0x190000)
            assert blob[0x13B484:0x13B488]==b'Plot'
            for idx in (159,160,370):
                p=0x13B490+idx*0x94;r=blob[p:p+0x94]
                assert r[0x6C:0x80]==bytes([6,5,7,20,2,24,15,30,10,10,35,60,1,1,7,12,23,35,32,40])
                for rel,old,new in ((0x6D,5,9),(0x6F,20,3),(0x73,30,10)):
                    edits.append((base+p+rel,bytes([old]),bytes([new])))
    from validate_hidden_rewards import validate_seolla_spirits
    checks=validate_seolla_spirits(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Seolla Snipe -> Flash SP10, Iron Wall -> Accel SP10; levels and skills unchanged',
        checks=checks,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/seolla_spirits_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
            assert validate_seolla_spirits([],applied=True)==checks
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def battle_rewards(apply=False):
    """Final defeat rewards: PP x2 per recipient, funds x6/5 after bonuses."""
    import os,subprocess
    before=sha(ISO)
    assert before=='9548f41307d8d3af6cceeabafe672d905b77c0055ddc04dbc3141e8982b9b218',before
    def elf(pc):return 0x94880+pc-0x100000
    # Retired refit-label cave is zero and has no remaining references.
    cave=0x499D38
    code=struct.pack('<13I',0x00101040,0x00501021,0x00021040,0x24030005,
        0x0043001B,0x00008012,0x8FA2011C,0x10400003,0,
        0x08000000|(0x31D7E4>>2),0,0x08000000|(0x31D7F8>>2),0)
    edits=[(elf(cave),bytes(len(code)),code),
        (elf(0x31D7D8),struct.pack('<2I',0x8FA2011C,0x10400006),struct.pack('<2I',0x08000000|(cave>>2),0)),
        # Load accumulator in the branch delay; double only the finalized PP
        # amount after all split/skill/minimum rules, before adding to totals.
        (elf(0x31DA6C),bytes(4),struct.pack('<I',0x8E030244)),
        (elf(0x31DA78),struct.pack('<I',0x8E030244),struct.pack('<I',0x00118840))]
    with ISO.open('rb') as f:
        for off,old,new in edits:
            f.seek(off);assert f.read(len(old))==old,hex(off)
    from validate_hidden_rewards import validate_battle_rewards
    checks=validate_battle_rewards(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Defeat reward PP x2, funds x1.2; after native bonuses/splits; event grants unchanged',
        checks=checks,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/battle_rewards_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
            assert validate_battle_rewards([],applied=True)==checks
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


def enemy_strength_plan():
    """Enemy combat totals +5; enemy UNTD body/weapon base upgrades +1.

    Repack twelve redundant callback descriptor initializations into an
    equivalent loop. Helpers occupy only the reclaimed instruction bytes.
    No text, master pilot record, save or scenario record is rewritten.
    """
    def elf(pc):return 0x94880+pc-0x100000
    def I(op,rs,rt,imm):return op<<26|rs<<21|rt<<16|(imm&0xffff)
    def R(rs,rt,rd,fn):return rs<<21|rt<<16|rd<<11|fn
    def J(pc,link=False):return (3 if link else 2)<<26|pc>>2
    start,end=0x2002A8,0x2003C4
    # t0/t1/t2 already equal 0x540000. Preserve all original final GPR/FPR
    # values and the exact twelve x three descriptor stores.
    init=[I(9,8,10,-0x73ac),I(9,0,9,12),
          I(0x39,10,2,0),I(0x39,10,1,4),I(0x39,10,0,8),
          I(9,10,10,16),I(9,9,9,-1),I(7,9,0,-6),0,
          I(15,0,10,0x54),I(15,0,9,0x54),I(15,0,5,0x54),J(end),0]
    pilot=start+len(init)*4
    # Same relation bit as native 1FADD0 -> 191540: enemy to player side 0.
    # s2 is the displaced move s2,a1, the callee's input stat accumulator.
    stats=[I(0x23,4,2,0x10),R(5,0,18,0x2d),I(4,2,0,9),I(0x24,4,3,0x74),
           I(12,3,3,7),R(2,3,2,0x21),I(15,0,3,0x17),R(2,3,2,0x21),
           I(0x24,2,2,0x608c),I(12,2,2,1),I(0x15,2,0,1),I(9,18,18,5),
           0x03e00008,0]
    spawn=pilot+len(stats)*4
    # Default hostile factions are 2/3/4 (native 18F9E0 defaults). Modify
    # only the copied UNTD six difficulty fields, before native cap/store.
    upgrades=[I(0x23,29,3,0xa8),I(9,3,2,-2),I(11,2,2,3),I(4,2,0,8),
              I(9,29,4,0xd8),I(9,0,5,6),I(0x23,4,2,0),I(9,2,2,1),
              I(0x2b,4,2,0),I(9,5,5,-1),I(7,5,0,-5),I(9,4,4,4),
              0x03e00008,I(10,3,1,6)]
    code=struct.pack('<%dI'%(len(init)+len(stats)+len(upgrades)),*(init+stats+upgrades))
    assert start+len(code)<=end
    code+=bytes(end-start-len(code))
    with ISO.open('rb') as f:
        f.seek(elf(start));old=f.read(end-start)
        # Fail closed: all replaced instructions must have the known store/
        # address-only shape. Native init equivalence is checked separately.
        assert u32(old,0)==0xE5428C54 and u32(old,len(old)-4)==0xE5008D0C
        edits=[(elf(start),old,code)]
        for fn in [0x1F8850,0x1F86C0,0x1F8530,0x1F83A0,0x1F8210,0x1F8080]:
            f.seek(elf(fn+0x18));a=f.read(8)
            assert a==struct.pack('<2I',0x00A0902D,0x7FB00000),(hex(fn),a.hex())
            edits.append((elf(fn+0x18),a[:4],struct.pack('<I',J(pilot,True))))
        f.seek(elf(0x1D5A08));a=f.read(8)
        assert a==struct.pack('<2I',0x8FA300A8,0x28610006),a.hex()
        edits.append((elf(0x1D5A08),a,struct.pack('<2I',J(spawn,True),0)))
    return edits,dict(pilot_helper=pilot,spawn_helper=spawn,initializer_start=start,initializer_end=end)


def enemy_strength(apply=False):
    import os,subprocess
    before=sha(ISO)
    assert before=='4b79877f3dd05cdcc89fddd8e916691cb2026f81393b1c3455569de92a4e69a1',before
    edits,layout=enemy_strength_plan()
    from validate_hidden_rewards import validate_enemy_strength
    checks=validate_enemy_strength(edits,layout)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,old,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(old))==old;h.update(new);cursor+=len(old)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Hostile pilot six combat totals +5; spawn enemy body/weapon upgrades +1 at each difficulty; native caps retained',
        layout=layout,checks=checks,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/enemy_strength_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,old,new in edits:
                    f.seek(off);assert f.read(len(old))==old;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
            assert validate_enemy_strength([],layout,applied=True)==checks
        except Exception:
            with ISO.open('r+b') as f:
                for off,old,new in edits:f.seek(off);f.write(old)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


def mumei_fallback(apply=False):
    """OG2 episode 6 clear: native grant is a no-op if alias 600 is owned."""
    import os,subprocess
    before=sha(ISO)
    assert before=='aa4aaa2fa4ab136eba8904e7270c6623a3b0b22147c0bd96be5630c33cc0dc77',before
    s=Scripts();n=74;insert=532;at,size=s.logos[n];rs=s.records(n)
    assert len(rs)==535 and rs[insert][1][:4]==(0x9c,DEAD,2,0)
    assert [r[1][0] for r in rs[526:532]]==[0x5f]*3+[0x5b]*3
    old=s.data[at:at+size];b=bytearray(old);pos=u32(b,0x2c)+insert*96
    # Table entries use record indexes including the per-script base (0x40).
    lookup=[u32(b,u32(b,0x3c)+i*4) for i in range(u32(b,0x38))]
    assert max(lookup)<insert+u32(b,0x20)
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8b,0x8c):
            for j in ([6,7] if r[0]==0x8b else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j],(i,j)
    b[pos:pos]=struct.pack('<24I',*command(0x5a,0x600))
    for off in (4,0x6c):struct.pack_into('<I',b,off,u32(b,off)+96)
    struct.pack_into('<I',b,0x28,len(rs)+1)
    for off in (0x34,0x3c,0x44,0x4c,0x54,0x5c):
        assert u32(b,off)>=pos;struct.pack_into('<I',b,off,u32(b,off)+96)
    assert len(b)<=s.logos[n+1][0]-at and not any(s.data[at+size:at+len(b)])
    restored=bytearray(b);del restored[pos:pos+96];restored[:0x70]=old[:0x70];assert restored==old
    edits=[(MAP+at,s.data[at:at+len(b)],bytes(b)),
           (MAP+0x557f800+12+n*8,struct.pack('<I',size),struct.pack('<I',len(b)))]
    from validate_hidden_rewards import validate_mumei_fallback
    checks=validate_mumei_fallback(edits)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,a,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(a))==a;h.update(new);cursor+=len(a)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='OG2 episode 6 clear missing-Mumei fallback, native duplicate check; episode 5 grant preserved',
        checks=checks,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/mumei_fallback_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,a,new in edits:
                    f.seek(off);assert f.read(len(a))==a;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
            assert validate_mumei_fallback([],applied=True)==checks
        except Exception:
            with ISO.open('r+b') as f:
                for off,a,new in edits:f.seek(off);f.write(a)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


WODAN_SURVIVAL_TEXT={
    109:{
        682:'워단：아직　움직일　수　있다、@메이거스……！',
        687:'워단：이제는……@Ｗ１５가　아닌……@워단・유밀로서　살겠다……',
        825:'워단：나의　모든　것을　걸고、@이　일격으로　길을　연다！！',
        827:'워단：젠가……소피아를　구해라！@이　싸움에서　살아남는다면、@나의　검을　너희에게　맡기겠다……！',
        830:'젠가：워단！！@네놈의　검은　아직　필요하다！@함께　돌아가는　거다！！',
        874:'젠가：살아있습니다。@슬레이드게르밀과　함께　회수해@지금은　함내에서　회복　중입니다。',
        876:'젠가：그　남자는　당신을　지켰습니다。@자신의　의지로……',
        878:'젠가：그는　우리와　함께　싸우며@앞으로도　당신을　지키겠다고　했습니다。',
        879:'소피아：그렇군요……。@부디、그를　잘　부탁드립니다。',
    },
    113:{38:'레몬：Ｗ１５도　Ｗ１６도……@내가　바라던　존재로　변해갔지。@워단은　자기　길을　찾았고……'},
    114:{216:'젠가：자신의　의지와　싸울　이유를@빼앗긴　존재를……두　번　다시는！'},
}


def wodan_survival_plan(source=ISO):
    """Last duel unchanged; rescue Wodan and grant him on existing alias 601."""
    from ogs_korean_codec import encode
    import re
    s=Scripts(source);edits=[];blobs={};dialogue=[]
    for n,changes in WODAN_SURVIVAL_TEXT.items():
        assert not set(changes)&set(OUKA_SURVIVAL_TEXT.get(n,{})),('Ouka dialogue overlap',n)
        at,size=s.logos[n];b=bytearray(s.data[at:at+size]);ts=s.texts(n)
        for i,text in changes.items():
            p,old=ts[i];a=encode(old);new=encode(text)
            assert text.split('：')[0]==old.split('：')[0]
            assert decode(new)==text and text.count('@')<=2
            assert all(len(encode(line))<=54 for line in text.split('@')),(n,i,text)
            assert not any(ord(c)<128 and c!='@' for c in text)
            assert not re.search('[\u3040-\u30fa\u4e00-\u9fff]',text)
            assert b[p-at:p-at+len(a)]==a
            if len(new)<=len(a):b[p-at:p-at+len(a)]=new.ljust(len(a),b'\0')
            else:
                if b[-1]!=0:b.append(0)
                struct.pack_into('<I',b,u32(b,0x54)+i*4,len(b)-u32(b,0x4c))
                b.extend(new+b'\0')
            dialogue.append(dict(script=n,text=i,before=old,after=text))
        blobs[n]=b
    b=blobs[109];rs=s.records(109);co=u32(b,0x2c)
    assert rs[2300][1][:5]==(0x81,DEAD,0x100a5,0x42d,0xc9)
    assert rs[2303][1][:3]==(0x63,DEAD,0xd)
    # Reuse this scene's asynchronous retreat movement. No later command
    # reads Wodan's map position; preserve the original event-selector command
    # and all subsequent dialogue/waits while the retreat runs.
    move=list(rs[2111][1]);assert move[4]==0x43a and move[9]==0x415
    move[4]=0x42d;move[9]=0x471
    struct.pack_into('<24I',b,co+2300*96,*move)
    # A fresh ally alias prevents original enemy-actor cleanup from deleting
    # the recruit. Reuse the existing owned robot, without resetting upgrades.
    insert=next(i for i,(a,r) in enumerate(rs) if i>2500 and r[:4]==(0x9c,DEAD,0x22,0))
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8b,0x8c):
            for j in ([6,7] if r[0]==0x8b else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j]
    assert max(u32(b,u32(b,0x3c)+i*4) for i in range(u32(b,0x38)))<insert+u32(b,0x20)
    pos=co+insert*96;b[pos:pos]=struct.pack('<24I',*command(0x5e,0x25))
    struct.pack_into('<I',b,0x28,u32(b,0x28)+1)
    for off in (0x34,0x3c,0x44,0x4c,0x54,0x5c):struct.pack_into('<I',b,off,u32(b,off)+96)
    for n,b in blobs.items():
        at,size=s.logos[n];cap=s.logos[n+1][0]-at
        assert len(b)<=cap and not any(s.data[at+size:at+len(b)]),(n,len(b),cap)
        for off in (4,0x6c):struct.pack_into('<I',b,off,len(b))
        edits.extend([(MAP+at,s.data[at:at+len(b)],bytes(b)),
            (MAP+0x557f800+12+n*8,struct.pack('<I',size),struct.pack('<I',len(b)))])
    wp=0x5071000;dp=wp+8+110*8;off,size=struct.unpack_from('<II',s.data,dp);at=wp+off
    count=u32(s.data,at+40);assert count in (202,203) and size==44+count*336
    original=s.data[at:at+size];row=bytearray(original[44+138*336:44+139*336])
    assert struct.unpack_from('<3I',row)==(0x491,0x11,0) and u32(row,0x20)==0x42d
    assert all(u32(original,44+j*336+4)!=0x25 for j in range(count))
    for index,value in [(0,0x601),(1,0x25),(4,0),(5,0),(6,0),(7,1),(8,0x602)]:struct.pack_into('<I',row,index*4,value)
    ub=bytearray(original);struct.pack_into('<I',ub,40,count+1);ub.extend(row)
    assert len(ub)<=wp+u32(s.data,dp+8)-at and not any(s.data[at+size:at+len(ub)])
    edits.extend([(MAP+at,s.data[at:at+len(ub)],bytes(ub)),(MAP+dp+4,struct.pack('<I',size),struct.pack('<I',len(ub)))])
    for base in (0x5da000,0x83f000):
        with source.open('rb') as f:f.seek(base);master=f.read(0x190000)
        assert struct.unpack_from('<H',master,0x13a484+0x42d*2)[0]==80
        assert struct.unpack_from('<H',master,0x11e898+0x601*2)[0]==0xc8
        assert struct.unpack_from('<H',master,0x13a484+0x602*2)[0]==0xffff
        assert master[0x13b490+80*148+18:0x13b490+80*148+20]==b'\0\0'
        edits.extend([(base+0x13a484+0x602*2,b'\xff\xff',struct.pack('<H',80)),
            (base+0x13b490+80*148+18,b'\0\0',b'\1\0')])
    # Reclaim a separate descriptor-initialization block, outside the enemy
    # option's code range. Narrow wrappers reuse ONLY our owned unit/pilot keys.
    # Every ordinary unit and pilot allocation tails to the original routine.
    def I(op,rs,rt,imm):return op<<26|rs<<21|rt<<16|(imm&0xffff)
    def J(pc,link=False):return (3 if link else 2)<<26|pc>>2
    start,end=0x2003f4,0x200514
    init=[I(9,8,10,-0x72cc),I(9,0,9,12),I(0x39,10,2,0),I(0x39,10,1,4),I(0x39,10,0,8),
          I(9,10,10,16),I(9,9,9,-1),I(7,9,0,-6),0,I(15,0,10,0x54),I(15,0,9,0x54),I(15,0,8,0x54),J(end),0]
    unit=start+len(init)*4
    def wrapper(key,lookup,original,pilot=False):
        return [I(9,0,2,key),I(5,5,2,14),0,I(9,29,29,-0x20),I(0x3f,29,31,0x10),I(0x3f,29,4,0),
            J(lookup,True),I(9,0,6,1) if pilot else I(9,0,7,0),
            I(1,2,1,4),I(0x37,29,4,0),I(9,0,5,key),J(original,True),I(9,0,6,0),
            I(0x37,29,31,0x10),0x03e00008,I(9,29,29,0x20),J(original),0]
    # Reusing a unit must detach its prior occupant through the native
    # association API before the group initializer assigns Wodan.
    uw=[I(9,0,2,0x601),I(5,5,2,21),0,I(9,29,29,-0x20),I(0x3f,29,31,0x10),I(0x3f,29,4,0),
        J(0x1abc50,True),I(9,0,7,0),I(1,2,0,8),I(0x37,29,4,0),I(0x3f,29,2,8),0x0040282d,
        J(0x1b1370,True),I(9,0,6,0),I(0x37,29,2,8),I(4,0,0,4),0,I(9,0,5,0x601),
        J(0x1b2070,True),I(9,0,6,0),I(0x37,29,31,0x10),0x03e00008,I(9,29,29,0x20),J(0x1b2070),0]
    pilot=unit+len(uw)*4;pw=wrapper(0x602,0x1ab6f0,0x1b1fd0,True)
    code=struct.pack('<%dI'%(len(init)+len(uw)+len(pw)),*(init+uw+pw)).ljust(end-start,b'\0')
    elf=lambda pc:0x94880+pc-0x100000
    with source.open('rb') as f:
        f.seek(elf(start));oldcode=f.read(end-start)
        assert u32(oldcode,0)==0x3c090054 and u32(oldcode,len(oldcode)-4)==0xe5008dec
        edits.append((elf(start),oldcode,code))
        for pc,target,original in [(0x1d5a3c,unit,0x1b2070),(0x1d5d98,pilot,0x1b1fd0)]:
            f.seek(elf(pc));before=f.read(4);assert before==struct.pack('<I',J(original,True))
            edits.append((elf(pc),before,struct.pack('<I',J(target,True))))
    edits=[e for e in edits if e[1]!=e[2]];edits.sort()
    for x,y in zip(edits,edits[1:]):assert x[0]+len(x[1])<=y[0]
    return edits,bytes(row),blobs,dialogue


def wodan_survival(apply=False):
    import os,subprocess
    before=sha(ISO);assert before=='8de813ec3c5c75e65dd1e2b1c3b4d358b141457f1ca10754365cc0ab7634f24c',before
    edits,row,blobs,dialogue=wodan_survival_plan()
    from validate_hidden_rewards import validate_wodan_survival
    checks=validate_wodan_survival(edits,row,blobs)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,a,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(a))==a;h.update(new);cursor+=len(a)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Wodan survives final duel and joins existing Sladegelmir after OG2 episode44; episode37 robot retained',
        checks=checks,dialogue=dialogue,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/wodan_survival_manifest.json';journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,a,new in edits:
                    f.seek(off);assert f.read(len(a))==a;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,a,new in edits:f.seek(off);f.write(a)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('edits','dialogue')},ensure_ascii=False,indent=2))


def grungust_type3_grant_plan(source=ISO):
    s=Scripts(source);n=103;at,size=s.logos[n];rs=s.records(n);insert=1464
    assert len(rs)==1467 and rs[1463][1][:3]==(0x5a,DEAD,0x601)
    assert rs[insert][1][:4]==(0x9c,DEAD,0x1d,0)
    original=s.data[at:at+size];b=bytearray(original);pos=u32(b,0x2c)+insert*96
    assert max(u32(b,u32(b,0x3c)+i*4) for i in range(u32(b,0x38)))<insert+u32(b,0x20)
    for i,(_,r) in enumerate(rs):
        if r[0] in (0x8b,0x8c):
            for j in ([6,7] if r[0]==0x8b else [7]):
                if r[j]<0x80000000:assert not i<insert<i+r[j]
    b[pos:pos]=struct.pack('<24I',*command(0x5a,0x602))
    struct.pack_into('<I',b,0x28,len(rs)+1)
    for off in (0x34,0x3c,0x44,0x4c,0x54,0x5c):struct.pack_into('<I',b,off,u32(b,off)+96)
    for off in (4,0x6c):struct.pack_into('<I',b,off,len(b))
    assert len(b)<=s.logos[n+1][0]-at and not any(s.data[at+size:at+len(b)])
    restored=bytearray(b);del restored[pos:pos+96];restored[:0x70]=original[:0x70];assert restored==original
    edits=[(MAP+at,s.data[at:at+len(b)],bytes(b)),
        (MAP+0x557f800+12+n*8,struct.pack('<I',size),struct.pack('<I',len(b)))]
    for base in (0x5da000,0x83f000):
        with source.open('rb') as f:f.seek(base);master=f.read(0x190000)
        assert struct.unpack_from('<H',master,0x11e898+0x45e*2)[0]==0x8a
        assert struct.unpack_from('<H',master,0x11e898+0x602*2)[0]==0xffff
        assert master[0x11f8a4+0x8a*100+0x22:0x11f8a4+0x8a*100+0x24]==b'\0\x08'
        edits.extend([(base+0x11e898+0x602*2,b'\xff\xff',struct.pack('<H',0x8a)),
            (base+0x11f8a4+0x8a*100+0x22,b'\0\x08',b'\1\x88')])
    # This wrapper handles UNIT keys only. The new unit key602 is unrelated
    # to Wodan's pilot key602 in the separate PTbl/pilot record namespace.
    edits.append((0x94880+0x114f90-0x100000,struct.pack('<I',0x2d080002),struct.pack('<I',0x2d080003)))
    with source.open('rb') as f:
        for off,a,b in edits:f.seek(off);assert f.read(len(a))==a,hex(off)
    return sorted(edits)


def grungust_type3_grant(apply=False):
    import os,subprocess
    before=sha(ISO);assert before=='4e4a25348d227539bdca20793d02a5a55aa74759127efe1ffa9001e083ee28bd',before
    edits=grungust_type3_grant_plan()
    from validate_hidden_rewards import validate_grungust_type3_grant
    checks=validate_grungust_type3_grant(edits)
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,a,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(a))==a;h.update(new);cursor+=len(a)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='OG2 episode37 clear Grungust Type3 (Sanger fixed Type3 Zankanto variant), robot only; old units preserved',
        checks=checks,edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/grungust_type3_grant_manifest.json';journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        running=subprocess.check_output(['powershell','-NoProfile','-Command',
            "@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True)
        assert running.strip()=='0','Close PCSX2 before ISO update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,a,new in edits:f.seek(off);assert f.read(len(a))==a;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,a,new in edits:f.seek(off);f.write(a)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def relocate_ally_sladegelmir_master(old):
    """Give ally601 its own body and six weapons; enemy490 stays original."""
    header=0x11E800
    ut,unit,wt,weapon=[header+u32(old,header+off) for off in (0x18,0x1C,0x20,0x24)]
    end=header+u32(old,0x11E00C);uc,wc=u32(old,unit+8),u32(old,weapon+8)
    assert (uc,wc)==(428,1630)
    assert all(struct.unpack_from('<H',old,ut+12+k*2)[0]==0xC8 for k in (0x490,0x601))
    keys=list(range(0x8C0,0x8C6));assert all(struct.unpack_from('<H',old,wt+12+k*2)[0]==0xFFFF for k in keys)
    uend,wend=unit+u32(old,unit+4),weapon+u32(old,weapon+4)
    body=bytearray(old[unit+12+0xC8*100:unit+12+(0xC8+1)*100])
    assert u32(body,0)==160000 and struct.unpack_from('<H',body,0x1A)[0]==1800
    oldkeys=list(struct.unpack_from('<16H',body,0x24));assert oldkeys[:6]==[0xA44,0x84E,0xA46,0xA47,0xA48,0xCD6]
    struct.pack_into('<I',body,0,8300);struct.pack_into('<H',body,0x1A,2100)
    struct.pack_into('<16H',body,0x24,*(keys+oldkeys[6:]))
    weapons=[]
    for key in oldkeys[:6]:
        index=struct.unpack_from('<H',old,wt+12+key*2)[0]
        record=bytearray(old[weapon+12+index*36:weapon+12+(index+1)*36])
        power=struct.unpack_from('<H',record,8)[0];assert power>0
        struct.pack_into('<H',record,8,power+200)
        if key==0xCD6:
            assert record[0x14]&4==0 and record[0x17:0x19]==b'\x01\x0A'
            record[0x14]|=4;record[0x15]=(record[0x15]&0xCF)|0x20
            record[0x18]=2
        weapons.append(bytes(record))
    b=bytearray(old[:end]);b[wend:wend]=b''.join(weapons);b[uend:uend]=body
    def moved(at):return at+(100 if at>=uend else 0)+(216 if at>=wend else 0)
    for field in range(0x18,0x8C,4):
        p=header+u32(old,header+field);assert header<=p<end
        struct.pack_into('<I',b,header+field,moved(p)-header)
    struct.pack_into('<II',b,unit+4,u32(old,unit+4)+100,uc+1)
    assert u32(old,ut+4)==u32(old,unit+4)
    struct.pack_into('<I',b,ut+4,u32(old,ut+4)+100)
    struct.pack_into('<H',b,ut+12+0x601*2,uc)
    nw,nwt=moved(weapon),moved(wt)
    struct.pack_into('<II',b,nw+4,u32(old,weapon+4)+216,wc+6)
    for i,k in enumerate(keys):struct.pack_into('<H',b,nwt+12+k*2,wc+i)
    struct.pack_into('<I',b,0x11E00C,u32(old,0x11E00C)+316)
    assert len(b)==end+316<=len(old) and not any(old[end:len(b)])
    assert b[unit+12:unit+12+uc*100]==old[unit+12:unit+12+uc*100]
    assert b[nw+12:nw+12+wc*36]==old[weapon+12:weapon+12+wc*36]
    restored=bytearray(b);del restored[wend+100:wend+316];del restored[uend:uend+100]
    for field in range(0x18,0x8C,4):restored[header+field:header+field+4]=old[header+field:header+field+4]
    for p,n in ((unit+4,8),(ut+4,4),(ut+12+0x601*2,2),(weapon+4,8),(0x11E00C,4)):
        restored[p:p+n]=old[p:p+n]
    for k in keys:restored[wt+12+k*2:wt+14+k*2]=old[wt+12+k*2:wt+14+k*2]
    assert restored==old[:end],'Unrelated master data changed'
    return bytes(b)


def sladegelmir_ally_balance(apply=False):
    import os,subprocess
    before=sha(ISO);assert before=='3f7285fc75c92c282eea7820bf4688a23aca0cfe10de247ad8c31b190780eb29',before
    edits=[];masters=[]
    with ISO.open('rb') as f:
        for base in (0x5DA000,0x83F000):
            f.seek(base);old=f.read(0x1A5800);b=relocate_ally_sladegelmir_master(old)
            edits.append((base+0x11E000,old[0x11E000:len(b)],b[0x11E000:]));masters.append(b)
    from validate_hidden_rewards import validate_sladegelmir_ally_balance
    checks=validate_sladegelmir_ally_balance(masters[0])
    h=hashlib.sha256();pos=0
    with ISO.open('rb') as f:
        for at,a,b in edits:
            while pos<at:
                raw=f.read(min(4<<20,at-pos));assert raw;h.update(raw);pos+=len(raw)
            assert f.read(len(a))==a;h.update(b);pos+=len(a)
        while raw:=f.read(4<<20):h.update(raw)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        feature='Ally Sladegelmir HP8300 armor2100 all six weapons+200; finisher P/range1-2/barrier penetration; enemy unchanged',
        edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/sladegelmir_ally_balance_manifest.json';journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        assert subprocess.check_output(['powershell','-NoProfile','-Command',"@(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -like '*pcsx*').Count"],text=True).strip()=='0','Close PCSX2 before update'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for at,a,b in edits:f.seek(at);assert f.read(len(a))==a;f.seek(at);f.write(b)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for at,a,b in edits:f.seek(at);f.write(a)
                f.flush();os.fsync(f.fileno())
            raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


def relocate_ally_mumei_master(old):
    """Preserve each option profile while extending ally-only Mumei tables."""
    end=0x11e800+u32(old,0x11e00c)
    unit,weapon=0x11f898,0x12bf7c
    uc,wc=u32(old,unit+8),u32(old,weapon+8)
    assert (uc,wc)==(427,1628)
    assert struct.unpack_from('<H',old,0x11e898+0x600*2)[0]==0x15c
    assert all(struct.unpack_from('<H',old,0x129f7c+k*2)[0]==0xffff for k in (0x851,0x852))
    uend,wend=unit+u32(old,unit+4),weapon+u32(old,weapon+4)
    assert (uend,wend)==(0x129f70,0x13a478)
    ally=bytearray(old[unit+12+0x15c*100:unit+12+(0x15c+1)*100])
    assert u32(ally,0)==63000
    struct.pack_into('<I',ally,0,6300)
    keys=list(struct.unpack_from('<16H',ally,0x24));assert keys[:4]==[0xd91,0xd92,0xd93,0xd94]
    keys[2:4]=[0x851,0x852];struct.pack_into('<16H',ally,0x24,*keys)
    weapons=[]
    for key,power in ((0xd93,5600),(0xd94,4600)):
        idx=struct.unpack_from('<H',old,0x129f7c+key*2)[0]
        rec=bytearray(old[weapon+12+idx*36:weapon+12+(idx+1)*36])
        assert struct.unpack_from('<H',rec,8)[0]==power-900
        struct.pack_into('<H',rec,8,power);weapons.append(bytes(rec))
    b=bytearray(old[:end]);b[wend:wend]=b''.join(weapons);b[uend:uend]=ally
    def relocated(p):return p+(100 if p>=uend else 0)+(72 if p>=wend else 0)
    for field in range(0x18,0x8c,4):
        p=0x11e800+u32(old,0x11e800+field)
        assert 0x11e800<=p<end
        struct.pack_into('<I',b,0x11e800+field,relocated(p)-0x11e800)
    struct.pack_into('<II',b,unit+4,u32(old,unit+4)+100,uc+1)
    assert u32(old,0x11e890)==u32(old,unit+4)
    struct.pack_into('<I',b,0x11e890,u32(old,0x11e890)+100)
    struct.pack_into('<H',b,0x11e898+0x600*2,uc)
    nw=relocated(weapon);nt=relocated(0x129f70)
    struct.pack_into('<II',b,nw+4,u32(old,weapon+4)+72,wc+2)
    for k,idx in ((0x851,wc),(0x852,wc+1)):struct.pack_into('<H',b,nt+12+k*2,idx)
    struct.pack_into('<I',b,0x11e00c,u32(old,0x11e00c)+172)
    assert len(b)==end+172<=len(old) and not any(old[end:len(b)])
    # All existing records, including enemy Mumei and every other weapon,
    # remain byte-identical at their new table locations.
    assert b[unit+12:unit+12+uc*100]==old[unit+12:unit+12+uc*100]
    assert b[nw+12:nw+12+wc*36]==old[weapon+12:weapon+12+wc*36]
    restored=bytearray(b);del restored[wend+100:wend+172];del restored[uend:uend+100]
    for field in range(0x18,0x8c,4):restored[0x11e800+field:0x11e804+field]=old[0x11e800+field:0x11e804+field]
    for p,n in ((unit+4,8),(0x11e890,4),(0x11e898+0x600*2,2),(weapon+4,8),(0x11e00c,4)):
        restored[p:p+n]=old[p:p+n]
    for k in (0x851,0x852):restored[0x129f7c+k*2:0x129f7e+k*2]=old[0x129f7c+k*2:0x129f7e+k*2]
    assert restored==old[:end],'Unrelated master bytes changed'
    return bytes(b)


def mumei_ally_balance(apply=False):
    """Separate ally600 from enemy52A; HP6300, swords4600/5600."""
    import os,psutil
    before=sha(ISO)
    assert before=='ac45e787b9e31e61ae3a87cda75673c78f5f48d3fffa12777ebde8de8263a4f6',before
    edits=[];masters=[]
    for base in (0x5da000,0x83f000):
        with ISO.open('rb') as f:f.seek(base);old=f.read(0x1a5800)
        b=relocate_ally_mumei_master(old)
        masters.append(bytes(b));edits.append((base+0x11e000,old[0x11e000:len(b)],bytes(b[0x11e000:])))
    from validate_hidden_rewards import validate_mumei_ally_balance
    checks=validate_mumei_ally_balance(masters[0])
    h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,a,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(a))==a;h.update(new);cursor+=len(a)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,checks=checks,
        feature='Ally Mumei independent body and weapons: HP6300, Shishio4600, finisher5600; enemy preserved',
        edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/mumei_ally_balance_manifest.json';journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        target=os.path.normcase(os.path.abspath(ISO))
        for proc in psutil.process_iter(['name']):
            if 'pcsx2' in (proc.info['name'] or '').lower():
                assert all(os.path.normcase(os.path.abspath(x.path))!=target for x in proc.open_files()),'Close emulator using SRWOGS_K.iso'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,a,b in edits:f.seek(off);assert f.read(len(a))==a;f.seek(off);f.write(b)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,a,b in edits:f.seek(off);f.write(a)
                f.flush();os.fsync(f.fileno())
            raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


def episode6_granzon_test(apply=False):
    """Diagnostic replacement only: same episode6 grant, Granzon robot body.

    Use a distinct alias so existing Mumei save records are not remapped.
    No script insertion, dialogue, stats or boarding masks are changed.
    """
    import os,psutil
    before=sha(ISO)
    assert before=='ac45e787b9e31e61ae3a87cda75673c78f5f48d3fffa12777ebde8de8263a4f6',before
    s=Scripts();at,r=s.records(74)[532]
    assert r[:3]==(0x5a,DEAD,0x600)
    edits=[(MAP+at+8,struct.pack('<I',0x600),struct.pack('<I',0x603)),
           (0x94880+0x114f90-0x100000,struct.pack('<I',0x2d080003),struct.pack('<I',0x2d080004))]
    with ISO.open('rb') as f:
        for base in (0x5da000,0x83f000):
            f.seek(base);m=f.read(0x190000)
            assert struct.unpack_from('<H',m,0x11e898+0x456*2)[0]==0x7f
            assert struct.unpack_from('<H',m,0x11f8a4+0x7f*100+12)[0]==268
            assert struct.unpack_from('<H',m,0x11e898+0x603*2)[0]==0xffff
            edits.append((base+0x11e898+0x603*2,b'\xff\xff',struct.pack('<H',0x7f)))
        for off,a,b in edits:f.seek(off);assert f.read(len(a))==a,hex(off)
    # Execute the actual game grant with the proposed alias and owner wrapper.
    from validate_hidden_rewards import VM
    vm=VM();c=vm.cpu
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x582980]=f.read(0x482980)
        f.seek(0x5da000);m=bytearray(f.read(0x190000))
    struct.pack_into('<H',m,0x11e898+0x603*2,0x7f)
    master=c.read(0x59d360,4);save=c.read(0x59d364,4)
    for field,rel in ((0x28,0x11e88c),(0x40,0x11f898)):
        dst=c.read(master+field,4);size=u32(m,rel+4);c.mem[dst:dst+size]=m[rel:rel+size]
    c.write(0x114f90,0x2d080004,4)
    assert c.run(0x1abc50,[save,0x603,0,0])==-1
    pilots=bytes(c.mem[save+0x25cfc:save+0x25cfc+512*92])
    vm.op(command(0x5a,0x603));slot=c.run(0x1abc50,[save,0x603,0,0])
    assert slot>=0 and c.run(0x1a9b70,[save,slot,1])==1
    assert c.run(0x1b1300,[save,slot,0])==-1
    assert c.mem[save+0x25cfc:save+0x25cfc+512*92]==pilots
    stable=bytes(c.mem[save:save+0x3b400]);vm.op(command(0x5a,0x603));assert c.mem[save:save+0x3b400]==stable
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,a,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(a))==a;h.update(new);cursor+=len(a)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(feature='Diagnostic episode6 Granzon robot instead of Mumei; separate alias603',source_sha256=before,
        target_sha256=h.hexdigest(),applied=False,native_owned_pilotless_idempotent=True,
        script_layout_unchanged=True,rendered_playthrough=False,
        edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    audit=ROOT/'runtime/scenario_skip_audit.json';data=json.loads(audit.read_text(encoding='utf-8'))
    data['episode6_granzon_test']=report;audit.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        target=os.path.normcase(os.path.abspath(ISO))
        for proc in psutil.process_iter(['name']):
            if 'pcsx2' in (proc.info['name'] or '').lower():
                assert all(os.path.normcase(os.path.abspath(x.path))!=target for x in proc.open_files()),'Close emulator using SRWOGS_K.iso'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,a,b in edits:f.seek(off);assert f.read(len(a))==a;f.seek(off);f.write(b)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
        except Exception:
            with ISO.open('r+b') as f:
                for off,a,b in edits:f.seek(off);f.write(a)
                f.flush();os.fsync(f.fileno())
            raise
        report['applied']=True;data['episode6_granzon_test']=report
        audit.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


def mumei_episode6_only(apply=False):
    """Remove the direct episode5 insertion; retain the existing episode6 grant.

    The same removal was tested by the user in the isolated diagnostic ISO.
    Do not rebuild dialogue or touch either unit master or the prototype ISO.
    """
    import os,psutil
    before=sha(ISO)
    assert before=='25ca7578de0a2b8647b08aeb64992d404d7d304d02285ba4edf2a87919013056',before
    s=Scripts();baseline=Scripts(ROOT/'baseline/srwogs-v1.4.3s1.iso')
    at,size=s.logos[138];old=s.data[at:at+size];b=bytearray(old)
    co=u32(b,0x2c);insert=626;pos=co+insert*96
    assert u32(b,0x28)==804
    assert struct.unpack_from('<24I',b,pos)==tuple(command(0x5a,0x600))
    del b[pos:pos+96]
    for off in (4,0x6c,0x28,0x34,0x3c,0x44,0x4c,0x54,0x5c):
        struct.pack_into('<I',b,off,u32(b,off)-(1 if off==0x28 else 96))
    bp,bs=baseline.logos[138];table=u32(b,0x3c);original_table=u32(baseline.data,bp+0x3c)
    labels=u32(b,0x38)
    assert labels==u32(baseline.data,bp+0x38)
    for i in range(labels):
        v=u32(baseline.data,bp+original_table+i*4)
        actual=u32(b,table+i*4)
        assert actual==v+(1 if v>=709 else 0),(i,v,actual)
        struct.pack_into('<I',b,table+i*4,v)
    assert len(b)==bs and b[:0x70]==baseline.data[bp:bp+0x70]
    # Every original command is retained exactly, including all dialogue args.
    prior=[r for _,r in s.records(138)]
    assert [struct.unpack_from('<24I',b,co+i*96) for i in range(803)]==prior[:insert]+prior[insert+1:]
    edits=[(MAP+at,old,bytes(b)+bytes(96)),
           (MAP+0x557f800+12+138*8,struct.pack('<I',size),struct.pack('<I',len(b)))]
    # Guard against accidentally applying a different removal than the tested one.
    tested=json.loads((ROOT/'runtime/scenario_skip_test_restore.json').read_text(encoding='utf-8'))
    assert [(e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in tested['edits']]==edits
    from validate_hidden_rewards import validate_mumei_fallback
    checks=validate_mumei_fallback(edits,applied=True,episode5_removed=True)
    edits.sort();h=hashlib.sha256();cursor=0
    with ISO.open('rb') as f:
        for off,a,new in edits:
            while cursor<off:
                chunk=f.read(min(4<<20,off-cursor));assert chunk;h.update(chunk);cursor+=len(chunk)
            assert f.read(len(a))==a;h.update(new);cursor+=len(a)
        while chunk:=f.read(4<<20):h.update(chunk)
    report=dict(source_sha256=before,target_sha256=h.hexdigest(),applied=False,
        feature='Mumei robot only at episode6 clear if not owned; episode5 original command layout restored',
        checks=checks,episode5_start_user_verified_in_diagnostic=True,production_playthrough_verified=False,
        edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits])
    journal=ROOT/'runtime/mumei_episode6_manifest.json'
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        # Other emulator sessions may use the separate TEST image. Refuse only
        # when this exact production ISO is open, and never close user sessions.
        target=os.path.normcase(os.path.abspath(ISO))
        for proc in psutil.process_iter(['name']):
            if 'pcsx2' not in (proc.info['name'] or '').lower():continue
            for opened in proc.open_files():
                assert os.path.normcase(os.path.abspath(opened.path))!=target,'Close the emulator using SRWOGS_K.iso'
        assert sha(ISO)==before
        try:
            with ISO.open('r+b') as f:
                for off,a,new in edits:
                    f.seek(off);assert f.read(len(a))==a;f.seek(off);f.write(new)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==report['target_sha256']
            assert validate_mumei_fallback([],applied=True,episode5_removed=True)==checks
        except Exception:
            with ISO.open('r+b') as f:
                for off,a,new in edits:f.seek(off);f.write(a)
                f.flush();os.fsync(f.fileno())
            assert sha(ISO)==before
            raise
        report['applied']=True
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dump',type=int,nargs='+');p.add_argument('--find',type=str);p.add_argument('--plan',action='store_true');p.add_argument('--apply',action='store_true')
    p.add_argument('--grant-mumei',action='store_true')
    p.add_argument('--mumei-fallback',action='store_true')
    p.add_argument('--mumei-episode6-only',action='store_true')
    p.add_argument('--episode6-granzon-test',action='store_true')
    p.add_argument('--mumei-ally-balance',action='store_true')
    p.add_argument('--sladegelmir-ally-balance',action='store_true')
    p.add_argument('--wodan-survival',action='store_true')
    p.add_argument('--grungust-type3-grant',action='store_true')
    p.add_argument('--ouka-survival',action='store_true')
    p.add_argument('--episode6-bonus',action='store_true')
    p.add_argument('--daizengar-durability',action='store_true')
    p.add_argument('--daizengar-refit',action='store_true')
    p.add_argument('--daizengar-combined-arsenal',action='store_true')
    p.add_argument('--daizengar-unified',action='store_true')
    p.add_argument('--daizengar-animation-links',action='store_true')
    p.add_argument('--daizengar-arsenal-balance',action='store_true')
    p.add_argument('--axel-spirits',action='store_true')
    p.add_argument('--seolla-spirits',action='store_true')
    p.add_argument('--battle-rewards',action='store_true')
    p.add_argument('--enemy-strength',action='store_true')
    p.add_argument('--melee-range-two',action='store_true')
    p.add_argument('--weapon-balance',action='store_true')
    p.add_argument('--grant-sladegelmir',action='store_true')
    p.add_argument('--daizengar-refit-labels',action='store_true')
    p.add_argument('--daizengar-builtin-weapons',action='store_true')
    p.add_argument('--weapon-consumption',action='store_true')
    p.add_argument('--release-preflight',action='store_true')
    p.add_argument('--daizengar-upgrade-cost',action='store_true')
    p.add_argument('--global-weapon-upgrade-discount',action='store_true')
    p.add_argument('--small-enemy-hp-boost',action='store_true')
    p.add_argument('--ouka-route-fix',action='store_true')
    p.add_argument('--daizengar-refit-visibility',action='store_true')
    a=p.parse_args()
    if a.sladegelmir_ally_balance:sladegelmir_ally_balance(a.apply);sys.exit()
    if a.ouka_route_fix:ouka_route_fix(a.apply);sys.exit()
    if a.small_enemy_hp_boost:small_enemy_hp_boost(a.apply);sys.exit()
    if a.global_weapon_upgrade_discount:global_weapon_upgrade_discount(a.apply);sys.exit()
    if a.mumei_ally_balance:mumei_ally_balance(a.apply);sys.exit()
    if a.episode6_granzon_test:episode6_granzon_test(a.apply);sys.exit()
    if a.mumei_episode6_only:mumei_episode6_only(a.apply);sys.exit()
    if a.grungust_type3_grant:grungust_type3_grant(a.apply);sys.exit()
    if a.wodan_survival:wodan_survival(a.apply);sys.exit()
    if a.mumei_fallback:mumei_fallback(a.apply);sys.exit()
    if a.enemy_strength:enemy_strength(a.apply);sys.exit()
    if a.battle_rewards:battle_rewards(a.apply);sys.exit()
    if a.seolla_spirits:seolla_spirits(a.apply);sys.exit()
    if a.axel_spirits:axel_spirits(a.apply);sys.exit()
    if a.daizengar_arsenal_balance:daizengar_arsenal_balance(a.apply);sys.exit()
    if a.daizengar_animation_links:daizengar_animation_links(a.apply);sys.exit()
    if a.daizengar_unified:daizengar_unified(a.apply);sys.exit()
    if a.daizengar_combined_arsenal:daizengar_combined_arsenal(a.apply);sys.exit()
    if a.daizengar_refit_visibility:daizengar_refit_visibility(a.apply);sys.exit()
    if a.daizengar_upgrade_cost:daizengar_upgrade_cost(a.apply);sys.exit()
    if a.release_preflight:release_preflight(a.apply);sys.exit()
    if a.weapon_consumption:weapon_consumption(a.apply);sys.exit()
    if a.daizengar_builtin_weapons:daizengar_builtin_weapons(a.apply);sys.exit()
    if a.daizengar_refit_labels:daizengar_refit_labels(a.apply);sys.exit()
    if a.grant_sladegelmir:grant_sladegelmir(a.apply);sys.exit()
    if a.weapon_balance:weapon_balance(a.apply);sys.exit()
    if a.melee_range_two:melee_range_two(a.apply);sys.exit()
    if a.daizengar_refit:daizengar_refit(a.apply);sys.exit()
    if a.daizengar_durability:daizengar_durability(a.apply);sys.exit()
    if a.episode6_bonus:episode6_bonus(a.apply);sys.exit()
    if a.ouka_survival:ouka_survival(a.apply);sys.exit()
    if a.grant_mumei:grant_mumei(a.apply);sys.exit()
    if a.plan or a.apply:build(a.apply);sys.exit()
    s=Scripts()
    if a.dump:s.dump(*a.dump)
    if a.find:
        for n in range(len(s.logos)):
            for i,(at,t) in enumerate(s.texts(n)):
                if a.find in t:print(n,i,hex(at),t)
