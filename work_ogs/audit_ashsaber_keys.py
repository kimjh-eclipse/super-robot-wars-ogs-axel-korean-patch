"""Read-only key and allocator audit for the Ashsaber acquisition repair."""
from pathlib import Path
import argparse
import struct
from runtime.analyze_change_candidate_filter import load_ram
from mips_dump import decode as disasm
from ogs_korean_codec import decode

ROOT = Path(__file__).resolve().parent
STATE = Path(r'C:\Users\OXP2\Desktop\슈퍼로봇대전 2차, 3파 알파 hd버전\pcsx2-v1.7.4005-windows-64bit-AVX2-Qt\sstates\SLPS-25733 (D3A7BA11).01.p2s')

def u16(d, p): return struct.unpack_from('<H', d, p)[0]
def u32(d, p): return struct.unpack_from('<I', d, p)[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', type=Path, default=STATE)
    ap.add_argument('--disasm', nargs=2, type=lambda s: int(s, 0))
    args = ap.parse_args()
    d = load_ram(args.state)
    if args.disasm:
        for pc in range(*args.disasm, 4):
            print(f'{pc:08X} {u32(d,pc):08X} {disasm(u32(d,pc),pc,None)}')
        return
    save = u32(d, 0x59D364)
    print('save', hex(save))
    for tag in (b'Unit', b'UTbl', b'Strg'):
        at = d.find(tag, 0xB00000)
        print(tag, hex(at), d[at:at+16].hex(' '))
    ut = d.find(b'UTbl', 0xB00000)
    un = d.find(b'Unit', 0xB00000)
    st = d.find(b'Strg', 0xB00000)
    count = u32(d,ut+8)
    assert 0 < count < 0x10000
    for slot in (0x3B,0x3C,0x49,0x4E):
        p=un+12+slot*100
        nid=u16(d,p+12)
        np=st+u32(d,st+12+4*nid)
        name=decode(d[np:d.index(b'\0',np)])
        keys=[i for i in range(count) if u16(d,ut+12+2*i)==slot]
        print('Unit',hex(slot),name,'HP',u32(d,p),'keys',[hex(x) for x in keys])
        for i in range(512):
            rec=save+0x6EFC+i*0xD8
            key=u16(d,rec)
            if key in keys:
                owned=bool(u32(d,save+0x3B2FC+(i//32)*4)&(1<<(i%32)))
                print('roster',hex(i),'key',hex(key),'owned',owned,'record',d[rec:rec+0x38].hex(' '))
    for prop in (1,3):
        p=0x867770+prop*12
        print('getter',prop,d[p:p+12].hex(' '))
        fn=u32(d,p)
        if 0x100000<=fn<0x500000:
            for pc in range(fn,fn+0x30,4):
                print(hex(pc),disasm(u32(d,pc),pc,None))

if __name__=='__main__': main()
