"""Small fail-closed scalar R5900 interpreter for offline allocator checks.

Executes game code from an EE snapshot, not replacements for game functions.
Unsupported instructions fail with their PC. No access to a running emulator.
"""
import struct
from collections import Counter

MASK64=(1<<64)-1
MASK128=(1<<128)-1
def signed(v,bits=64):
    v &= (1<<bits)-1
    return v-(1<<bits) if v>>(bits-1) else v

class CPU:
    def __init__(self,ram):
        self.mem=bytearray(ram)
        self.r=[0]*32
        self.r[28]=0x5879F0  # executable's global pointer
        self.lo=self.hi=0
        self.fpr=[0]*32
        self.fcc=False
        self.pc=0
        self.pending=None
        self.count=0
        self.visits=Counter()
        self.writes=[]
    def read(self,a,n):
        a &= 0xFFFFFFFF
        if a+n>len(self.mem): raise RuntimeError(f'read {a:X}/{n} at {self.pc:X}')
        return int.from_bytes(self.mem[a:a+n],'little')
    def write(self,a,v,n):
        a &= 0xFFFFFFFF
        if a+n>len(self.mem): raise RuntimeError(f'write {a:X}/{n} at {self.pc:X}')
        self.mem[a:a+n]=(v&((1<<(n*8))-1)).to_bytes(n,'little')
        self.writes.append((a,n,self.pc))
    def put(self,i,v,bits=64):
        if i: self.r[i]=(self.r[i]&(~((1<<bits)-1)&MASK128))|(v&((1<<bits)-1))
    def run(self,pc,args=(),limit=2000000,stop=0x600000):
        self.r[29]=0x1F00000
        self.r[31]=stop
        for i,x in enumerate(args,4): self.r[i]=x
        self.pc=pc;self.pending=None; self.count=0
        while self.pc != stop:
            if self.count>=limit: raise RuntimeError(f'step limit PC={self.pc:X}')
            self.step()
        return signed(self.r[2])
    def step(self):
        pc=self.pc; w=self.read(pc,4)
        self.visits[pc]+=1; self.count+=1
        op=w>>26; s=(w>>21)&31; t=(w>>16)&31; d=(w>>11)&31; sh=(w>>6)&31; fn=w&63
        a=self.r[s]&MASK64; b=self.r[t]&MASK64
        imm=w&65535; sim=signed(imm,16); addr=(a+sim)&0xFFFFFFFF
        target=self.pending; self.pending=None; nextpc=pc+4
        def put(v,bits=64): self.put(d,v,bits)
        def branch(taken,likely=False):
            nonlocal nextpc
            if taken: self.pending=pc+4+(sim<<2)
            elif likely: nextpc=pc+8
        if op==0:
            if fn==0: put(signed(b<<sh,32))
            elif fn==2: put(signed((b&0xFFFFFFFF)>>sh,32))
            elif fn==3: put(signed(b,32)>>sh)
            elif fn==4: put(signed(b<<(a&31),32))
            elif fn==6: put(signed((b&0xFFFFFFFF)>>(a&31),32))
            elif fn==7: put(signed(b,32)>>(a&31))
            elif fn in (8,9):
                self.pending=a&0xFFFFFFFF
                if fn==9: put(pc+8)
            elif fn==10:
                if b==0: put(a)
            elif fn==11:
                if b!=0: put(a)
            elif fn==16: put(self.hi)
            elif fn==18: put(self.lo)
            elif fn in (24,25):
                v=(signed(a,32)*signed(b,32)) if fn==24 else ((a&0xFFFFFFFF)*(b&0xFFFFFFFF))
                self.lo=signed(v,32)&MASK64; self.hi=signed(v>>32,32)&MASK64
                if d: put(self.lo)
            elif fn in (26,27):
                x,y=(signed(a,32),signed(b,32)) if fn==26 else (a&0xFFFFFFFF,b&0xFFFFFFFF)
                if not y: raise RuntimeError('division by zero')
                q=(abs(x)//abs(y))*(-1 if (x<0)!=(y<0) else 1)
                self.lo=signed(q,32)&MASK64;self.hi=signed(x-q*y,32)&MASK64
            elif fn in (32,33): put(signed(a+b,32))
            elif fn in (34,35): put(signed(a-b,32))
            elif fn==36: put(a&b)
            elif fn==37: put(a|b)
            elif fn==38: put(a^b)
            elif fn==39: put(~(a|b))
            elif fn==42: put(int(signed(a)<signed(b)))
            elif fn==43: put(int(a<b))
            elif fn in (44,45): put(a+b)
            elif fn in (46,47): put(a-b)
            elif fn in (56,58,59,60,62,63):
                n=sh+(32 if fn>=60 else 0)
                put((b<<n) if fn in (56,60) else ((b>>n) if fn in (58,62) else signed(b)>>n))
            else: raise NotImplementedError(f'{pc:08X}: {w:08X}')
        elif op==1:
            if t not in (0,1,2,3,16,17): raise NotImplementedError(f'REGIMM {pc:X}/{t}')
            yes=signed(a)<0 if t in (0,2,16) else signed(a)>=0
            if t>=16: self.put(31,pc+8)
            branch(yes,t in (2,3))
        elif op in (2,3):
            self.pending=((pc+4)&0xF0000000)|((w&0x3FFFFFF)<<2)
            if op==3:self.put(31,pc+8)
        elif op in (4,5,6,7,20,21,22,23):
            k=op&15
            branch({4:a==b,5:a!=b,6:signed(a)<=0,7:signed(a)>0}[k],op>=20)
        elif op in (8,9): self.put(t,signed(a+sim,32))
        elif op==10:self.put(t,int(signed(a)<sim))
        elif op==11:self.put(t,int(a<(sim&MASK64)))
        elif op==12:self.put(t,a&imm)
        elif op==13:self.put(t,a|imm)
        elif op==14:self.put(t,a^imm)
        elif op==15:self.put(t,signed(imm<<16,32))
        elif op in (24,25):self.put(t,a+sim)
        elif op in (30,32,33,35,36,37,39,55):
            n={30:16,32:1,33:2,35:4,36:1,37:2,39:4,55:8}[op]
            v=self.read(addr,n)
            if op in (32,33,35):v=signed(v,8*n)
            self.put(t,v,128 if op==30 else 64)
        elif op==17:
            def f(i): return struct.unpack('<f',struct.pack('<I',self.fpr[i]))[0]
            def sf(i,v): self.fpr[i]=struct.unpack('<I',struct.pack('<f',v))[0]
            if s==0: self.put(t,signed(self.fpr[d],32))
            elif s==4: self.fpr[d]=b&0xFFFFFFFF
            elif s==8:
                if t not in (0,1,2,3): raise NotImplementedError(f'COP1 branch {pc:X}')
                branch(self.fcc if t&1 else not self.fcc, bool(t&2))
            elif s==20 and fn==32: sf(sh,float(signed(self.fpr[d],32)))
            elif s==16:
                if fn==6: self.fpr[sh]=self.fpr[d]
                elif fn==32: self.fpr[sh]=self.fpr[d]
                elif fn==13: self.fpr[sh]=int(f(d))&0xFFFFFFFF
                elif fn in (0,1,2,3): sf(sh,{0:lambda:f(d)+f(t),1:lambda:f(d)-f(t),2:lambda:f(d)*f(t),3:lambda:f(d)/f(t)}[fn]())
                elif fn in (50,60,62): self.fcc={50:lambda:f(d)==f(t),60:lambda:f(d)<f(t),62:lambda:f(d)<=f(t)}[fn]()
                else: raise NotImplementedError(f'COP1.S {pc:X}/{w:X}')
            else: raise NotImplementedError(f'COP1 {pc:X}/{w:X}')
        elif op==49:self.fpr[t]=self.read(addr,4)  # lwc1, bit-preserving
        elif op==57:self.write(addr,self.fpr[t],4) # swc1, bit-preserving
        elif op in (31,40,41,43,63):
            n={31:16,40:1,41:2,43:4,63:8}[op]
            self.write(addr,self.r[t],n)
        else: raise NotImplementedError(f'{pc:08X}: {w:08X}')
        self.r[0]=0
        self.pc=target if target is not None else nextpc
