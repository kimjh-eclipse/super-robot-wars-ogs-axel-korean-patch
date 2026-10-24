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

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dump',type=int,nargs='+');p.add_argument('--find',type=str);p.add_argument('--plan',action='store_true');p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    if a.plan or a.apply:build(a.apply);sys.exit()
    s=Scripts()
    if a.dump:s.dump(*a.dump)
    if a.find:
        for n in range(len(s.logos)):
            for i,(at,t) in enumerate(s.texts(n)):
                if a.find in t:print(n,i,hex(at),t)
