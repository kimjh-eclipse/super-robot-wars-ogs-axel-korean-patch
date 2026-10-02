"""Guarded in-place Ashsaber update of CURRENT. Never modifies user saves.

Actual UTbl keys, not Unit HP: enhanced Soulgain 0x428, Ashsaber 0x41C.
Backfill runs before change-unit menu initialization/list construction.
The allocator-tail hook explicitly reloads its original return address after
the nested allocator call. Existing release assets are never overwritten.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'build/SRWOGS_AxelRoleSwap_kr_CURRENT.iso'
EXPECTED='831A646BCDE363B92A1E8CD2C5CACE786102A61833A5757BB155B527CF35B9CC'
PREVIOUS='85B52648D87020A72136D690D6646167A2C35BEC95519FB7F42AC1ADE6E4FF4F'
TARGET='94DBCB2995D7A8CACCB6B07C92286DDBF50670B3D275B3D8792661055E8BE5A1'
EVENT=0x4995A0
MENU=0x49A6F4
SOUL=0x428
ASH=0x41C

def iso_at(va): return 0x94880+va-0x100000
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest().upper()
def imm(op,t,s,n): return op<<26|s<<21|t<<16|(n&65535)
def move(d,s): return s<<21|d<<11|0x2D
def jump(va,link=False): return (3 if link else 2)<<26|(va>>2)

class Asm:
    def __init__(self,base): self.base=base; self.w=[];self.labels={};self.refs=[]
    def emit(self,*ws): self.w.extend(ws)
    def label(self,n): self.labels[n]=self.base+len(self.w)*4
    def branch(self,op,s,t,label):
        self.refs.append((len(self.w),label));self.emit(imm(op,t,s,0))
    def finish(self,size):
        for i,label in self.refs:
            delta=(self.labels[label]-(self.base+i*4+4))//4
            self.w[i]|=delta&65535
        b=struct.pack('<'+'I'*len(self.w),*self.w)
        assert len(b)<=size,(hex(self.base),len(b),size)
        return b.ljust(size,b'\0')

def patches():
    # Allocator epilogue: s4=key, s5=save, s6=pool, s3=result.
    a=Asm(EVENT)
    a.emit(imm(9,1,0,SOUL))
    a.branch(5,20,1,'done');a.emit(move(4,21))
    a.branch(5,22,0,'done');a.emit(imm(9,5,0,ASH)) # allied pool only
    a.emit(imm(9,6,0,1),jump(0x1ABC50,True),move(7,0))
    a.branch(1,2,1,'activate');a.emit(move(4,21))
    a.emit(imm(9,5,0,ASH),jump(0x1B2070,True),move(6,0))
    a.label('activate')
    a.branch(1,2,0,'done');a.emit(move(6,2))
    # Record allocation alone leaves affiliation/property 2 = 0, which
    # fails 1A9B70(save,slot,1). Register as allied group 1 via game setter.
    a.emit(move(4,21),imm(9,5,0,2),imm(9,7,0,1),jump(0x1AF000,True),move(8,0))
    a.label('done')
    a.emit(move(2,19),jump(0x1B21D8),imm(55,31,29,0x70))
    event=a.finish(96)
    # Runs before the original initializer. s1=save, s3=menu context.
    a=Asm(MENU)
    a.emit(move(4,17),imm(9,5,0,SOUL),imm(9,6,0,1),jump(0x1ABC50,True),move(7,0))
    a.branch(1,2,0,'original');a.emit(move(4,17))
    a.emit(imm(9,5,0,ASH),imm(9,6,0,1),jump(0x1ABC50,True),move(7,0))
    a.branch(1,2,1,'activate');a.emit(move(4,17))
    a.emit(imm(9,5,0,ASH),jump(0x1B2070,True),move(6,0))
    a.label('activate')
    a.branch(1,2,0,'original');a.emit(move(6,2))
    a.emit(move(4,17),imm(9,5,0,2),imm(9,7,0,1),jump(0x1AF000,True),move(8,0))
    a.label('original')
    a.emit(imm(15,1,0,2),imm(13,1,1,0xC260),0x02612021,
           jump(0x150760,True),0,jump(0x431780),0)
    menu=a.finish(132)
    return [
        # Keep the original ld ra at 1B21D4: allocation failure branches
        # directly to it, bypassing the new tail hook.
        ('allocator tail',iso_at(0x1B21D0),bytes.fromhex('2d 10 60 02 70 00 bf df'),struct.pack('<II',jump(EVENT),0xDFBF0070)),
        ('allocator cave',iso_at(EVENT),bytes(96),event),
        ('change-menu entry',iso_at(0x431778),bytes.fromhex('d8 41 05 0c 2d 90 00 00'),struct.pack('<II',jump(MENU),move(18,0))),
        ('change-menu cave',iso_at(MENU),bytes(132),menu),
        ('SHARED allied Ashsaber mask',0x6FAFD2,b'\x01\x02',b'\xff\xff'),
        ('IM allied Ashsaber mask',0x95FFD2,b'\x01\x02',b'\xff\xff'),
    ]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build',action='store_true');args=ap.parse_args()
    pp=patches()
    # Deny all sharing while hashing/writing, including PCSX2 reads.
    import ctypes
    import msvcrt
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    kernel.CreateFileW.restype=ctypes.c_void_p
    handle=kernel.CreateFileW(str(SOURCE),0xC0000000,0,None,3,0,None)
    if handle==ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    fd=msvcrt.open_osfhandle(handle,os.O_RDWR|os.O_BINARY)
    def stream_sha(f):
        f.seek(0);h=hashlib.sha256()
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
        return h.hexdigest().upper()
    with os.fdopen(fd,'r+b') as f:
        before=stream_sha(f)
        if before==TARGET:
            print('CURRENT is already updated.');return
        if before not in (EXPECTED,PREVIOUS):raise ValueError(f'CURRENT hash differs: {before}')
        if before==PREVIOUS:
            prior=json.loads((ROOT/'runtime/ashsaber_verified_acquisition_manifest.json').read_text(encoding='utf-8'))
            if prior['output_sha256']!=PREVIOUS:raise ValueError('Prior patch manifest mismatch')
            prior_ranges={int(p['offset'],16):bytes.fromhex(p['after']) for p in prior['patches']}
            pp=[(label,off,prior_ranges[off],new) for label,off,old,new in pp]
        for label,off,old,new in pp:
            f.seek(off);actual=f.read(len(old))
            if actual!=old:raise ValueError(f'guard failed: {label} {off:X}')
        print('CURRENT hash and all six byte guards passed.',flush=True)
        if not args.build:return
        try:
            for label,off,old,new in pp:f.seek(off);f.write(new)
            f.flush();os.fsync(f.fileno())
            after=stream_sha(f)
            if after!=TARGET:raise ValueError(f'Post-write hash differs: {after}')
        except Exception:
            for label,off,old,new in pp:f.seek(off);f.write(old)
            f.flush();os.fsync(f.fileno())
            if stream_sha(f)!=before:raise RuntimeError('Rollback verification failed')
            raise
    changed=sum(sum(x!=y for x,y in zip(old,new)) for _,_,old,new in pp)
    manifest={'source':str(SOURCE),'output':str(SOURCE),'mode':'in-place','source_sha256':before,'output_sha256':after,
              'changed_bytes':changed,'keys':{'Soulgain':hex(SOUL),'Ashsaber':hex(ASH)},
              'patches':[{'label':l,'offset':hex(o),'before':b.hex(' '),'after':a.hex(' ')} for l,o,b,a in pp],
              'live_verified':False,'user_saves_modified':False}
    dest=ROOT/'runtime/ashsaber_verified_acquisition_manifest.json'
    dest.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(manifest,indent=2,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
