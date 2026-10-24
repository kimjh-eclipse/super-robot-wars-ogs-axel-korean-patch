"""Offline evidence: execute actual R5900 branch/grant handlers from a save.

This is not a full PCSX2 playthrough. Text, master data and ISO bytes outside
the manifest are separately checked for exact preservation.
"""
import hashlib,itertools,json,struct,zipfile
from build_hidden_rewards import *
from r5900_scalar_check import CPU

def load_ram(path):
    with zipfile.ZipFile(path) as z:
        info=z.getinfo('eeMemory.bin')
        try:return z.read(info)
        except NotImplementedError:
            import zstandard
            assert info.compress_type in (20,93),info.compress_type
            with path.open('rb') as f:
                f.seek(info.header_offset);header=f.read(30)
                name,extra=struct.unpack_from('<HH',header,26);f.seek(name+extra,1)
                result=zstandard.ZstdDecompressor().decompress(f.read(info.compress_size),max_output_size=info.file_size)
            assert len(result)==info.file_size
            return result

CTX=0x1800000;REC=0x1900000
ram=load_ram(ROOT/'sstates/SLPS-25733 (C7D3DE2B).01.p2s')
class VM:
    def __init__(self):
        self.cpu=CPU(ram)
        for i in range(16):self.cpu.write(CTX+0x8E8C+i*4,0xFFFFFFFF,4)
    def op(self,r,index=0):
        for j,v in enumerate(r):self.cpu.write(REC+j*4,v,4)
        self.cpu.write(CTX+0x6270,index,4)
        fn=u32(ram,0x868190+r[0]*12+8)
        assert self.cpu.run(fn,[CTX,REC])==10
        return self.cpu.read(CTX+0x6270,4)+1
    def reg(self,n,v):self.op(command(0x95,v,n))
    def trace(self,rs,start,end,flags=None):
        flags=flags or {};i=start;seen=[]
        for _ in range(1000):
            if i>=end:return seen
            seen.append(i);r=list(rs[i])
            if r[0]==0x8E:
                if r[2]==0x100BD:self.reg(r[5],flags.get((r[3],r[4]),0))
                i+=1
            elif r[0] in [0x8B,0x8C,0x84,0x85,0x95,0x59]:i=self.op(r,i)
            else:i+=1
        raise AssertionError('VM script failed to terminate')

def main():
    s=Scripts();actual=sha(ISO)
    manifest=ROOT/'runtime/hidden_rewards_manifest.json'
    applied=actual!=EXPECTED
    if applied:
        m=json.loads(manifest.read_text(encoding='utf-8'));assert actual==m['target_sha256']
        # Reconstruct pre-option MAP in memory only.
        b=bytearray(s.data)
        for e in m['edits']:
            o=e['offset']-MAP;a=bytes.fromhex(e['after']);old=bytes.fromhex(e['before'])
            assert b[o:o+len(a)]==a;b[o:o+len(old)]=old
        s.data=bytes(b)
        # Restore child directory lengths cached by Scripts.
        for n,(a,z) in enumerate(s.logos):s.logos[n]=(a,u32(s.data,0x557F800+12+n*8))
    edits,notes,blobs=plan(s)
    patched={n:[struct.unpack_from('<24I',b,u32(b,0x2C)+i*0x60) for i in range(u32(b,0x28))] for n,b in blobs.items()}
    checks=[]
    # Execute unchanged true/false handlers to establish branch semantics.
    for op in [0x8B,0x8C]:
        for truth in [False,True]:
            r=command(op,int(truth),0x8000,1,1,3 if op==0x8B else DEAD,5)
            assert VM().op(r,100)==(101 if truth else (103 if op==0x8B else 105))
    checks.append('Actual R5900 IF and IF/ELSE true/false paths')
    for n,i in [(89,1183),(90,922),(106,1844),(118,44),(118,46),(119,42),(119,54)]:
        for v in [0,1,65535]:
            vm=VM();vm.reg(0x8000,v);assert vm.op(patched[n][i],i)==i+1
    for n,i in [(88,68),(105,187)]:
        assert VM().op(patched[n][i],i)==i+3
    checks.append('Reward conditions pass at low/high input; weapon confiscation skipped')
    for f in itertools.product([0,1],repeat=3):
        vm=VM();trace=vm.trace(patched[100],1762,1776,dict(zip([(11,1),(11,2),(11,3)],f)))
        assert 1769 not in trace and 1774 not in trace and 1771 in trace
    checks.append('Wildwurger L retained for all 8 prior-flag combinations')
    for difficulty in [0,1,2]:
        vm=VM();vm.reg(0x8004,difficulty);trace=vm.trace(patched[101],505,511)
        assert trace.count(510)==1
        assert (506 in trace)==(difficulty==0)
    checks.append('Gilliam boomerang exactly once, Easy stat changes remain Easy-only')
    for f in itertools.product([0,1],repeat=3):
        trace=VM().trace(patched[105],145,155,dict(zip([(19,0),(19,1),(19,2)],f)))
        assert 151 in trace and 153 not in trace
    checks.append('Raven group 0x1E selected for all 8 route-flag combinations')
    trace=VM().trace(patched[118],43,51)
    assert 47 in trace and 48 in trace
    trace=VM().trace(patched[119],39,59)
    assert 55 in trace and 56 in trace
    trace=VM().trace(patched[109],2560,2568)
    assert 2562 in trace and 2566 in trace
    rs=s.records(119)
    g=next(i for i,(at,r) in enumerate(rs) if at==0x64969E0)
    vm=VM();vm.trace(patched[119],92,96);trace=vm.trace(patched[119],g,g+5)
    assert g+1 in trace and g+2 in trace
    checks.append('Route-specific S/R unlocks and both G Impact/Neo Chakram grants with zero flags')
    # Assert exact original spawn records: same pilots/positions, upgraded units.
    wp=0x5071000
    def spawn(n):
        o,z=struct.unpack_from('<II',s.data,wp+8+n*8);a=wp+o
        return [struct.unpack_from('<84I',s.data,a+44+i*0x150) for i in range(u32(s.data,a+40))]
    r=spawn(107);assert [r[i][0] for i in [142,143]]==[0x564,0x568]
    assert r[142][1]==r[143][1]==0x1E
    assert r[89][2:]==r[142][2:] and r[90][2:]==r[143][2:]
    r=spawn(103);assert r[7][0:2]==(0x4C3,1)
    checks.append('UNTD Raven and Wildwurger spawn identities verified')
    # Real allocation handlers run, rather than only checking written opcodes.
    for op,key in [(0x5F,0xDB9),(0x5F,0xDAC),(0x5F,0xDCA),(0x5B,0x1F),(0x5B,0x20),(0x5B,0x21)]:
        vm=VM();before=bytes(vm.cpu.mem);vm.op(command(op,key,0))
        save=u32(ram,0x59D364);global_save=u32(ram,0x59D36C)
        assert any((save<=a<save+0x40000 or global_save<=a<global_save+0x3000) for a,n,pc in vm.cpu.writes)
    checks.append('Actual game weapon/part grant handlers completed on copied save RAM')
    # Metadata and all localized pools retain their content after insertion.
    for n,b in blobs.items():
        at,size=s.logos[n];old=s.data[at:at+size]
        if n==88:
            for co,po,scale in [(0x30,0x34,16),(0x38,0x3C,4),(0x40,0x44,4),(0x50,0x54,4)]:
                num=u32(old,co);assert num==u32(b,co)
                assert old[u32(old,po):u32(old,po)+num*scale]==b[u32(b,po):u32(b,po)+num*scale]
            assert old[u32(old,0x4C):]==b[u32(b,0x4C):]
        else:assert old[u32(old,0x34):]==b[u32(b,0x34):]
    assert [r[0] for r in patched[88][812:819]]==[0x5B]*3+[0x5F]*2+[0x33]*2
    assert sum(r[0]==0x5F and r[2]==0xDB9 for r in patched[88])==1
    checks.append('Inspector grants moved once; all text/auxiliary tables byte-preserved')
    if applied:
        # Mask only changed bytes back to the protected input and hash all 4.5GB.
        h=hashlib.sha256();cursor=0
        with open(ISO,'rb') as f:
            for off,old,new in edits:
                while cursor<off:
                    b=f.read(min(4<<20,off-cursor));h.update(b);cursor+=len(b)
                assert f.read(len(new))==new;h.update(old);cursor+=len(new)
            while b:=f.read(4<<20):h.update(b)
        assert h.hexdigest()==EXPECTED
        checks.append('Entire ISO outside exact planned edits preserved (SHA-256 reconstruction)')
    report=dict(passed=True,iso_applied=applied,checks=checks,live_playthrough=False)
    (ROOT/'runtime/hidden_rewards_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
