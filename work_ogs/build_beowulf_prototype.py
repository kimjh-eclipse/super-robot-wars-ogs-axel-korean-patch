"""Separate Mk-III/Riese animation prototype. Never writes the release ISO.

New animation resources are appended inside BATTLE's verified zero tail.
Original payloads remain byte-identical, including the displaced directory's
first animation resource. The generated atlas is converted to native indexed
pages; commands, UVs, transforms, dimensions and alpha masks stay native.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, struct, sys
import numpy as np
from PIL import Image
from ogs_korean_codec import encode, decode
from build_hidden_rewards import Scripts, MAP

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'build/SRWOGS_K.iso'
OUT=ROOT/'build/SRWOGS_BEOWULF_TEST.iso'
ART=ROOT/'runtime/beowulf'
BATTLE=0x2511F800
TAIL=0x85A7B800
LIMIT=0x87D1F800
BANK=227
PILOT=0x603
UNIT=0x604
FACE=223
SWIZZLE=np.array([(i&~24)|((i&8)<<1)|((i&16)>>1) for i in range(256)])

def sha(b): return hashlib.sha256(b).hexdigest()
def read(f,at,n):
    f.seek(at);b=f.read(n);assert len(b)==n;return b
def u16(b,p=0):return struct.unpack_from('<H',b,p)[0]
def u32(b,p=0):return struct.unpack_from('<I',b,p)[0]

def small_beowulf_portrait(f,faces):
    """Native evil face 18, converted to the status portrait's native size."""
    large=faces.get(f,58*32+18)
    assert len(large)==1024+112*112
    pixels=np.frombuffer(large[1024:],np.uint8).reshape(112,112)
    # Native large portraits use a112-pixel storage pitch but a100x100
    # visible face. Scaling the padded canvas leaves a14-pixel empty border.
    palette=np.frombuffer(large[:1024],np.uint8).reshape(256,4)[SWIZZLE]
    assert not np.any(palette[pixels[100:,:],3])
    assert not np.any(palette[pixels[:,100:],3])
    nearest=np.arange(128)*100//128
    resized=pixels[nearest[:,None],nearest[None,:]]
    return large[:1024]+resized.tobytes()

class Asm:
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

def retirement_hook(f):
    """Reclaim a redundant startup initializer, preserving its exact results."""
    start,end=0x200104,0x200270
    elf=lambda pc:0x94880+pc-0x100000
    old=read(f,elf(start),end-start)
    assert u32(old)==0x3C07004A and u32(old,len(old)-4)==0x3C090054
    a=Asm(start)
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
    hook=start+len(a.words)*4
    h=Asm(hook)
    h.i(0x23,18,8,8);h.i(15,0,9,1);h.i(13,9,9,0xa5)
    h.branch(5,8,9,'end');h.emit(0)
    h.i(0x23,18,8,12);h.i(9,0,9,0x41f)
    h.branch(5,8,9,'end');h.emit(0)
    h.move(4,19);h.i(15,0,5,1);h.i(13,5,5,0xa5)
    h.jump(0x2B7330,True);h.i(9,0,6,PILOT)
    h.i(0x23,2,8,0x18);h.branch(1,8,0,'end');h.emit(0)
    h.move(17,2);h.jump(0x1E87B0,True);h.move(4,17)
    h.i(0x23,19,4,0x310c);h.i(15,0,1,4);h.i(13,1,1,0x4e00)
    h.emit(4<<21|1<<16|4<<11|0x21);h.move(5,17)
    h.jump(0x1DFB30,True);h.i(9,0,6,0xce)
    # Hook the common join, including the native "Alfimi is already absent"
    # path. Hooking 2D8C1C alone lets that branch bypass companion cleanup.
    h.label('end');h.i(15,0,2,1);h.i(15,0,3,1)
    h.jump(0x2D8C28);h.emit(19<<21|3<<16|3<<11|0x21)
    code=(a.data()+h.data()).ljust(end-start,b'\0')
    assert len(code)==end-start
    site=0x2D8C20
    assert read(f,elf(site),8)==struct.pack('<II',0x0060102d,0x02631821)
    return [(elf(start),code,'Compact startup initializer and Alfimi-linked retreat helper'),
            (elf(site),struct.pack('<II',2<<26|hook>>2,0),'Alfimi disappearance also retires Beowulf')],hook

class Archive:
    def __init__(self,f,base):
        self.base=base
        h=read(f,base,16);assert h[:4]==b'LICE'
        self.di,self.count,self.slots=struct.unpack_from('<III',h,4)
        self.mapping=list(struct.unpack('<%dH'%self.slots,read(f,base+16,self.slots*2)))
        self.directory=base+self.di
        h=read(f,self.directory,8+self.count*8)
        assert h[:4]==b'Wpbb' and u32(h,4)==self.count
        self.entries=[(self.directory+u32(h,8+i*8),u32(h,12+i*8)) for i in range(self.count)]
    def get(self,f,key):
        idx=self.mapping[key];assert idx!=0xffff
        at,n=self.entries[idx];return read(f,at,n)

def pages(b):
    """Native RGBA32 CSM1 palettes and linear PSMT8 256-wide pages."""
    desc=struct.unpack_from('<20H',b,24);flags=u32(b,8)
    found=[]
    for slot,d in enumerate(desc):
        if not d:continue
        at=d*256;h=256 if flags&(1<<slot) else 128
        assert at>=64 and at+1024+256*h<=len(b),(slot,hex(at),h,len(b))
        p=np.frombuffer(b[at:at+1024],np.uint8).reshape(256,4)[SWIZZLE].copy()
        p[:,3]=np.minimum(p[:,3].astype(np.uint16)*2,255)
        indices=np.frombuffer(b[at+1024:at+1024+256*h],np.uint8).reshape(h,256)
        found.append((slot,at,p[indices].copy()))
    assert len(found)==u16(b,6),(len(found),u16(b,6))
    return found

def components(mask):
    """Native disconnected part boxes, not AI-repositioned bounding boxes."""
    seen=np.zeros_like(mask);out=[]
    for y,x in zip(*np.where(mask)):
        if seen[y,x]:continue
        todo=[(y,x)];seen[y,x]=True;pts=[]
        while todo:
            yy,xx=todo.pop();pts.append((yy,xx))
            for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                ny,nx=yy+dy,xx+dx
                if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=True;todo.append((ny,nx))
        if len(pts)>=12:
            yy,xx=zip(*pts);out.append((min(xx),min(yy),max(xx)+1,max(yy)+1))
    return out

class Skin:
    def __init__(self,source):
        self.source=source
        gen=np.array(Image.open(ART/'mk3_atlas_generated.png').convert('RGBA').resize((256,256),Image.Resampling.LANCZOS))
        a=source[:,:,3]>128;b=gen[:,:,3]>128
        self.alpha_iou=float(np.count_nonzero(a&b)/np.count_nonzero(a|b))
        assert self.alpha_iou>.70,'Generated sheet no longer matches its source layout'
        self.generated=gen
        # Exact native alpha and rectangles are required by existing UVs.
        self.converted=gen.copy();self.converted[:,:,3]=source[:,:,3]
        missing=a&~b
        self.converted[missing,:3]=source[missing,:3]
        self.boxes=components(a)
        self.lut={}
        for rgb in np.unique(source[a,:3],axis=0):
            hits=np.all(source[:,:,:3]==rgb,axis=2)&a&b
            if hits.any():self.lut[tuple(rgb)]=np.median(gen[hits,:3],axis=0).astype(np.uint8)
        self.cache={};self.stats={'pages':0,'part_matches':0,'palette_pages':0}

    def page(self,im,base=False):
        if base:return self.converted.copy()
        key=sha(im.tobytes())
        if key in self.cache:return self.cache[key]
        result=im.copy();opaque=im[:,:,3]>0
        colors=np.unique(im[opaque,:3],axis=0)
        overlap=sum(tuple(c) in self.lut for c in colors)/max(len(colors),1)
        # Do not recolour explosion or beam palettes unrelated to the body.
        if overlap>.55:
            for c in colors:
                mapped=self.lut.get(tuple(c))
                if mapped is not None:result[np.all(im[:,:,:3]==c,axis=2)&opaque,:3]=mapped
            self.stats['palette_pages']+=1
        for x0,y0,x1,y1 in self.boxes:
            part=self.source[y0:y1,x0:x1];mask=part[:,:,3]>128
            yy,xx=np.where(mask)
            if len(xx)<20:continue
            # Pick an uncommon native pixel as the exact-match anchor.
            samples=np.linspace(0,len(xx)-1,min(12,len(xx)),dtype=int)
            anchor=min(samples,key=lambda j:np.count_nonzero(np.all(im==part[yy[j],xx[j]],axis=2)))
            ay,ax=yy[anchor],xx[anchor]
            ys,xs=np.where(np.all(im==part[ay,ax],axis=2))
            for py,px in zip(ys,xs):
                ty,tx=int(py-ay),int(px-ax);h,w=mask.shape
                if ty<0 or tx<0 or ty+h>im.shape[0] or tx+w>im.shape[1]:continue
                patch=im[ty:ty+h,tx:tx+w]
                if np.mean(np.all(patch[mask]==part[mask],axis=1))>.99:
                    replacement=self.converted[y0:y1,x0:x1]
                    result[ty:ty+h,tx:tx+w][mask]=replacement[mask]
                    self.stats['part_matches']+=1
        assert np.array_equal(result[:,:,3],im[:,:,3])
        self.stats['pages']+=1;self.cache[key]=result
        return result

    def asset(self,b,base=False):
        cache=ART/'converted';cache.mkdir(exist_ok=True)
        cp=cache/(sha(b+self.generated.tobytes()+bytes([base]))+'.bin')
        if cp.exists():return cp.read_bytes()
        out=bytearray(b);ranges=[]
        for slot,at,im in pages(b):
            new=self.page(im,base=base and slot==0)
            # Quantize to <=255 opaque colours, reserve index zero for alpha.
            alpha=new[:,:,3];opaque=alpha>0
            rgb=Image.fromarray(new[:,:,:3])
            quant=rgb.quantize(colors=255,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
            idx=np.array(quant,dtype=np.uint8).astype(np.uint16)+1
            idx[~opaque]=0;idx=idx.astype(np.uint8)
            palette=np.zeros((256,4),np.uint8)
            pal=np.array(quant.getpalette(),np.uint8).reshape(-1,3)
            palette[1:1+len(pal),:3]=pal
            palette[1:,3]=128
            # Source alpha is binary for these body pages.
            assert set(np.unique(alpha))<={0,255},'Native partial alpha needs a different encoder'
            rawpal=palette[SWIZZLE]
            out[at:at+1024]=rawpal.tobytes()
            out[at+1024:at+1024+idx.size]=idx.tobytes()
            ranges.append((at,at+1024+idx.size))
        # The executable animation program itself must remain byte-for-byte.
        pos=0
        for start,end in sorted(ranges):assert out[pos:start]==b[pos:start];pos=end
        assert out[pos:]==b[pos:]
        assert len(out)==len(b)
        cp.write_bytes(out)
        return bytes(out)

    def palette_safe_asset(self,b):
        """Keep native indices/CLUT slots/alpha; recolour body RGB only.

        Animation streams can address the native palette directly. Requantizing
        a page is therefore not equivalent to preserving its decoded RGBA mask.
        """
        out=bytearray(b);body=0;cutin=0
        for slot,at,im in pages(b):
            raw=np.frombuffer(b[at:at+1024],np.uint8).reshape(256,4).copy()
            palette=raw[SWIZZLE].copy()
            opaque=palette[:,3]>0;rgb=palette[:,:3]
            colors=rgb[opaque]
            overlap=sum(tuple(c) in self.lut for c in colors)/max(len(colors),1)
            # Native close-up sheets have a dense 241-colour body palette.
            # Effects use separate sparse palettes; do not recolour them.
            closeup=len(np.unique(raw,axis=0))==241 and np.mean(im[:,:,3]>0)>.25
            if overlap>.55:
                for i,c in enumerate(rgb):
                    if opaque[i] and tuple(c) in self.lut:palette[i,:3]=self.lut[tuple(c)]
                body+=1
            elif closeup:
                for i,(rr,gg,bb) in enumerate(rgb.astype(int)):
                    if not opaque[i]:continue
                    if rr>gg*1.3 and rr>bb*1.15 and rr-gg>=10:
                        value=max(rr*.60,rr*.25+gg*.5+bb*.25)
                        palette[i,:3]=np.clip([value*.85,value*.92,value],0,255).astype(np.uint8)
                    elif rr>bb*1.5 and gg>rr*.55 and rr>40:
                        palette[i,:3]=[rr,min(255,int(gg*.75)),min(bb,int(rr*.18))]
                cutin+=1
            else:continue
            out[at:at+1024]=palette[SWIZZLE].tobytes()
            assert out[at+3:at+1024:4]==b[at+3:at+1024:4]
        # This protects every command, UV, image index and non-body effect byte.
        allowed=np.zeros(len(b),dtype=bool)
        for slot,at,im in pages(b):
            for ch in (0,1,2):allowed[at+ch:at+1024:4]=True
        diff=np.frombuffer(b,np.uint8)!=np.frombuffer(out,np.uint8)
        assert not np.any(diff&~allowed)
        return bytes(out),body,cutin

class Plan:
    def __init__(self,f):self.f=f;self.edits=[];self.cursor=TAIL
    def add(self,at,new,label):
        old=read(self.f,at,len(new))
        if old!=new:self.edits.append((at,old,bytes(new),label))
    def alloc(self,b,label):
        at=(self.cursor+2047)//2048*2048
        assert at+len(b)<=LIMIT,'BATTLE tail capacity exceeded'
        assert not any(read(self.f,at,len(b))),label
        self.add(at,b,label);self.cursor=at+len(b);return at
    def archive(self,a,additions,move_first=False):
        entries=list(a.entries);mapping=list(a.mapping)
        di=a.di+0x800 if move_first else a.di
        if move_first:
            oldat,n=entries[0];at=self.alloc(read(self.f,oldat,n),'relocated unchanged attack asset 0')
            entries[0]=(at,n)
        for key,data,label in additions:
            while len(mapping)<=key:mapping.append(0xffff)
            assert mapping[key]==0xffff
            mapping[key]=len(entries);entries.append((self.alloc(data,label),len(data)))
        assert 16+len(mapping)*2<=di
        d=bytearray(b'Wpbb'+struct.pack('<I',len(entries)))
        for at,n in entries:
            assert at>=a.base+di
            d.extend(struct.pack('<II',at-a.base-di,n))
        directory_end=a.base+di+len(d)
        assert all(at>=directory_end or at+n<=a.base+di for at,n in entries),'directory overlaps an asset'
        self.add(a.base+4,struct.pack('<III',di,len(entries),len(mapping)),'LICE directory/counts')
        self.add(a.base+16,struct.pack('<%dH'%len(mapping),*mapping),'LICE logical resource map')
        self.add(a.base+di,d,'Wpbb directory, original resources preserved')
        return max(at+n for at,n in entries)-a.base

def plan(source=SOURCE):
    with source.open('rb') as f:
        p=Plan(f);actor=Archive(f,0x27D66800);attack=Archive(f,0x2970D000)
        master=read(f,0x5DA000,0x190000)
        assert all(u16(master,0x11F8A4+i*100+0x44)!=BANK for i in range(427))
        assert actor.mapping[BANK]==0xffff
        assert not any(read(f,0x859F9000+BANK*144,144))
        native_actor=actor.get(f,42)
        skin=Skin(pages(native_actor)[0][2])
        actor_size=p.archive(actor,[(BANK,skin.asset(native_actor,base=True),'Mk-III idle/evade/body resource')])
        row=read(f,0x859F9000+42*144,144)
        assetids=sorted(set(k for k in struct.unpack_from('<70H',row,4) if k!=0xffff))
        newids={old:attack.slots+i for i,old in enumerate(assetids)}
        additions=[(newids[k],skin.palette_safe_asset(attack.get(f,k))[0],f'Mk-III clone of Riese animation {k}') for k in assetids]
        attack_size=p.archive(attack,additions,move_first=True)
        p.add(0x25120000+8+1*8+4,struct.pack('<I',actor_size),'BATTLE body archive span')
        p.add(0x25120000+8+2*8+4,struct.pack('<I',attack_size),'BATTLE animation archive span')
        newrow=bytearray(row)
        for i,k in enumerate(struct.unpack_from('<70H',row,4)):
            if k!=0xffff:struct.pack_into('<H',newrow,4+i*2,newids[k])
        p.add(0x859F9000+BANK*144,newrow,'Independent Mk-III animation bank')
        # The game's own expression 18/19 is the sinister Beowulf face in
        # the supplied screenshot. Alias a new face group; leave Kyosuke's
        # original expressions, textures and lookup entries untouched.
        faces=Archive(f,0x1A2F3000);small=Archive(f,0x1B12D800)
        mapping=faces.mapping+[0xffff]*(32*(FACE+1)-faces.slots)
        assert all(x==0xffff for x in mapping[FACE*32:(FACE+1)*32])
        for i in range(32):mapping[FACE*32+i]=faces.mapping[58*32+(19 if i in (1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31) else 18)]
        # Scenario portraits have a separate 760-byte expression lookup row.
        # Image aliases alone work in status/battle UI but leave event faces blank.
        expression_base=0x1e7ee000
        expression_row=bytearray(read(f,expression_base+58*760,760))
        assert not any(read(f,expression_base+FACE*760,760))
        normal,talking=struct.unpack_from('<2H',expression_row,18*2)
        assert (normal,talking)==(348,349)
        for i in range(32):struct.pack_into('<H',expression_row,i*2,talking if i%2 else normal)
        p.add(expression_base+FACE*760,expression_row,'Separate scenario portrait expression lookup')
        gpos=0x24BA1000;oldpos,n=faces.entries[0]
        original_face0=read(f,oldpos,n)
        assert not any(read(f,gpos,n)) and gpos+n<0x2511F800
        p.add(gpos,original_face0,'Relocated unchanged blank face 0 inside GRAPHIC padding')
        face_entries=list(faces.entries);face_entries[0]=(gpos,n)
        newdi=faces.di+0x800
        directory=b'Wpbb'+struct.pack('<I',faces.count)+b''.join(struct.pack('<II',at-faces.base-newdi,z) for at,z in face_entries)
        assert 16+len(mapping)*2<=newdi
        assert all(at>=faces.base+newdi+len(directory) for at,z in face_entries)
        p.add(faces.base+4,struct.pack('<III',newdi,faces.count,len(mapping)),'Expanded portrait lookup header')
        p.add(faces.base+16,struct.pack('<%dH'%len(mapping),*mapping),'New Beowulf large portrait aliases')
        p.add(faces.base+newdi,directory,'Rebased unchanged portrait payload directory')
        p.add(0x17020000+8+1*8+4,struct.pack('<I',max(at+z for at,z in face_entries)-faces.base),'GRAPHIC portrait archive span')
        small_payload=small_beowulf_portrait(f,faces)
        small_at=(gpos+len(original_face0)+2047)//2048*2048
        assert not any(read(f,small_at,len(small_payload)))
        p.add(small_at,small_payload,'Native sinister Beowulf status portrait')
        sm=small.mapping+[0xffff]*(10*(FACE+1)-small.slots)
        for i in range(10):sm[FACE*10+i]=small.count
        assert 16+len(sm)*2<=small.di
        assert small.directory+8+(small.count+1)*8<=min(at for at,n in small.entries)
        p.add(small.base+8,struct.pack('<I',small.count+1),'Small portrait archive physical count')
        p.add(small.directory+4,struct.pack('<I',small.count+1),'Small portrait directory count')
        p.add(small.directory+8+small.count*8,struct.pack('<II',small_at-small.directory,len(small_payload)),'New Beowulf status portrait entry')
        p.add(0x17020000+8+2*8+4,struct.pack('<I',small_at+len(small_payload)-small.base),'GRAPHIC small portrait archive span')
        p.add(small.base+12,struct.pack('<I',len(sm)),'Expanded small portrait lookup count')
        p.add(small.base+16,struct.pack('<%dH'%len(sm),*sm),'Beowulf small portrait aliases, native evil expression')
        for base in (0x5DA000,0x83F000):
            m=read(f,base,0x190000)
            assert u16(m,0x11E898+UNIT*2)==u16(m,0x13A484+PILOT*2)==0xffff
            assert all(u16(m,0x13A484+k*2)!=381 for k in range(2048))
            p.add(base+0x11E898+UNIT*2,struct.pack('<H',0x19F),'New Mk-III unit alias')
            p.add(base+0x13A484+PILOT*2,struct.pack('<H',381),'Separate Beowulf pilot alias')
            mk=bytearray(m[0x11F8A4+0x19F*100:0x11F8A4+(0x19F+1)*100])
            mk[0x24:0x44]=m[0x11F8A4+0x44*100+0x24:0x11F8A4+0x44*100+0x44]
            # No Excellen co-attacker is available to the enemy boss.
            struct.pack_into('<H',mk,0x24+5*2,0xffff)
            struct.pack_into('<H',mk,0,50000)
            struct.pack_into('<H',mk,0x18,140)
            struct.pack_into('<H',mk,0x1A,2300)
            struct.pack_into('<H',mk,0x20,300)
            struct.pack_into('<H',mk,0x44,BANK)
            p.add(base+0x11F8A4+0x19F*100,mk,'Arm native event Mk-III; preserve its model/name/stats')
            # Fihx explicitly points to Strg and Expl, leaving verified Strg slack.
            st=0x155BFC;size=u32(m,st+4);count=u32(m,st+8)
            assert m[st:st+4]==b'Strg' and count in (1806,1807)
            pointers=struct.unpack_from('<%dI'%count,m,st+12)
            pool=m[st+12+count*4:st+size]
            name=encode('베오울프　쿄스케')+b'\0'
            textoff=size+4
            s=bytearray(b'Strg'+struct.pack('<II',size+4+len(name),count+1))
            s.extend(struct.pack('<%dI'%(count+1),*[x+4 for x in pointers],textoff));s.extend(pool);s.extend(name)
            expl=0x11E800+u32(m,0x11E800+0x84)
            assert m[expl:expl+4]==b'Expl'
            delta=max(0,(st+len(s)-expl+3)//4*4)
            if delta:
                end=0x11E800+u32(m,0x11E000+12)
                assert end+delta<=0x1A5800 and not any(read(f,base+end,delta))
                p.add(base+expl+delta,read(f,base+expl,end-expl),'Relocate following master tables inside entry padding')
                for pointer in range(0x18,0x8C,4):
                    v=u32(m,0x11E800+pointer)
                    if v>=expl-0x11E800:
                        p.add(base+0x11E800+pointer,struct.pack('<I',v+delta),'Fihx table relocation pointer')
                p.add(base+0x11E000+12,struct.pack('<I',u32(m,0x11E000+12)+delta),'Nested master payload size')
            else:
                assert not any(m[st+size:st+len(s)])
            for i,ptr in enumerate(pointers):
                new=u32(s,12+i*4)
                assert m[st+ptr:m.find(b'\0',st+ptr)+1]==s[new:s.find(b'\0',new)+1]
            p.add(base+st,s,'Extend string table within verified slack; all original strings identical')
            pilot=bytearray(m[0x13B490+114*148:0x13B490+115*148])
            struct.pack_into('<3H',pilot,4,count,count,count)
            for off in (0x48,0x58,0x5A,0x5C,0x5E):
                assert u16(pilot,off)==58
                struct.pack_into('<H',pilot,off,FACE)
            p.add(base+0x13B490+381*148,pilot,'Separate named Beowulf, normal Kyosuke unchanged')
        s=Scripts(source);wp=0x5071000;spawn=[];map_cursor=0x8DDE000
        for table in range(u32(s.data,wp+4)):
            dp=wp+8+table*8;at=wp+u32(s.data,dp);size=u32(s.data,dp+4)
            if s.data[at:at+4]!=b'UNTD':continue
            count=u32(s.data,at+40)
            if size!=44+count*336:
                assert table==49,'Unexpected nonstandard UNTD layout'
                continue
            original=s.data[at:at+size];rows=[]
            for i in range(count):
                row=bytearray(original[44+i*336:44+(i+1)*336])
                if u32(row,0x20)!=0x41F or u32(row,8) not in (2,3):continue
                group=u32(row,4);x,y=u32(row,16),u32(row,20)
                occupied={(u32(original,44+j*336+16),u32(original,44+j*336+20)) for j in range(count) if u32(original,44+j*336+4)==group}
                candidates=[(x+1,y),(x-1,y),(x,y+1),(x,y-1)]
                xy=next((q for q in candidates if q not in occupied and min(q)>=0),None)
                assert xy is not None
                for off,value in ((0,UNIT),(16,xy[0]),(20,xy[1]),(32,PILOT)):
                    struct.pack_into('<I',row,off,value)
                rows.append(row)
                spawn.append(dict(table=table,original_alfimi_row=i,group=group,side=u32(row,8),
                                  difficulty_bits=u32(row,52),position=list(xy),
                                  stage_resource_name=original[24:32].split(b'\0')[0].decode('ascii')))
            if not rows:continue
            data=bytearray(original);data.extend(b''.join(rows));struct.pack_into('<I',data,40,count+len(rows))
            nxt=wp+u32(s.data,dp+8) if table+1<u32(s.data,wp+4) else 0x557E800
            if len(data)<=nxt-at:
                assert not any(s.data[at+size:at+len(data)])
                p.add(MAP+at,data,f'Beowulf accompanies every enemy Alfimi group, UNTD {table}')
            else:
                map_cursor=(map_cursor+2047)//2048*2048
                assert not any(s.data[map_cursor:map_cursor+len(data)])
                p.add(MAP+map_cursor,data,f'Relocated expanded UNTD {table}')
                p.add(MAP+dp,struct.pack('<I',map_cursor-wp),'Expanded UNTD directory offset')
                map_cursor+=len(data)
            p.add(MAP+dp+4,struct.pack('<I',len(data)),'Expanded UNTD directory length')
        assert spawn
        if map_cursor>0x8DDE000:
            p.add(MAP+0x800+8+13*8+4,struct.pack('<I',map_cursor-0x5070000),'MAP unit archive expanded span')
        hooks,hook=retirement_hook(f)
        for at,data,label in hooks:p.add(at,data,label)
        (ART/'enemy_spawn_plan.json').write_text(json.dumps(spawn,ensure_ascii=False,indent=2),encoding='utf-8')
        p.edits.sort(key=lambda x:x[0])
        for a,b in zip(p.edits,p.edits[1:]):assert a[0]+len(a[1])<=b[0],(a[3],b[3])
        report={'source':str(source),'output':str(OUT),'bank':BANK,'unit_key':hex(UNIT),'pilot_key':hex(PILOT),
                'pilot_record':381,'animation_clones':len(additions),'tail_used_bytes':p.cursor-TAIL,
                'art':{'generated_alpha_iou':skin.alpha_iou,**skin.stats},
                'normal_kyosuke_and_riese_records_preserved':True,'spawn_installed':True,
                'enemy_spawn_variants':len(spawn),'enemy_stage_tables':len({x['table'] for x in spawn}),
                'boss_stats':{'HP':50000,'EN':300,'mobility':140,'armor':2300},
                'alfimi_synchronised_retreat_installed':True,'retirement_helper':hex(hook),
                'gpu_playthrough_verified':False,'dedicated_beowulf_voice_recordings':False,
                'beowulf_portrait_group':FACE,'beowulf_large_expressions':[1874,1875],
                'small_portrait_is_native_kyosuke_thumbnail':False,
                'edits':[{'offset':at,'size':len(old),'before_sha256':sha(old),'after_sha256':sha(new),'reason':label} for at,old,new,label in p.edits]}
        return p.edits,report

def episode6_test():
    """Append a test enemy to the existing episode 6 initial enemy group.

    Deliberately independent of plan(): release master tables have since moved.
    No scenario commands, victory conditions or production ISO bytes change.
    """
    expected='78a3e8a7b4e76584dfa344e6755c066a036c851b6fb25d5032d382a7eff451bb'
    manifest=ART/'prototype_manifest.json'
    report=json.loads(manifest.read_text(encoding='utf-8'))
    assert not report.get('episode6_test',{}).get('applied'), 'Episode 6 test already installed'
    with SOURCE.open('rb') as f:
        production_hash=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected, 'Unexpected TEST ISO revision'
        scripts=Archive(f,MAP+0x557E800)
        assert scripts.mapping[1011]==74
        units=Archive(f,MAP+0x5070000)
        matches=[]
        for table,(at,size) in enumerate(units.entries):
            header=read(f,at,44)
            if header[:4]==b'UNTD' and header[24:32].split(b'\0')[0]==b'01011':
                matches.append((table,at,size,header))
        assert len(matches)==1
        table,at,size,header=matches[0]
        assert table==78 and u32(header,40)==40 and size==44+40*336
        original=read(f,at,size)
        row=bytearray(original[44+8*336:44+9*336])
        assert (u32(row),u32(row,4),u32(row,8),u32(row,32),u32(row,52))==(0x423,2,2,0x3E9,0)
        xy=(21,9)
        occupied={(u32(original,44+i*336+16),u32(original,44+i*336+20)) for i in range(40)}
        assert xy not in occupied
        for offset,value in ((0,UNIT),(16,xy[0]),(20,xy[1]),(32,PILOT)):
            struct.pack_into('<I',row,offset,value)
        data=bytearray(original)+row
        struct.pack_into('<I',data,40,41)
        assert at+len(data)<=units.entries[table+1][0]
        before=read(f,at,len(data))
        assert not any(before[size:])
        dp=units.directory+8+table*8+4
        old_size=read(f,dp,4)
        assert u32(old_size)==size
        # Resolve actual native unit/pilot/animation getters against TEST data.
        from validate_hidden_rewards import ram
        from r5900_scalar_check import CPU
        c=CPU(ram)
        c.mem[0x100000:0x49A778]=read(f,0x94880,0x39A778)
        master=u32(ram,0x59D360)
        blob=read(f,0x5DA000,0x190000)
        for offset,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),(0x70,0x12BF7C),(0x88,0x13A478),(0xA0,0x13B484)):
            dest=c.read(master+offset,4);n=u32(blob,rel+4)
            c.mem[dest:dest+n]=blob[rel:rel+n]
        assert c.run(0x1A6690,[master,UNIT])==BANK
        assert c.run(0x1A7D40,[master,UNIT])==50000
        assert c.run(0x1A37C0,[master,PILOT])==1
        assert c.run(0x1A2900,[master,PILOT])==FACE
    edits=[(dp,old_size,struct.pack('<I',len(data))),(at,before,bytes(data))]
    edits.sort()
    test=dict(applied=False,source_sha256=expected,production_sha256=production_hash,
              logo=74,script_logical_id=1011,unit_table=table,group=2,side=2,
              unit_key=hex(UNIT),pilot_key=hex(PILOT),position=list(xy),difficulty_bits=0,
              original_rows=40,test_rows=41,scenario_commands_unchanged=True,
              native_unit_pilot_face_HP_bank_verified=True,gpu_playthrough_verified=False,
              edits=[dict(offset=p,before=b.hex(),after=a.hex()) for p,b,a in edits])
    report['episode6_test']=test
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for pos,b,a in edits:
                assert read(f,pos,len(b))==b
                f.seek(pos);f.write(a)
            f.flush()
            # Invert only our edits while hashing to prove every other byte is preserved.
            f.seek(0);inverse=hashlib.sha256();target=hashlib.sha256();pos=0
            for start,b,a in edits:
                while pos<start:
                    part=f.read(min(4<<20,start-pos));assert part
                    inverse.update(part);target.update(part);pos+=len(part)
                assert f.read(len(a))==a
                inverse.update(b);target.update(a);pos+=len(a)
            while part:=f.read(4<<20):inverse.update(part);target.update(part)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==production_hash
    except Exception:
        with OUT.open('r+b') as f:
            for pos,b,a in edits:f.seek(pos);f.write(b)
        raise
    test.update(applied=True,target_sha256=target.hexdigest(),
                all_other_TEST_bytes_preserved=True,production_ISO_unchanged=True)
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in test.items() if k!='edits'},ensure_ascii=False,indent=2))


def shishio_power(apply=False):
    """Give Beowulf an independent 4800-power Shishio; common weapon unchanged."""
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='0d112afc54c4c7158b189e3b5d3af4ea00e0f1cb396bb598f727786b7fb93c09'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    edits=[]
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        for base in (0x5da000,0x83f000):
            old=read(f,base,0x1a5800);h=0x11e800;end=h+u32(old,0x11e00c)
            ut,unit,wt,weap=[h+u32(old,h+x) for x in (0x18,0x1c,0x20,0x24)]
            assert u16(old,ut+12+UNIT*2)==427 and u32(old,weap+8)==1633
            assert u16(old,wt+12+0xf85*2)==65535 and u16(old,wt+12+0x5e9*2)==0x60b
            slot=unit+12+427*100+0x24+10;assert u16(old,slot)==0x5e9
            rec=bytearray(old[weap+12+0x60b*36:weap+12+(0x60b+1)*36]);assert u16(rec,8)==4400
            struct.pack_into('<H',rec,8,4800);wend=weap+u32(old,weap+4)
            b=bytearray(old[:end]);b[wend:wend]=rec
            assert len(b)<=len(old) and not any(old[end:len(b)])
            for field in range(0x18,0x8c,4):
                at=h+u32(old,h+field)
                if at>=wend:struct.pack_into('<I',b,h+field,at+36-h)
            struct.pack_into('<II',b,weap+4,u32(old,weap+4)+36,1634)
            struct.pack_into('<H',b,wt+12+0xf85*2,1633);struct.pack_into('<H',b,slot,0xf85)
            struct.pack_into('<I',b,0x11e00c,u32(old,0x11e00c)+36)
            assert b[weap+12:weap+12+1633*36]==old[weap+12:weap+12+1633*36]
            edits.append((base+0x11e000,old[0x11e000:len(b)],bytes(b[0x11e000:])))
            # Run the native weapon getters using the relocated master tables.
            from r5900_scalar_check import CPU
            ram=(ART/'current_user_ram.bin').read_bytes();c=CPU(ram)
            c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
            master=u32(ram,0x59d360);dest=0x1100000;c.mem[dest:dest+len(b[h:])]=b[h:]
            for i,field in enumerate(range(0x18,0x8c,4)):
                at=dest+u32(b,h+field)
                for off,v in ((0,at),(4,c.read(at,4)),(8,c.read(at+4,4)),(12,c.read(at+8,4)),(16,at),(20,at+12)):c.write(master+0x28+i*24+off,v,4)
            assert c.run(0x1a5dc0,[master,0xf85])==4800
            assert c.run(0x1a5dc0,[master,0x5e9])==4400
            assert c.run(0x1a4a20,[master,0xf85])==23
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,
        weapon_key=0xf85,weapon_power=4800,common_weapon_power=4400,native_getters_verified=True,
        edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits])
    if not apply:
        report['shishio_power_prepared']={k:v for k,v in entry.items() if k!='edits'}
        journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report['shishio_power_prepared'],indent=2));return
    report['shishio_power']=entry;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a in edits:assert read(f,off,len(b))==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);target=hashlib.sha256();inverse=hashlib.sha256();pos=0
            for off,b,a in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;target.update(raw);inverse.update(raw);pos+=len(raw)
                assert f.read(len(a))==a;target.update(a);inverse.update(b);pos+=len(a)
            while raw:=f.read(4<<20):target.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2))


def shishio_add(apply=False):
    """Add the existing common Shishio Blade to Beowulf only."""
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='df93c7f0e1b563d8d644c36cc151022ff7d8126063ec0a115c4be5e20319e10d'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    edits=[]
    from r5900_scalar_check import CPU
    ram=(ART/'current_user_ram.bin').read_bytes();c=CPU(ram)
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
        for base in (0x5DA000,0x83F000):
            blob=read(f,base,0x1A5800);h=0x11E800
            ut,units,wt,weap=[h+u32(blob,h+x) for x in (0x18,0x1c,0x20,0x24)]
            idx=u16(blob,ut+12+UNIT*2);assert idx==427
            at=units+12+idx*100+0x24
            assert struct.unpack_from('<16H',blob,at)==tuple(range(0xF80,0xF85))+(65535,)*11
            weapon=u16(blob,wt+12+0x5e9*2);assert weapon==0x60b
            rec=blob[weap+12+weapon*36:weap+12+(weapon+1)*36]
            assert u16(rec,8)==4400 and rec[0x17:0x19]==b'\1\2'
            edits.append((base+at+10,b'\xff\xff',struct.pack('<H',0x5e9)))
        master=u32(ram,0x59d360);dest=0x1100000;c.mem[dest:dest+len(blob[h:])]=blob[h:]
        for i,field in enumerate(range(0x18,0x8c,4)):
            at=dest+u32(blob,h+field)
            for off,v in ((0,at),(4,c.read(at,4)),(8,c.read(at+4,4)),(12,c.read(at+8,4)),(16,at),(20,at+12)):c.write(master+0x28+i*24+off,v,4)
        obj=0x1800000;c.run(0x290e10,[obj]);banks=read(f,0x859f9000,43200)
        c.mem[0x93b900:0x93b900+len(banks)]=banks
        ma=Archive(f,0x85a04000);at,n=ma.entries[0];meta=read(f,at,n);c.mem[0x946200:0x946200+n]=meta
        motion=c.run(0x1a4a20,[master,0x5e9]);assert motion==23
        asset=c.run(0x290c90,[obj,BANK,motion]);assert asset==4073
        native=c.run(0x290c90,[obj,42,motion]);assert native==857
        assert meta[asset*16:(asset+1)*16]==meta[native*16:(native+1)*16] and any(meta[asset*16:(asset+1)*16])
        animation=Archive(f,0x2970d000).get(f,asset)
        assert len(animation)>64 and pages(animation)
        for sub in range(5):assert c.run(0x290990,[obj,BANK,motion,sub])==c.run(0x290990,[obj,42,motion,sub])
        assert c.run(0x1a5dc0,[master,0x5e9])==4400
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,
        weapon_key=0x5e9,weapon_power=4400,range=[1,2],motion=motion,animation_asset=asset,
        original_five_weapons_preserved=True,native_animation_and_auxiliary_getters_verified=True,
        live_playback_verified=False,edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits])
    if not apply:print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2));return
    report['shishio_add']=entry;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a in edits:assert read(f,off,2)==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);target=hashlib.sha256();inverse=hashlib.sha256();pos=0
            for off,b,a in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;target.update(raw);inverse.update(raw);pos+=len(raw)
                assert f.read(2)==a;target.update(a);inverse.update(b);pos+=2
            while raw:=f.read(4<<20):target.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2))


def status_frame_fix(apply=False):
    """Remove native large-portrait storage padding from the status thumbnail."""
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='6b2c7e7a71c12f53b7fb87d40546ef4ef600d24aa4cf7e945131ee84095186ab'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        small=Archive(f,0x1b12d800);faces=Archive(f,0x1a2f3000)
        assert small.mapping[2230:2240]==[276]*10
        at,n=small.entries[276];old=read(f,at,n);large=faces.get(f,1874)
        idx=np.frombuffer(large[1024:],np.uint8).reshape(112,112);nearest=np.arange(128)*112//128
        assert old==large[:1024]+idx[nearest[:,None],nearest[None,:]].tobytes()
        new=small_beowulf_portrait(f,faces);assert len(new)==len(old)==17408
        assert new[:1024]==old[:1024] and new!=old
        native_small=small.get(f,580)
        palette=np.frombuffer(new[:1024],np.uint8).reshape(256,4)[SWIZZLE]
        image=palette[np.frombuffer(new[1024:],np.uint8).reshape(128,128)]
        yy,xx=np.where(image[:,:,3]>0);assert (int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max()))==(0,0,127,127)
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,
        storage_canvas=[112,112],native_visible_area=[100,100],status_texture=[128,128],
        palette_and_native_face_pixels_preserved=True,original_Kyosuke_thumbnail_unchanged=True,
        offset=at,before=old.hex(),after=new.hex(),live_status_screen_verified=False)
    if not apply:print(json.dumps({k:v for k,v in entry.items() if k not in ('before','after')},indent=2));return
    report['status_frame_fix']=entry;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            assert read(f,at,n)==old;f.seek(at);f.write(new);f.flush();os.fsync(f.fileno())
            f.seek(0);target=hashlib.sha256();inverse=hashlib.sha256();remaining=at
            while remaining:
                raw=f.read(min(4<<20,remaining));assert raw;remaining-=len(raw);target.update(raw);inverse.update(raw)
            assert f.read(n)==new;target.update(new);inverse.update(old)
            while raw:=f.read(4<<20):target.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
            assert Archive(f,0x1b12d800).get(f,580)==native_small
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:f.seek(at);f.write(old)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    rgba=image.copy();rgba[:,:,3]=np.minimum(rgba[:,:,3].astype(np.uint16)*2,255)
    Image.fromarray(rgba).save(ART/'small_beowulf_preview.png')
    print(json.dumps({k:v for k,v in entry.items() if k not in ('before','after')},indent=2))


def hp_match(apply=False):
    """Match native Alfimi base HP without touching any other boss parameter."""
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='4a6a923d27d44c1827ec664e560db792276385f029d0938e8ecbeb725cda0e0f'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    edits=[]
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        for base in (0x5DA000,0x83F000):
            b=read(f,base,0x1A5800);h=0x11E800;ut=h+u32(b,h+0x18);units=h+u32(b,h+0x1c)+12
            alf=u16(b,ut+12+0x4d2*2);boss=u16(b,ut+12+UNIT*2)
            assert (alf,boss)==(273,427)
            target=u32(b,units+alf*100);old=read(f,base+units+boss*100,4)
            assert target==135000 and u32(old)==50000
            edits.append((base+units+boss*100,old,struct.pack('<I',target)))
        spawns=json.loads((ART/'enemy_spawn_plan.json').read_text(encoding='utf-8'));a=Archive(f,MAP+0x5070000)
        for p in spawns:
            at,n=a.entries[p['table']];d=read(f,at,n);alf=d[44+p['original_alfimi_row']*336:44+(p['original_alfimi_row']+1)*336]
            rows=[d[44+i*336:44+(i+1)*336] for i in range(u32(d,40)) if u32(d,44+i*336)==UNIT and u32(d,44+i*336+4)==p['group']]
            assert len(rows)==1 and rows[0][0x34:]==alf[0x34:]
        # Verify both the base getter and full map-actor HP calculation.
        from r5900_scalar_check import CPU
        rr=(ART/'current_user_ram.bin').read_bytes();c=CPU(rr);c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
        b=bytearray(read(f,0x5da000,0x1a5800));h=0x11e800;unit=h+u32(b,h+0x1c)+12
        struct.pack_into('<I',b,unit+427*100,target)
        master=u32(rr,0x59d360);dest=0x1100000;payload=b[h:];c.mem[dest:dest+len(payload)]=payload
        for i,field in enumerate(range(0x18,0x8c,4)):
            at=dest+u32(b,h+field)
            for off,value in ((0,at),(4,c.read(at,4)),(8,c.read(at+4,4)),(12,c.read(at+8,4)),(16,at),(20,at+12)):c.write(master+0x28+i*24+off,value,4)
        actor=0x6e3d50;save=u32(rr,0x59d364);slot=c.read(actor+0x18,4);rec=save+0x6efc+slot*0xd8
        assert c.read(rec,2)==UNIT
        values=[]
        for key in (0x4d2,UNIT):
            c.write(rec,key,2)
            values.append((c.run(0x1a7d40,[master,key]),c.run(0x1fe9d0,[actor,0x14,0,0,0])))
        assert values==[(target,target),(target,target)]
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,old_HP=50000,new_HP=target,
        Alfimi_matching_spawn_variants=len(spawns),native_base_and_full_HP_getters_verified=True,
        edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits])
    if not apply:print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2));return
    report['hp_match']=entry;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a in edits:assert read(f,off,4)==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);targethash=hashlib.sha256();inverse=hashlib.sha256();pos=0
            for off,b,a in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;targethash.update(raw);inverse.update(raw);pos+=len(raw)
                assert f.read(4)==a;targethash.update(a);inverse.update(b);pos+=4
            while raw:=f.read(4<<20):targethash.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=targethash.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2))


def beowulf_story_scenes():
    A,B,K,R,T,E=0x41F,PILOT,0x446,0x49F,0x48C,0x420
    return {
      84:[(320,'소환',[ 
        (A,'알피미：쿄스케……。@저는 당신을 만나고 싶었어요……。'),
        (R,'라이：중위！@또 다른 기체가 나타났습니다！'),
        (A,'알피미：이 느낌은……쿄스케……？@아니에요。당신은……。'),
        (B,'베오울프：……네가 나를 불렀나。'),
        (K,'쿄스케：그 목소리……。@누구냐。'),
        (B,'베오울프：이쪽 세계의 나인가。@아직 그 모습으로 남아 있었군。'),
        (T,'브릿트：중위님과……@같은 사람이라는 겁니까！？'),
        (A,'알피미：저는……그저 쿄스케를@만나고 싶었을 뿐인데……。'),
        (B,'베오울프：그 부름이 내게까지 닿았다。@네 마음이 만든 틈을 따라왔지。'),
        (K,'쿄스케：……다른 세계에서 왔다고？'),
        (B,'베오울프：베오울프라고 불러라。@이 세계의 끝을 보러 왔다。'),
        (A,'알피미：잠깐……기다려요……！'),
        (K,'쿄스케：브릿트、물러서라。@저 기체도 경계해라。')])],
      121:[(492,'별도 루트의 소환',[
        (A,'알피미：쿄스케……。@만나고 싶다고 생각했을 뿐인데……。'),
        (B,'베오울프：그 마음이 닿았다。@다른 세계의 나에게까지 말이다。'),
        (A,'알피미：당신도……쿄스케……？'),
        (B,'베오울프：베오울프다。@네 부름을 따라 이곳까지 왔다。'),
        (A,'알피미：하지만……。@제가 찾던 느낌과는……달라요。'),
        (B,'베오울프：그 차이는 곧 알게 되겠지。')])],
      97:[(660,'부름의 정체',[
        (A,'알피미：당신에게서도……@쿄스케를 느껴요。그런데……。'),
        (B,'베오울프：같은 이름、같은 목소리。@그것으로는 부족한가？'),
        (A,'알피미：저는……아직 모르겠어요……。'),
        (B,'베오울프：그렇다면 지켜봐라。@어느 쪽이 네가 찾던 쿄스케인지。')])],
      106:[(526,'엑셀렌을 향한 부름',[
        (A,'알피미：엑셀렌……。@쿄스케는 당신을……。'),
        (B,'베오울프：또 그 이름인가。@네가 찾던 것은 그 여자인가？'),
        (A,'알피미：당신에게도……@소중한 사람은 없었나요……？'),
        (B,'베오울프：그런 것은、더는 필요 없다。')])],
      110:[(596,'두 쿄스케',[
        (B,'베오울프：또 만났군、이쪽의 나。@그 몸으로 어디까지 버틸 셈이지？'),
        (K,'쿄스케：네 기준에 맞출 생각은 없다。'),
        (A,'알피미：같은 목소리인데……。@어째서、이렇게 다른 건가요……？'),
        (B,'베오울프：답은 전장에서 확인해라。')])],
      126:[(711,'별도 루트의 두 쿄스케',[
        (A,'알피미：쿄스케를 원했을 텐데……。@당신을 보면、뭔가가 달라요……。'),
        (B,'베오울프：그 녀석도 나도、같은 존재다。'),
        (K,'쿄스케：모습이 닮았으면 같다는 건가？@멋대로 결정하지 마라。'),
        (A,'알피미：……그 말은……。')])],
      112:[(705,'어긋난 마음',[
        (B,'베오울프：길은 넓어지고 있다。@이젠、네 바람만으론 멈추지 않아。'),
        (A,'알피미：저는……그것까지 바라진 않았어요……。'),
        (B,'베오울프：바람이 불렀고、힘이 응했다。@이제 와서 무엇이 두렵지？'),
        (A,'알피미：……당신이、두려워요。')])],
      130:[(324,'별도 루트의 어긋난 마음',[
        (A,'알피미：당신이 와 주길 원했던 건……。'),
        (B,'베오울프：부른 것은 너다。@나를 거부하는 건가？'),
        (A,'알피미：같은 목소리라도……@제가 만나고 싶었던 사람과는 달라요……。'),
        (B,'베오울프：그렇다면、그 남자까지 확인해 주지。')])],
      114:[(161,'열리는 문',[
        (B,'베오울프：문이 열리는군。@이제、그 작은 틈에 매달릴 필요도 없겠어。'),
        (A,'알피미：제 마음이、당신을 불렀어요……。@하지만、그것만으로는……。'),
        (B,'베오울프：아직도 망설이는 건가。@그 남자의 무엇을 원하는 거지？'),
        (A,'알피미：그건……。@제가、알고 싶은 것이에요……。')])],
      115:[(82,'결전의 문턱',[
        (B,'베오울프：여기까지 왔나。@같은 얼굴로、어디까지 버틸 셈이지？'),
        (K,'쿄스케：누구와 같은 얼굴이든 상관없다。@이 세계는 넘겨주지 않겠다。'),
        (A,'알피미：쿄스케……베오울프……。@저는……어느 쪽을 원했던 걸까요……？')]),
       (199,'부름을 거두다',[
        (B,'베오울프：아직도 나를 거부하나、알피미。'),
        (A,'알피미：제가 찾던 쿄스케는……@당신이 아니에요。'),
        (B,'베오울프：그토록 강하게 불러 놓고、@이제 와서 길을 막을 셈인가？'),
        (A,'알피미：그 부름은、제 마음이었어요。@그러니……멈추는 것도 저예요。'),
        (K,'쿄스케：네가 어떤 나였든 상관없다。@이쪽 세계에 네 뜻을 강요하게 두진 않겠다。'),
        (A,'알피미：당신이 지나온、그 틈을……@지금、닫겠어요。'),
        (B,'베오울프：……큭！@이 나를、원래 세계로……！？'),
        ('retire',None),
        (K,'쿄스케：여기까지다。베오울프。')]),
       (1077,'자신의 마음',[
        (E,'알피미：당신을 만나고 싶었던……@그때의 기분도……@분명、제 것이었어요……。'),
        (K,'쿄스케：너는 누구의 그림자도 아니다。@알피미。너는 너다。')])],
    }


def rebuild_beowulf_story_logo(old,scenes,speaker_context=False):
    from build_hidden_rewards import DEAD,command
    count,co=u32(old,0x28),u32(old,0x2c);prefix=u32(old,0x20)
    nc,kc,hc=u32(old,0x40),u32(old,0x50),u32(old,0x38)
    records=[list(struct.unpack_from('<24I',old,co+i*96)) for i in range(count)]
    template=next((r for r in records if r[0]==0x30 and r[4]==0x41f and r[13]==0x100a5),None)
    if template is None:template=next(r for r in records if r[0]==0x30)
    inserts={};messages=[];scene_notes=[];next_label=hc
    for point,title,lines in sorted(scenes):
        assert 0<point<count and point not in inserts
        added=[]
        local=next((r for r in reversed(records[:point]) if r[0]==0x30),template)
        for speaker,text in lines:
            if speaker=='command':
                assert len(text)==24;added.append(list(text));continue
            if speaker=='retire':
                added.append(command(0x81,0x100a5,PILOT,0xce,0xdeaddeed));continue
            text=text.replace('@',' ').replace(' ','　')
            wrapped=[]
            while len(text)>20:
                cut=text.rfind('　',6,21)
                if cut<0:cut=20
                wrapped.append(text[:cut]);text=text[cut:].lstrip('　')
            text='@'.join(wrapped+[text]);assert len(text.split('@'))<=3
            assert not any('\u3040'<=ch<='\u30ff' or '\u4e00'<=ch<='\u9fff' for ch in text),'Untranslated draft'
            encoded=encode(text);assert decode(encoded)==text
            context=local
            if speaker_context:
                context=next((r for r in reversed(records[:point]) if r[0]==0x30 and r[4]==speaker),
                    next((r for r in records if r[0]==0x30 and r[4]==speaker),local))
            r=list(context);r[1]=next_label;r[2]=nc+kc-1+len(messages);r[4]=speaker
            r[5]=8 if speaker in (0x41f,0x420) else 1 if speaker==0x446 else 0
            added.append(r);messages.append(dict(label=next_label,speaker=speaker,text=text,encoded=encoded.hex()))
            next_label+=1
        inserts[point]=added;scene_notes.append(dict(before_record=point,title=title,records=len(added)))
    def moved(i):return i+sum(len(v) for p,v in inserts.items() if p<=i)
    out_records=[];new_labels={}
    for i in range(count+1):
        for r in inserts.get(i,[]):
            if r[0]==0x30:new_labels[r[1]]=prefix+len(out_records)
            out_records.append(r)
        if i==count:break
        r=list(records[i])
        if r[0] in (0x8b,0x8c):
            for field in ((6,7) if r[0]==0x8b else (7,)):
                if r[field]<0x80000000:r[field]=moved(i+r[field])-moved(i)
        out_records.append(r)
    extra=(len(out_records)-count)*96
    endcode=co+count*96
    b=bytearray(old[:co])+bytearray(b''.join(struct.pack('<24I',*r) for r in out_records))+bytearray(old[endcode:])
    struct.pack_into('<I',b,0x28,len(out_records))
    for field in (0x34,0x3c,0x44,0x4c,0x54,0x5c):
        assert u32(old,field)>=endcode;struct.pack_into('<I',b,field,u32(old,field)+extra)
    # Native 0x2B5928..0x2B5940 adds the prefix count when kind != 0.
    # These targets are MAIN-relative, unlike the combined history indices.
    desc=u32(b,0x34)
    for i in range(u32(old,0x30)):
        at=desc+i*16;kind=u32(b,at);target=u32(b,at+8)
        if kind:struct.pack_into('<I',b,at+8,moved(target))
    history=[u32(old,u32(old,0x3c)+i*4) for i in range(hc)]
    history=[prefix+moved(i-prefix) if i>=prefix else i for i in history]
    history.extend(new_labels[i] for i in range(hc,next_label))
    combined=old[u32(old,0x44):u32(old,0x44)+(nc+kc)*4]
    assert u32(old,0x54)==u32(old,0x44)+nc*4
    pointers=list(struct.unpack('<%dI'%(nc+kc),combined))[:-1];pool=u32(b,0x4c)
    assert all(r[2]!=nc+kc-1 for r in records if r[0]==0x30)
    for msg in messages:
        pointers.append(len(b)-pool);b.extend(bytes.fromhex(msg['encoded'])+b'\0')
    pointers.append(len(b)-pool)  # Retain a final end-of-pool sentinel.
    b.extend(bytes((-len(b))%4));table=len(b);b.extend(struct.pack('<%dI'%len(pointers),*pointers))
    struct.pack_into('<I',b,0x44,table);struct.pack_into('<I',b,0x54,table+nc*4)
    struct.pack_into('<I',b,0x50,kc+len(messages));struct.pack_into('<I',b,0x58,u32(old,0x58)+len(messages))
    hist=len(b);b.extend(struct.pack('<%dI'%len(history),*history))
    struct.pack_into('<II',b,0x38,len(history),hist)
    struct.pack_into('<I',b,4,len(b));struct.pack_into('<I',b,0x6c,len(b))
    return bytes(b),dict(scenes=scene_notes,messages=messages,insert_counts={str(k):len(v) for k,v in inserts.items()})


def story_fix(apply=False):
    """Install additional story scenes in TEST only; retain original scripts."""
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='f5b3a0eeacae547422f07e454982a5d4048bf0ea98da82729e86cbc13eba1b65'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    scripts=Scripts(OUT);chapters=[];edits=[];cursor=0x8F00000
    from r5900_scalar_check import CPU
    rr=(ART/'current_user_ram.bin').read_bytes();native_checks=0
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        for n,scenes in sorted(beowulf_story_scenes().items()):
            oldat,size=scripts.logos[n];old=scripts.data[oldat:oldat+size]
            new,notes=rebuild_beowulf_story_logo(old,scenes)
            from validate_beowulf_prototype import validate_story_blob
            notes['validation']=validate_story_blob(old,new,notes,rr)
            assert u32(new,0x20)==u32(old,0x20)
            # Execute real string and backlog lookups against the new LOGO.
            c=CPU(rr);ctx,base=0x1600000,0x1800000;c.mem[base:base+len(new)]=new;c.run(0x2b5c90,[ctx,base])
            oldtotal=u32(old,0x40)+u32(old,0x50)
            for j,msg in enumerate(notes['messages']):
                raw=bytes.fromhex(msg['encoded']);assert len(raw)<128
                c.run(0x2baf90,[ctx,0,oldtotal-1+j]);assert bytes(c.mem[ctx+0x85a0:ctx+0x85a0+len(raw)])==raw
                c.run(0x2ba420,[ctx,msg['label'],0,0,0],stop=0x2ba478)
                index=c.r[5]&0xffffffff;off=u32(new,0x24)+index*96
                assert u32(new,off)==0x30 and u32(new,off+4)==msg['label'] and u32(new,off+8)==oldtotal-1+j
                native_checks+=1
            cursor=(cursor+2047)//2048*2048;assert cursor+len(new)<0x9600000
            assert not any(read(f,MAP+cursor,len(new)))
            edits.append((MAP+cursor,bytes(len(new)),new))
            dp=MAP+0x557F800+8+n*8
            edits.append((dp,read(f,dp,8),struct.pack('<II',cursor-0x557F800,len(new))))
            chapters.append(dict(script=n,source_offset=oldat,source_size=size,source_sha256=sha(old),
                target_offset=cursor,target_size=len(new),target_sha256=sha(new),**notes))
            cursor+=len(new)
        rootspan=MAP+0x800+8+14*8+4
        edits.append((rootspan,read(f,rootspan,4),struct.pack('<I',cursor-0x557E800)))
    edits.sort()
    for a,b in zip(edits,edits[1:]):assert a[0]+len(a[1])<=b[0]
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,
        scripts=len(chapters),scenes=sum(len(x['scenes']) for x in chapters),
        messages=native_checks,native_string_and_backlog_lookup_checks=native_checks,
        original_script_payloads_retained=True,live_playthrough_verified=False,chapters=chapters,
        edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits])
    report['story_fix']=entry
    if not apply:
        print(json.dumps({k:v for k,v in entry.items() if k not in ('edits','chapters')},indent=2));return
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a in edits:assert read(f,off,len(b))==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);target=hashlib.sha256();inverse=hashlib.sha256();pos=0
            for off,b,a in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;target.update(raw);inverse.update(raw);pos+=len(raw)
                assert f.read(len(a))==a;target.update(a);inverse.update(b);pos+=len(a)
            while raw:=f.read(4<<20):target.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    text=['베오울프 추가 시나리오 — 시험 ISO 반영본','기존 대사를 유지하고 아래 대화를 추가했습니다。','']
    order=[84,121,97,106,110,126,112,130,114,115]
    for ch in sorted(chapters,key=lambda x:order.index(x['script'])):
        cursor=0
        for point,title,lines in beowulf_story_scenes()[ch['script']]:
            text.extend(['【'+title+'】',''])
            for speaker,line in lines:
                if speaker=='retire':text.extend(['[베오울프의 기체가 원래 세계로 퇴장]','']);continue
                text.extend([ch['messages'][cursor]['text'].replace('　',' ').replace('@','\n'),'']);cursor+=1
    (ART/'story_dialogue.txt').write_text('\n'.join(text),encoding='utf-8-sig')
    print(json.dumps({k:v for k,v in entry.items() if k not in ('edits','chapters')},indent=2))


def release_beowulf_master(old, tested):
    """Append tested Beowulf to a current option profile; keep its existing records."""
    h=0x11e800;fields=list(range(0x18,0x8c,4))
    starts=[h+u32(old,h+k) for k in fields];end=h+u32(old,0x11e00c)
    other={k:h+u32(tested,h+k) for k in fields}
    tables={k:bytearray(old[p:(starts[i+1] if i+1<len(starts) else end)]) for i,(k,p) in enumerate(zip(fields,starts))}
    uc,wc=u32(tables[0x1c],8),u32(tables[0x24],8)
    assert uc in (429,430,431) and wc in (1636,1639,1643)
    if uc==431:assert u16(tables[0x18],12+0x606*2)==430
    if wc==1643:assert all(u16(tables[0x20],12+k*2)==1639+i for i,k in enumerate(range(0xfa0,0xfa4)))
    if wc==1639:assert all(u16(tables[0x20],12+k*2)==1636+i for i,k in enumerate(range(0xf90,0xf93)))
    if uc==430:assert u16(tables[0x18],12+0x605*2)==429
    assert u16(tables[0x18],12+UNIT*2)==0xffff
    assert all(u16(tables[0x20],12+k*2)==0xffff for k in range(0xf80,0xf86))
    assert u16(tables[0x28],12+PILOT*2)==0xffff
    assert all(u16(tables[0x28],12+k*2)!=381 for k in range(2048))
    body=tested[other[0x1c]+12+427*100:other[0x1c]+12+428*100]
    assert len(body)==100 and u16(body,0x44)==BANK
    tables[0x1c].extend(body);struct.pack_into('<II',tables[0x1c],4,u32(tables[0x1c],4)+100,uc+1)
    struct.pack_into('<I',tables[0x18],4,u32(tables[0x18],4)+100)
    struct.pack_into('<H',tables[0x18],12+UNIT*2,uc)
    for i,key in enumerate(range(0xf80,0xf86)):
        idx=u16(tested,other[0x20]+12+key*2)
        record=tested[other[0x24]+12+idx*36:other[0x24]+12+(idx+1)*36]
        tables[0x24].extend(record);struct.pack_into('<H',tables[0x20],12+key*2,wc+i)
    struct.pack_into('<II',tables[0x24],4,u32(tables[0x24],4)+216,wc+6)
    pilot=bytearray(tested[other[0x2c]+12+381*148:other[0x2c]+12+382*148])
    # Append only the display name, keeping every existing string ID stable.
    st=tables[0x80];count=u32(st,8);size=u32(st,4);name=encode('베오울프')+b'\0'
    ptrs=struct.unpack_from('<%dI'%count,st,12)
    stnew=bytearray(b'Strg'+struct.pack('<II',size+4+len(name),count+1))
    stnew.extend(struct.pack('<%dI'%(count+1),*[p+4 for p in ptrs],size+4))
    stnew.extend(st[12+count*4:size]);stnew.extend(name);stnew.extend(bytes((-len(stnew))%4))
    tables[0x80]=stnew
    struct.pack_into('<3H',pilot,4,count,count,count)
    tables[0x2c][12+381*148:12+382*148]=pilot
    struct.pack_into('<H',tables[0x28],12+PILOT*2,381)
    out=bytearray(old[:starts[0]])
    for k in fields:
        struct.pack_into('<I',out,h+k,len(out)-h);out.extend(tables[k])
    struct.pack_into('<I',out,0x11e00c,len(out)-h)
    assert len(out)<=len(old) and not any(old[end:len(out)])
    out.extend(old[len(out):])
    for k,stride in ((0x1c,100),(0x24,36),(0x2c,148)):
        before=starts[fields.index(k)];after=h+u32(out,h+k);cnt=u32(old,before+8)
        for i in range(cnt):
            if k==0x2c and i==381:continue
            assert out[after+12+i*stride:after+12+(i+1)*stride]==old[before+12+i*stride:before+12+(i+1)*stride]
    for i,p in enumerate(ptrs):
        np=u32(stnew,12+i*4)
        assert stnew[np:stnew.index(0,np)]==st[p:st.index(0,p)]
    return bytes(out)

def beowulf_balance_master(old):
    """Independent weapons and Kyosuke+10 base stats; native characters untouched."""
    h=0x11E800;end=h+u32(old,0x11E00C)
    ut,unit,wt,weap,pt,plot=[h+u32(old,h+field) for field in (0x18,0x1c,0x20,0x24,0x28,0x2c)]
    assert u16(old,ut+12+UNIT*2)==427 and u16(old,pt+12+PILOT*2)==381
    assert u32(old,unit+8)==428 and u32(old,weap+8)==1628
    keys=list(range(0xF80,0xF85));assert all(u16(old,wt+12+k*2)==65535 for k in keys)
    original_keys=list(struct.unpack_from('<5H',old,unit+12+0x44*100+0x24))
    assert original_keys==[0x8A0,0x8A1,0x8A2,0x8A3,0x8A4]
    assert list(struct.unpack_from('<5H',old,unit+12+427*100+0x24))==original_keys
    copies=[];powers=[]
    for k in original_keys:
        idx=u16(old,wt+12+k*2);r=bytearray(old[weap+12+idx*36:weap+12+(idx+1)*36])
        power=u16(r,8);assert 0<power<65035;struct.pack_into('<H',r,8,power+500)
        copies.append(bytes(r));powers.append([power,power+500])
    wend=weap+u32(old,weap+4);extra=b''.join(copies);b=bytearray(old[:end]);b[wend:wend]=extra
    assert len(b)<=len(old) and not any(old[end:len(b)])
    for field in range(0x18,0x8C,4):
        at=h+u32(old,h+field)
        if at>=wend:struct.pack_into('<I',b,h+field,at+len(extra)-h)
    struct.pack_into('<II',b,weap+4,u32(old,weap+4)+len(extra),1633)
    for i,k in enumerate(keys):struct.pack_into('<H',b,wt+12+k*2,1628+i)
    struct.pack_into('<5H',b,unit+12+427*100+0x24,*keys)
    newplot=plot+len(extra);native=old[plot+12+114*148+0x65:plot+12+114*148+0x6B]
    assert all(x<246 for x in native)
    assert b[newplot+12+381*148+0x65:newplot+12+381*148+0x6B]==native
    b[newplot+12+381*148+0x65:newplot+12+381*148+0x6B]=bytes(x+10 for x in native)
    struct.pack_into('<I',b,0x11E00C,u32(old,0x11E00C)+len(extra))
    assert b[weap+12:weap+12+1628*36]==old[weap+12:weap+12+1628*36]
    assert b[newplot+12+114*148:newplot+12+115*148]==old[plot+12+114*148:plot+12+115*148]
    return bytes(b),dict(base_stats=list(native),new_stats=[x+10 for x in native],weapons=powers,weapon_keys=keys)


def balance_fix(apply=False):
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='04e1da7dfeb2de660e736e32aea547aac34b01bbd0d0441b862b2ed1fe24681b'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        edits=[]
        for base in (0x5DA000,0x83F000):
            old=read(f,base,0x1A5800);new,details=beowulf_balance_master(old)
            edits.append((base+0x11E000,old[0x11E000:len(new)],new[0x11E000:]))
        spawns=json.loads((ART/'enemy_spawn_plan.json').read_text(encoding='utf-8'));a=Archive(f,MAP+0x5070000)
        for spawn in spawns:
            at,n=a.entries[spawn['table']];d=read(f,at,n)
            alf=d[44+spawn['original_alfimi_row']*336:44+(spawn['original_alfimi_row']+1)*336]
            rows=[d[44+i*336:44+(i+1)*336] for i in range(u32(d,40)) if u32(d,44+i*336)==UNIT and u32(d,44+i*336+4)==spawn['group']]
            assert len(rows)==1 and rows[0][0x34:0x44]==alf[0x34:0x44]
        from validate_hidden_rewards import ram
        from r5900_scalar_check import CPU
        c=CPU(ram);c.mem[0x100000:0x582980]=read(f,0x94880,0x482980);master=u32(ram,0x59D360);h=0x11E800
        for i,(ctxoff,field) in enumerate(((0x28,0x18),(0x40,0x1c),(0x58,0x20),(0x70,0x24),(0x88,0x28),(0xA0,0x2c))):
            rel=h+u32(new,h+field);dest=0x1000000+i*0x100000;n=u32(new,rel+4);c.mem[dest:dest+n]=new[rel:rel+n]
            for off,value in ((0,dest),(4,u32(new,rel)),(8,n),(12,u32(new,rel+8)),(16,dest),(20,dest+12)):c.write(master+ctxoff+off,value,4)
        stats=[]
        for fn in (0x1A3EF0,0x1A3E70,0x1A3DF0,0x1A3D70,0x1A3CF0,0x1A3C70):
            normal=c.run(fn,[master,0x446]);boss=c.run(fn,[master,PILOT]);assert boss==normal+10;stats.append([normal,boss])
        for k,power in zip(details['weapon_keys'],details['weapons']):assert c.run(0x1A5DC0,[master,k])==power[1]
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,details=details,
        native_pilot_stat_getters=stats,Alfimi_matching_level_variants=len(spawns),native_weapon_power_getters_verified=True,
        original_Kyosuke_Riese_preserved=True,live_playback_verified=False,
        edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits])
    if not apply:print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2));return
    report['balance_fix']=entry;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a in edits:assert read(f,off,len(b))==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);target=hashlib.sha256();inverse=hashlib.sha256();pos=0
            for off,b,a in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;target.update(raw);inverse.update(raw);pos+=len(raw)
                assert f.read(len(a))==a;target.update(a);inverse.update(b);pos+=len(a)
            while raw:=f.read(4<<20):target.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2))


def voice_chunk_fix(apply=False):
    """Register Kyosuke's native selector/text/voice chunk under Beowulf's key."""
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='84c95c9698eb14a46af8ca5f3928d022b395304c9ffc0c69fc5d5808ca5250cf'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        archive=Archive(f,0x8574E800);assert PILOT>=archive.slots
        original=archive.get(f,0x446);h=struct.unpack_from('<16H',original);clone=bytearray(original)
        assert h[12]<h[13]<h[14]<h[15]<len(original)
        count=(h[13]-h[12])//2;changed=0
        for off in range(h[12],h[13],2):
            tag=u16(clone,off)
            if tag&0x7ff==0x446:
                struct.pack_into('<H',clone,off,(tag&0xf800)|PILOT);changed+=1
        assert changed==520
        assert clone[:h[12]]==original[:h[12]] and clone[h[13]:]==original[h[13]:]
        plan=Plan(f)
        plan.cursor=max(o+n for base in (0x25120800,0x27D66800,0x2970D000,0x8574E800) for o,n in Archive(f,base).entries)
        size=plan.archive(archive,[(PILOT,bytes(clone),'Separate native Kyosuke battle speech for Beowulf')])
        plan.add(0x25120000+8+5*8+4,struct.pack('<I',size),'BATTLE speech archive span includes new chunk')
        edits=sorted(plan.edits)
        for (a,b,c,l),(d,e,g,ll) in zip(edits,edits[1:]):assert a+len(b)<=d
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,source_pilot_key=0x446,
        target_pilot_key=PILOT,retagged_self_speaker_rows=changed,chunk_rows=count,
        selectors_text_voice_IDs_unchanged=True,original_Kyosuke_chunk_preserved=True,
        live_playback_verified=False,edits=[dict(offset=o,before=b.hex(),after=a.hex(),label=l) for o,b,a,l in edits])
    if not apply:
        print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2));return
    report['voice_chunk_fix']=entry;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a,label in edits:assert read(f,off,len(b))==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);target=hashlib.sha256();inverse=hashlib.sha256();pos=0
            for off,b,a,label in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;target.update(raw);inverse.update(raw);pos+=len(raw)
                assert f.read(len(a))==a;target.update(a);inverse.update(b);pos+=len(a)
            while raw:=f.read(4<<20):target.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
            checked=Archive(f,0x8574e800);assert checked.get(f,PILOT)==clone
            assert checked.get(f,0x446)==original
            assert checked.mapping[:archive.slots]==archive.mapping
            for (at,n),(newat,nn) in zip(archive.entries,checked.entries):assert (at,n)==(newat,nn)
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a,label in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2))


def attack_display_fix(apply=False):
    """Complete each cloned attack with its required 16-byte display record."""
    import os,psutil
    assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2'
    expected='c5a2648954a0867153db6039277045cc968436bf0283388ed449820796b507ae'
    journal=ART/'prototype_manifest.json';report=json.loads(journal.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        archive=Archive(f,0x85A04000);at,n=archive.entries[0];metadata=bytearray(read(f,at,n))
        native=struct.unpack_from('<70H',read(f,0x859F9000+42*144,144),4)
        clone=struct.unpack_from('<70H',read(f,0x859F9000+BANK*144,144),4)
        pairs=sorted(set(zip(native,clone))-{(65535,65535)})
        assert len(pairs)==50
        edits=[]
        for oldkey,newkey in pairs:
            old=bytes(metadata[newkey*16:(newkey+1)*16]);new=bytes(metadata[oldkey*16:(oldkey+1)*16])
            assert old==bytes(16) and any(new)
            edits.append((at+newkey*16,old,new));metadata[newkey*16:(newkey+1)*16]=new
        from r5900_scalar_check import CPU
        c=CPU((ART/'current_user_ram.bin').read_bytes());obj=0x1800000;c.run(0x290e10,[obj])
        c.mem[0x93b900:0x93b900+43200]=read(f,0x859f9000,43200)
        before=read(f,at,n);c.mem[0x946200:0x946200+n]=before
        bad=[]
        for motion,(a,b) in enumerate(zip(native,clone)):
            if a==65535:continue
            want=tuple(c.run(fn,[obj,42,motion,0]) for fn in (0x290b20,0x290990))
            got=tuple(c.run(fn,[obj,BANK,motion,0]) for fn in (0x290b20,0x290990))
            if want!=got:bad.append(motion)
        assert bad, 'Failure must be reproduced before patch'
        c.mem[0x946200:0x946200+n]=metadata
        cases=0
        for motion,a in enumerate(native):
            if a==65535:continue
            for fn in (0x290b20,0x290990):
                want=c.run(fn,[obj,42,motion,0]);got=c.run(fn,[obj,BANK,motion,0])
                assert want==got,(motion,hex(fn),want,got)
            cases+=1
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,
        display_records=50,native_motion_metadata_cases=cases,missing_display_metadata_reproduced=bad,
        live_playback_verified=False,edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits])
    if not apply:print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2));return
    report['attack_display_fix']=entry;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a in edits:assert read(f,off,len(b))==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);inverse=hashlib.sha256();target=hashlib.sha256();pos=0
            for off,b,a in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                assert f.read(len(a))==a;inverse.update(b);target.update(a);pos+=len(a)
            while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2))


def playable_voice_fix(apply=False):
    """Restore native Kyosuke battle speech and force the ally onto the ground."""
    import os,psutil
    assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter())
    expected='a5ae3f3506875cee8c82ca0b88a93cefc6b726c6af3f395bdb353eda4e9bf567'
    report=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'));edits=[]
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        for base in (0x5DA000,0x83F000):
            b=read(f,base,0x1A5800);h=0x11E800;plot=h+u32(b,h+0x2c)+12
            old=b[plot+381*148+0x58:plot+381*148+0x60]
            original=b[plot+114*148+0x58:plot+114*148+0x60]
            assert old==struct.pack('<4H',FACE,FACE,FACE,FACE) and original==struct.pack('<4H',58,58,58,58)
            assert u16(b,plot+381*148+0x48)==FACE
            edits.append((base+plot+381*148+0x58,old,original))
        aa=Archive(f,MAP+0x5070000);at,n=aa.entries[78];offset=at+44+40*336+0x1c
        old=read(f,offset,4);assert u32(old)==5
        edits.append((offset,old,struct.pack('<I',3)))
    # Execute the actual spawn-bit handling: bit2 forces flight, bit1 grounds.
    from r5900_scalar_check import CPU
    rr=(ART/'current_user_ram.bin').read_bytes()
    for flags,mode in ((5,1),(3,0)):
        c=CPU(rr);actor=0x6e3d50;row=0x1800000;c.r[20]=actor
        c.write(actor+0x168,row,4);c.write(row+0x1c,flags,4)
        c.run(0x1e79b8,stop=0x1e7a24)
        assert c.run(0x1fe9d0,[actor,0x131,0,0,0])==mode
        assert c.run(0x1fe9d0,[actor,0x14c,0,0,0])==2
    edits.sort();entry=dict(applied=False,source_sha256=expected,production_sha256=production,
        native_spawn_ground_mode_verified=True,native_Kyosuke_battle_groups=[58]*4,Beowulf_portrait=FACE,
        edits=[dict(offset=o,before=b.hex(),after=a.hex()) for o,b,a in edits])
    if not apply:return entry
    report['playable_voice_fix']=entry
    (ART/'prototype_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            for off,b,a in edits:
                assert read(f,off,len(b))==b;f.seek(off);f.write(a)
            f.flush();os.fsync(f.fileno());f.seek(0);h=hashlib.sha256();inverse=hashlib.sha256();pos=0
            for off,b,a in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;h.update(raw);inverse.update(raw);pos+=len(raw)
                assert f.read(len(a))==a;h.update(a);inverse.update(b);pos+=len(a)
            while raw:=f.read(4<<20):h.update(raw);inverse.update(raw)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:
            for off,b,a in edits:f.seek(off);f.write(b)
        raise
    entry.update(applied=True,target_sha256=h.hexdigest(),all_other_bytes_preserved=True)
    (ART/'prototype_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k!='edits'},indent=2))


def episode6_ally_test(apply=False):
    """Replace the enemy test row with a controllable ally beside Soulgain."""
    import os, psutil
    assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()), 'Close PCSX2 first'
    expected='0dd5ec28b46cfc3637de565c2862e46ceb7c9b85803b87a0925b0677672b598d'
    manifest=ART/'prototype_manifest.json'
    report=json.loads(manifest.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f: production=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        archive=Archive(f,MAP+0x5070000);at,size=archive.entries[78]
        data=read(f,at,size)
        assert data[24:32].split(b'\0')[0]==b'01011' and u32(data,40)==41
        offset=at+44+40*336;old=data[44+40*336:44+41*336]
        assert (u32(old),u32(old,4),u32(old,8),u32(old,32))==(UNIT,7,2,PILOT)
        row=bytearray(data[44+24*336:44+25*336])
        assert (u32(row),u32(row,4),u32(row,8),u32(row,32),u32(row,52))==(0x57A,6,0,0x3F4,7)
        xy=(16,7)
        assert xy not in {(u32(data,44+i*336+16),u32(data,44+i*336+20)) for i in range(40)}
        for off,value in ((0,UNIT),(16,xy[0]),(20,xy[1]),(32,PILOT)):struct.pack_into('<I',row,off,value)
        from validate_hidden_rewards import ram
        from r5900_scalar_check import CPU
        c=CPU(ram);c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
        master=u32(ram,0x59D360);blob=read(f,0x5DA000,0x1A5800);h=0x11E800
        for i,(ctxoff,field) in enumerate(((0x28,0x18),(0x40,0x1c),(0x58,0x20),(0x70,0x24),(0x88,0x28),(0xA0,0x2c))):
            rel=h+u32(blob,h+field);dest=0x1000000+i*0x100000;n=u32(blob,rel+4)
            c.mem[dest:dest+n]=blob[rel:rel+n]
            for off,value in ((0,dest),(4,u32(blob,rel)),(8,n),(12,u32(blob,rel+8)),(16,dest),(20,dest+12)):c.write(master+ctxoff+off,value,4)
        ctx,src=0x1600000,0x1700000
        c.write(ctx+0x28,0x59B240,4);c.write(ctx+0x346D4,src,4);c.mem[src:src+336]=row
        diff=c.read(0x59D36C,4);c.write(diff+0xF60,0,4);c.write(diff+0xF68,1,4)
        assert c.run(0x1D5970,[ctx,0])==1
        save=c.read(0x59D364,4);slot=c.run(0x1ABC50,[save,UNIT,0,0]);assert slot>=0
        assert c.run(0x1B01D0,[save,0x14,slot,0])==50000
        assert c.run(0x1A6690,[master,UNIT])==BANK
        assert c.run(0x1A2900,[master,PILOT])==FACE
    entry=dict(applied=False,source_sha256=expected,production_sha256=production,offset=offset,
        before=old.hex(),after=row.hex(),template_row=24,group=6,side=0,position=list(xy),
        native_roster_creation_verified=True,native_HP_bank_portrait_verified=True,
        original_40_rows_preserved=True,enemy_test_removed=True,script_bytes_unchanged=True,live_battle_verified=False)
    if not apply:
        print(json.dumps({k:v for k,v in entry.items() if k not in ('before','after')},indent=2));return
    report['episode6_ally_test']=entry
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            assert read(f,offset,336)==old;f.seek(offset);f.write(row);f.flush();os.fsync(f.fileno())
            f.seek(0);inverse=hashlib.sha256();target=hashlib.sha256();remaining=offset
            while remaining:
                b=f.read(min(4<<20,remaining));assert b;remaining-=len(b);inverse.update(b);target.update(b)
            assert f.read(336)==row;inverse.update(old);target.update(row)
            while b:=f.read(4<<20):inverse.update(b);target.update(b)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:f.seek(offset);f.write(old)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),all_other_bytes_preserved=True)
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k not in ('before','after')},indent=2))


def episode6_test_fix():
    """Use the playable battle enemy row, not the difficulty-zero intro cast."""
    import os
    expected='b561766a681108ccd3017765fae695a06501ae993bc2f71323a79ab4b0508511'
    manifest=ART/'prototype_manifest.json'
    report=json.loads(manifest.read_text(encoding='utf-8'))
    prior=report['episode6_test'];assert prior['applied']
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        units=Archive(f,MAP+0x5070000);at,size=units.entries[78]
        data=read(f,at,size)
        assert data[24:32].split(b'\0')[0]==b'01011' and u32(data,40)==41
        offset=at+44+40*336;old=data[44+40*336:44+41*336]
        assert (u32(old),u32(old,4),u32(old,32),u32(old,52))==(UNIT,2,PILOT,0)
        row=bytearray(data[44+25*336:44+26*336])
        assert (u32(row),u32(row,4),u32(row,8),u32(row,32),u32(row,52))==(0x4EB,7,2,0x4CE,7)
        xy=(15,12)
        assert xy not in {(u32(data,44+i*336+16),u32(data,44+i*336+20)) for i in range(40)}
        for off,value in ((0,UNIT),(16,xy[0]),(20,xy[1]),(32,PILOT)):
            struct.pack_into('<I',row,off,value)
        # Execute the native roster initializer on the exact new enemy row.
        from validate_hidden_rewards import ram
        from r5900_scalar_check import CPU
        c=CPU(ram);c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
        master=u32(ram,0x59D360);blob=read(f,0x5DA000,0x190000)
        for off,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),(0x70,0x12BF7C),(0x88,0x13A478),(0xA0,0x13B484)):
            dst=c.read(master+off,4);n=u32(blob,rel+4);c.mem[dst:dst+n]=blob[rel:rel+n]
        ctx,src=0x1600000,0x1700000
        c.write(ctx+0x28,0x59B240,4);c.write(ctx+0x346D4,src,4)
        c.mem[src:src+336]=row
        diff=c.read(0x59D36C,4);c.write(diff+0xF60,0,4);c.write(diff+0xF68,1,4)
        assert c.run(0x1D5970,[ctx,0])==1
        save=c.read(0x59D364,4)
        slot=c.run(0x1ABC50,[save,UNIT,0,0]);assert slot>=0
        assert c.run(0x1B01D0,[save,0x14,slot,0])==50000
        assert c.run(0x1A6690,[master,UNIT])==BANK
    repair=dict(applied=False,source_sha256=expected,group=7,side=2,difficulty_bits=7,
                position=list(xy),template_row=25,native_roster_creation_verified=True,
                native_HP_bank_verified=True,live_spawn_test=False,
                offset=offset,before=old.hex(),after=row.hex())
    prior['battle_group_fix']=repair
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with OUT.open('r+b') as f:
            assert read(f,offset,len(old))==old;f.seek(offset);f.write(row);f.flush();os.fsync(f.fileno())
            f.seek(0);h=hashlib.sha256();inverse=hashlib.sha256();remaining=offset
            while remaining:
                b=f.read(min(4<<20,remaining));assert b;remaining-=len(b);h.update(b);inverse.update(b)
            assert f.read(336)==row;h.update(row);inverse.update(old)
            while b:=f.read(4<<20):h.update(b);inverse.update(b)
            assert inverse.hexdigest()==expected
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with OUT.open('r+b') as f:f.seek(offset);f.write(old)
        raise
    repair.update(applied=True,target_sha256=h.hexdigest(),production_unchanged=production,
                  all_other_bytes_preserved=True)
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in repair.items() if k not in ('before','after')},indent=2))


def animation_palette_fix(apply=False):
    """Repair the existing TEST animation clones without altering native indexing."""
    import os,psutil
    expected='9850143e18ae82f288fa7f00a2b3b70aa831b774152b97f1dc93145eaf762e20'
    manifest=ART/'prototype_manifest.json';report=json.loads(manifest.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    edits=[];records=[];body_pages=cutin_pages=0
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        actor=Archive(f,0x27D66800);skin=Skin(pages(actor.get(f,42))[0][2])
        archive=Archive(f,0x2970D000)
        native=struct.unpack_from('<70H',read(f,0x859F9000+42*144,144),4)
        clones=struct.unpack_from('<70H',read(f,0x859F9000+BANK*144,144),4)
        for key,newkey in sorted(set(zip(native,clones))):
            if key==0xFFFF:assert newkey==0xFFFF;continue
            original=archive.get(f,key);before=archive.get(f,newkey)
            cache=ART/'converted'/(sha(original+skin.generated.tobytes()+b'\0')+'.bin')
            assert cache.read_bytes()==before,'Prior converted cache is required for exact rollback'
            after,nbody,ncutin=skin.palette_safe_asset(original)
            assert len(after)==len(before)
            at,n=archive.entries[archive.mapping[newkey]];assert n==len(before)
            if after!=before:edits.append((at,before,after))
            records.append(dict(native_key=key,clone_key=newkey,offset=at,size=n,
                before_cache=str(cache),before_sha256=sha(before),after_sha256=sha(after),
                body_pages=nbody,cutin_pages=ncutin))
            body_pages+=nbody;cutin_pages+=ncutin
        assert len(records)==50 and body_pages>0 and cutin_pages>0
        edits.sort();h=hashlib.sha256();pos=0;f.seek(0)
        for at,b,a in edits:
            while pos<at:
                chunk=f.read(min(4<<20,at-pos));assert chunk;h.update(chunk);pos+=len(chunk)
            assert f.read(len(b))==b;h.update(a);pos+=len(b)
        while chunk:=f.read(4<<20):h.update(chunk)
    fix=dict(applied=False,source_sha256=expected,target_sha256=h.hexdigest(),
        production_unchanged=production,resources=records,body_pages=body_pages,cutin_pages=cutin_pages,
        native_indices_CLUT_slots_alpha_commands_UVs_preserved=True,
        original_Kyosuke_Riese_resources_unchanged=True,live_battle_verified=False)
    report['animation_palette_fix']=fix
    manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for proc in psutil.process_iter(['name']):
            if 'pcsx2' in (proc.info['name'] or '').lower():
                assert all(Path(x.path).resolve()!=OUT.resolve() for x in proc.open_files()),'Close PCSX2 using TEST ISO'
        with OUT.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        try:
            with OUT.open('r+b') as f:
                for at,b,a in edits:
                    assert read(f,at,len(b))==b;f.seek(at);f.write(a)
                f.flush();os.fsync(f.fileno())
            with OUT.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==fix['target_sha256']
            with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
        except Exception:
            with OUT.open('r+b') as f:
                for at,b,a in edits:f.seek(at);f.write(b)
                f.flush();os.fsync(f.fileno())
            raise
        fix['applied']=True
        manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in fix.items() if k!='resources'},indent=2))


def status_portrait_fix(apply=False):
    import os,psutil
    expected='1677e6103cfdff60375b83acb538a48dfc044ced72d93db3c9301e86cf58d1b9'
    path=ART/'prototype_manifest.json';report=json.loads(path.read_text(encoding='utf-8'))
    with SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    edits=[]
    with OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        small=Archive(f,0x1B12D800);faces=Archive(f,0x1A2F3000)
        assert small.count==276 and small.slots==2240
        assert small.mapping[FACE*10:(FACE+1)*10]==[small.mapping[580]]*10
        payload=small_beowulf_portrait(f,faces)
        loc=(sum(faces.entries[0])+2047)//2048*2048
        assert loc==0x24BA4800 and not any(read(f,loc,len(payload)))
        assert small.directory+8+(small.count+1)*8<=min(at for at,n in small.entries)
        def add(at,new):edits.append((at,read(f,at,len(new)),bytes(new)))
        add(loc,payload)
        add(small.base+8,struct.pack('<I',small.count+1))
        add(small.directory+4,struct.pack('<I',small.count+1))
        add(small.directory+8+small.count*8,struct.pack('<II',loc-small.directory,len(payload)))
        add(small.base+16+FACE*10*2,struct.pack('<10H',*([small.count]*10)))
        add(0x17020000+8+2*8+4,struct.pack('<I',loc+len(payload)-small.base))
        edits.sort();h=hashlib.sha256();pos=0;f.seek(0)
        for at,b,a in edits:
            while pos<at:
                chunk=f.read(min(4<<20,at-pos));assert chunk;h.update(chunk);pos+=len(chunk)
            assert f.read(len(b))==b;h.update(a);pos+=len(b)
        while chunk:=f.read(4<<20):h.update(chunk)
        normal=small.get(f,580)
    fix=dict(applied=False,source_sha256=expected,target_sha256=h.hexdigest(),production_unchanged=production,
        native_large_expression=1874,small_group=FACE,small_physical_index=276,
        dimensions=[128,128],normal_Kyosuke_unchanged=True,
        edits=[dict(offset=p,before=b.hex(),after=a.hex()) for p,b,a in edits])
    report['status_portrait_fix']=fix
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for proc in psutil.process_iter(['name']):
            if 'pcsx2' in (proc.info['name'] or '').lower():
                assert all(Path(x.path).resolve()!=OUT.resolve() for x in proc.open_files()),'Close PCSX2 using TEST ISO'
        with OUT.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        try:
            with OUT.open('r+b') as f:
                for at,b,a in edits:assert read(f,at,len(b))==b;f.seek(at);f.write(a)
                f.flush();os.fsync(f.fileno())
            with OUT.open('rb') as f:
                assert hashlib.file_digest(f,'sha256').hexdigest()==fix['target_sha256']
                archive=Archive(f,0x1B12D800)
                assert archive.get(f,580)==normal
                assert archive.get(f,FACE*10)==payload
            with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
        except Exception:
            with OUT.open('r+b') as f:
                for at,b,a in edits:f.seek(at);f.write(b)
                f.flush();os.fsync(f.fileno())
            raise
        fix['applied']=True;report['small_portrait_is_native_kyosuke_thumbnail']=False
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    palette=np.frombuffer(payload[:1024],np.uint8).reshape(256,4)[SWIZZLE].copy()
    palette[:,3]=np.minimum(palette[:,3].astype(np.uint16)*2,255)
    Image.fromarray(palette[np.frombuffer(payload[1024:],np.uint8).reshape(128,128)]).save(ART/'small_beowulf_preview.png')
    print(json.dumps({k:v for k,v in fix.items() if k!='edits'},indent=2))



class RieseNightHeadSkin:
    """Native palette transfer; generated art is confined to matched head masks."""
    def __init__(self,f):
        actor=Archive(f,0x27D66800);attack=Archive(f,0x2970D000)
        self.native={k:pages(actor.get(f,k))[0][2] for k in (40,41,42)}
        def palette(k):
            data=actor.get(f,k);at=pages(data)[0][1]
            return np.frombuffer(data[at:at+1024],np.uint8).reshape(256,4)[SWIZZLE].copy()
        normal,night=palette(40),palette(41)
        self.night_lut={tuple(a[:3]):b[:3].copy() for a,b in zip(normal,night) if a[3] and not np.array_equal(a[:3],b[:3])}
        self.riese_colors={tuple(c) for c in np.unique(self.native[42][:,:,:3][self.native[42][:,:,3]>0],axis=0)}
        self.patterns=[];self.cache={};self.page_cache={};self.stats={'pages':0,'body_pages':0,'head_matches':0,'head_pages':0}
        def generated(path,cols,rows):
            a=np.array(Image.open(path).convert('RGBA'));cells=[]
            for i in range(cols*rows):
                cell=a[i//cols*a.shape[0]//rows:(i//cols+1)*a.shape[0]//rows,i%cols*a.shape[1]//cols:(i%cols+1)*a.shape[1]//cols]
                mask=(cell[:,:,3]>240)&(cell[:,:,:3].max(axis=2)>35)
                yy,xx=np.where(mask)
                cells.append(Image.fromarray(cell[yy.min():yy.max()+1,xx.min():xx.max()+1,:3]))
            return cells
        riese=generated(ART/'riese_head_glow_generated.png',3,1)
        # The fifth cell set has an empty sixth cell, therefore only read five.
        a=np.array(Image.open(ART/'night_head_glow_generated.png').convert('RGBA'));ordinary=[]
        for i in range(5):
            cell=a[i//3*a.shape[0]//2:(i//3+1)*a.shape[0]//2,i%3*a.shape[1]//3:(i%3+1)*a.shape[1]//3]
            mask=(cell[:,:,3]>240)&(cell[:,:,:3].max(axis=2)>35);yy,xx=np.where(mask)
            ordinary.append(Image.fromarray(cell[yy.min():yy.max()+1,xx.min():xx.max()+1,:3]))
        for i,box in enumerate(((35,130,102,179),(140,132,189,165),(171,201,203,255))):
            self.patterns.append((self.native[42][box[1]:box[3],box[0]:box[2]],riese[i],f'riese{i}'))
        for i,box in enumerate(((150,60,191,87),(2,61,43,100),(212,89,254,143),(115,211,164,251),(170,212,222,254))):
            self.patterns.append((self.native[41][box[1]:box[3],box[0]:box[2]],ordinary[i],f'night{i}'))
        combat=next(im for slot,at,im in pages(attack.get(f,840)) if slot==1)
        for box,angle in (((75,1,118,63),0),((153,3,199,37),1),((52,5,70,61),2)):
            self.patterns.append((combat[box[1]:box[3],box[0]:box[2]],riese[angle],f'combat_head{angle}'))
        dense=next(im for slot,at,im in pages(attack.get(f,842)) if slot==18)
        self.patterns.append((dense[203:255,49:89],riese[1],'cutin_head'))
        self.extra=np.array([[36,1,6],[68,2,12],[105,2,18],[145,3,24],[190,5,32],[225,8,40],
            [255,16,48],[255,40,64],[255,70,90],[255,105,120],[255,145,155],[255,200,205],
            [255,235,238],[255,250,250],[180,75,100],[95,30,55]],np.uint8)

    @staticmethod
    def matches(im,part):
        mask=part[:,:,3]>128;yy,xx=np.where(mask)
        samples=np.linspace(0,len(xx)-1,min(24,len(xx)),dtype=int)
        counts=[np.count_nonzero(np.all(im==part[yy[j],xx[j]],axis=2)) for j in samples]
        j=samples[int(np.argmin(counts))]
        if not min(counts):return []
        ay,ax=yy[j],xx[j];ys,xs=np.where(np.all(im==part[ay,ax],axis=2));h,w=mask.shape;found=[]
        for y,x in zip(ys,xs):
            y,x=int(y-ay),int(x-ax)
            if y<0 or x<0 or y+h>im.shape[0] or x+w>im.shape[1]:continue
            if np.array_equal(im[y:y+h,x:x+w][mask],part[mask]):found.append((x,y))
        return found

    def asset(self,b):
        digest=sha(b)
        if digest in self.cache:return self.cache[digest]
        out=bytearray(b);evidence=[]
        for slot,at,im in pages(b):
            self.stats['pages']+=1;h,w=im.shape[:2]
            cachekey=sha(b[at:at+1024+h*w])
            if cachekey in self.page_cache:
                palette_bytes,index_bytes,entry=self.page_cache[cachekey]
                out[at:at+1024]=palette_bytes;out[at+1024:at+1024+h*w]=index_bytes
                es=dict(entry,slot=slot);evidence.append(es)
                self.stats['body_pages']+=int(es['body_palette_transfer'])
                self.stats['head_pages']+=int(bool(es['head_matches']));self.stats['head_matches']+=len(es['head_matches'])
                continue
            raw=np.frombuffer(b[at:at+1024],np.uint8).reshape(256,4).copy();pal=raw[SWIZZLE].copy()
            idx=np.frombuffer(b[at+1024:at+1024+h*w],np.uint8).reshape(h,w).copy()
            colors=np.unique(im[im[:,:,3]>0,:3],axis=0)
            overlap=sum(tuple(c) in self.riese_colors for c in colors)/max(1,len(colors))
            body=bool(overlap>.55 or (len(np.unique(raw,axis=0))==241 and np.mean(im[:,:,3]>0)>.25))
            if body:
                for i,c in enumerate(pal[:,:3].copy()):
                    if pal[i,3] and tuple(c) in self.night_lut:pal[i,:3]=self.night_lut[tuple(c)]
                    elif pal[i,3] and int(c[0])>int(c[1])*1.3 and int(c[0])>int(c[2])*1.2 and int(c[0])-int(c[1])>=10:
                        # Same native navy palette for shaded high-colour closeups.
                        normal=np.array(list(self.night_lut),np.int32);q=np.argmin(np.sum((normal-c.astype(np.int32))**2,axis=1))
                        pal[i,:3]=self.night_lut[tuple(normal[q])]
                self.stats['body_pages']+=1
            coverage=np.zeros((h,w),bool);target=np.zeros((h,w,3),np.uint8);hits=[]
            for part,art,name in self.patterns:
                ph,pw=part.shape[:2];mask=part[:,:,3]>128
                for x,y in self.matches(im,part):
                    rgb=part[:,:,:3].astype(np.int32)
                    # Dark green shadow entries are not eyes. Saturation and
                    # brightness guards prevent red dots on the jaw/background.
                    eye=mask&(rgb[:,:,1]>=50)&(rgb[:,:,1]-rgb[:,:,0]>=15)&(rgb[:,:,1]-rgb[:,:,2]>=15)
                    if not eye.any():continue
                    aligned=pal[idx[y:y+ph,x:x+pw],:3].copy()
                    ey,ex=np.argwhere(eye).mean(axis=0)
                    def dilate(a,r):
                        padded=np.pad(a,r);return np.logical_or.reduce([padded[oy:oy+ph,ox:ox+pw] for oy in range(2*r+1) for ox in range(2*r+1)])
                    halo=dilate(eye,1)&mask
                    face=halo.copy()
                    spill=halo&~eye
                    aligned[spill]=np.clip(aligned[spill].astype(float)*[.75,.65,.65]+[40,0,0],0,255).astype(np.uint8)
                    aligned[eye]=[225,8,40]
                    bright=eye&(rgb[:,:,1]>=rgb[:,:,1][eye].max()*.8)
                    aligned[bright]=[255,145,155]
                    # Retain native jaw shading. Add a compact two-row mouth
                    # and just TWO single-pixel fangs inside a solid metal run.
                    eye_bottom=int(np.where(eye)[0].max());candidates=[]
                    metal=mask&(rgb.max(axis=2)-rgb.min(axis=2)<35)&(rgb.max(axis=2)>60)
                    for my in range(eye_bottom+2,min(ph-1,eye_bottom+6)):
                        xs=np.flatnonzero(metal[my]&(np.arange(pw)>=ex-8)&(np.arange(pw)<=ex+4))
                        runs=[]
                        for xx in xs:
                            if runs and xx==runs[-1][-1]+1:runs[-1].append(int(xx))
                            else:runs.append([int(xx)])
                        for run in runs:
                            if len(run)>=5:
                                width=min(7,len(run));mx=max(run[0],min(int(round(ex))-2-width//2,run[-1]-width+1))
                                if mask[my:my+2,mx:mx+width].all():
                                    score=abs(my-(eye_bottom+3))+.15*abs(mx+width/2-(ex-2))
                                    candidates.append((score,my,mx,width))
                    if candidates:
                        _,my,mx,width=min(candidates)
                        aligned[my,mx:mx+width]=[12,10,20];face[my,mx:mx+width]=True
                        aligned[my+1,mx+1:mx+width-1]=[12,10,20];face[my+1,mx+1:mx+width-1]=True
                        for tx in (mx+1,mx+width-2):aligned[my,tx]=[210,213,220]
                    area=coverage[y:y+ph,x:x+pw];area[face]=True
                    target[y:y+ph,x:x+pw][face]=aligned[face];hits.append((name,x,y,pw,ph))
            if hits:
                available=np.flatnonzero((pal[:,3]>0)&~np.isin(np.arange(256),idx))
                assert len(available)>=len(self.extra),(slot,len(available))
                pal[available[:len(self.extra)],:3]=self.extra
                choices=np.flatnonzero(pal[:,3]>0);rgb=target[coverage].astype(np.int32);candidate=pal[choices,:3].astype(np.int32)
                mapped=choices[np.argmin(np.sum((rgb[:,None,:]-candidate[None,:,:])**2,axis=2),axis=1)]
                idx[coverage]=mapped.astype(np.uint8)
                self.stats['head_matches']+=len(hits);self.stats['head_pages']+=1
            assert np.array_equal(idx[~coverage],np.frombuffer(b[at+1024:at+1024+h*w],np.uint8).reshape(h,w)[~coverage])
            assert np.array_equal(pal[:,3],raw[SWIZZLE,3])
            decoded_alpha=pal[idx,3];assert np.array_equal(decoded_alpha>0,im[:,:,3]>0)
            out[at:at+1024]=pal[SWIZZLE].tobytes();out[at+1024:at+1024+h*w]=idx.tobytes()
            entry=dict(slot=slot,head_matches=hits,head_pixels=int(coverage.sum()),body_palette_transfer=body)
            evidence.append(entry);self.page_cache[cachekey]=(pal[SWIZZLE].tobytes(),idx.tobytes(),entry)
        ranges=sorted((at,at+1024+im.shape[0]*256) for slot,at,im in pages(b));pos=0
        for start,end in ranges:assert out[pos:start]==b[pos:start];pos=end
        assert out[pos:]==b[pos:] and len(out)==len(b)
        self.cache[digest]=(bytes(out),evidence);return bytes(out),evidence


def riese_night_head_preview():
    with SOURCE.open('rb') as f:
        skin=RieseNightHeadSkin(f);actor=Archive(f,0x27D66800);attack=Archive(f,0x2970D000)
        original=actor.get(f,42);converted,proof=skin.asset(original)
        Image.fromarray(pages(converted)[0][2]).save(ART/'riese_night_berserk_preview.png')
        row=read(f,0x859F9000+42*144,144);keys=sorted(set(struct.unpack_from('<70H',row,4))-{0,65535});records=[]
        for key in keys:
            data,es=skin.asset(attack.get(f,key));records.append(dict(key=key,head_matches=sum(len(e['head_matches']) for e in es),evidence=es))
        report=dict(base='native Alteisen Riese actor42/bank42',colour='native night-camouflage palette40->41',stats=skin.stats,
            actor=proof,attacks=records,originals_preserved=True,ISO_applied=False,
            generated_art=['riese_head_glow_generated.png','night_head_glow_generated.png'])
        (ART/'riese_night_head_preview.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in ('attacks','actor')},ensure_ascii=False,indent=2))


def riese_night_head_update(apply=False):
    """Update only the existing separate TEST clones, never native resources."""
    import os
    path=ART/'prototype_manifest.json';m=json.loads(path.read_text(encoding='utf-8'))
    assert not m.get('riese_night_head',{}).get('applied'),'Already applied; inspect journal before rebuilding'
    expected=m['status_portrait_fix']['target_sha256']
    with OUT.open('rb') as f:before=hashlib.file_digest(f,'sha256').hexdigest()
    assert before==expected,'Unexpected TEST ISO; do not overwrite user changes'
    edits=[]
    def add(at,old,new,label):
        if old!=new:edits.append((at,old,bytes(new),label))
    with SOURCE.open('rb') as src,OUT.open('rb') as test:
        production=hashlib.file_digest(src,'sha256').hexdigest();skin=RieseNightHeadSkin(src)
        a=Archive(src,0x27D66800);ta=Archive(test,0x27D66800);aa=Archive(src,0x2970D000);taa=Archive(test,0x2970D000)
        row=read(src,0x859F9000+42*144,144);cloned=read(test,0x859F9000+BANK*144,144)
        native_ids=struct.unpack_from('<70H',row,4);cloned_ids=struct.unpack_from('<70H',cloned,4)
        mappings=dict(zip(native_ids,cloned_ids));assert mappings[0xffff]==0xffff
        data=a.get(src,42);new,_=skin.asset(data);idx=ta.mapping[BANK];dest,n=ta.entries[idx];assert n==len(data)
        assert a.get(src,42)==ta.get(test,42) and a.get(src,41)==ta.get(test,41)
        add(dest,read(test,dest,n),new,'Separate bank227 body, native Riese pixels/alpha retained outside head')
        checks=[]
        for key in sorted(set(native_ids)-{0,0xffff}):
            data=aa.get(src,key);assert data==taa.get(test,key),'Native animation was changed'
            key2=mappings[key];idx=taa.mapping[key2];dest,n=taa.entries[idx];assert n==len(data)
            new,proof=skin.asset(data);add(dest,read(test,dest,n),new,f'Separate cloned Riese attack{key}/{key2}')
            checks.append(dict(native_key=key,clone_key=key2,size=n,head_matches=sum(len(e['head_matches']) for e in proof)))
        # Restore the original native event unit578; put Beowulf's body in an
        # appended record instead of overwriting the native Unit19F.
        masters=[]
        for base in (0x5DA000,0x83F000):
            old=read(test,base,0x1A5800);original=read(src,base,0x1A5800);h=0x11E800
            unit=h+u32(old,h+0x1c);ut=h+u32(old,h+0x18);count=u32(old,unit+8);assert count==427
            origunit=h+u32(original,h+0x1c);uend=unit+u32(old,unit+4);end=h+u32(old,0x11E00C)
            body=old[unit+12+0x19f*100:unit+12+(0x19f+1)*100];assert u16(body,0x44)==BANK
            b=bytearray(old[:end]);b[unit+12+0x19f*100:unit+12+(0x19f+1)*100]=original[origunit+12+0x19f*100:origunit+12+(0x19f+1)*100]
            b[uend:uend]=body
            for field in range(0x18,0x8c,4):
                absolute=h+u32(old,h+field)
                if absolute>=uend:struct.pack_into('<I',b,h+field,u32(old,h+field)+100)
            struct.pack_into('<II',b,unit+4,u32(old,unit+4)+100,count+1)
            struct.pack_into('<I',b,ut+4,u32(old,ut+4)+100)
            struct.pack_into('<H',b,ut+12+UNIT*2,count)
            struct.pack_into('<I',b,0x11E00C,u32(old,0x11E00C)+100)
            assert not any(old[end:end+100])
            # Existing appended pilot name belongs only to the TEST Beowulf.
            st=h+u32(b,h+0x80);strings=u32(b,st+8);nameat=st+u32(b,st+12+(strings-1)*4)
            oldname=b[nameat:b.find(b'\0',nameat)+1]
            assert decode(oldname[:-1])=='베오울프　쿄스케'
            name=encode('베오울프')+b'\0';assert len(name)<=len(oldname)
            b[nameat:nameat+len(oldname)]=name+bytes(len(oldname)-len(name))
            assert b[unit+12+0x19f*100:unit+12+(0x19f+1)*100]==original[origunit+12+0x19f*100:origunit+12+(0x19f+1)*100]
            add(base+0x11E000,old[0x11E000:len(b)],b[0x11E000:],'Append independent Beowulf unit; restore original native unit578')
            masters.append(bytes(b))
        # Actual getters resolve the new record without disturbing native578.
        from validate_hidden_rewards import ram
        from r5900_scalar_check import CPU
        c=CPU(ram);c.mem[0x100000:0x49A778]=read(test,0x94880,0x39A778);master=u32(ram,0x59D360)
        blob=masters[0]
        for i,(ctxoff,field) in enumerate(((0x28,0x18),(0x40,0x1c),(0x58,0x20),(0x70,0x24),(0x88,0x28),(0xA0,0x2c))):
            rel=0x11E800+u32(blob,0x11E800+field);dest=0x1000000+i*0x100000;n=u32(blob,rel+4)
            c.mem[dest:dest+n]=blob[rel:rel+n]
            for off,value in ((0,dest),(4,u32(blob,rel)),(8,n),(12,u32(blob,rel+8)),(16,dest),(20,dest+12)):c.write(master+ctxoff+off,value,4)
        actual_bank=c.run(0x1A6690,[master,UNIT])
        print('New unit lookup:',actual_bank,'UTbl604',u16(blob,0x11E800+u32(blob,0x11E818)+12+UNIT*2),'unit427 bank',u16(blob,0x11E800+u32(blob,0x11E81C)+12+427*100+0x44),flush=True)
        assert actual_bank==BANK
        assert c.run(0x1A7D40,[master,UNIT])==50000
        assert c.run(0x1A6690,[master,0x578])==41
        assert c.run(0x1A7D40,[master,0x578])==4200
        assert c.run(0x1A2900,[master,PILOT])==FACE
    edits.sort();assert all(a+len(old)<=z for (a,old,new,label),(z,*_) in zip(edits,edits[1:]))
    feature=dict(applied=False,source_sha256=before,production_sha256=production,base_actor=42,clone_bank=BANK,
        stats=skin.stats,animation_resources=checks,native_originals_preserved=True,
        original_unit578_restored=True,new_unit_index=427,Beowulf_portrait_retained=True,
        name='베오울프',all_command_UV_alpha_bytes_preserved=True,live_battle_verified=False,
        art_tool='built-in image_gen',art_files=['riese_head_glow_generated.png','night_head_glow_generated.png'],
        edits=[dict(offset=a,before=old.hex(),after=new.hex(),label=label) for a,old,new,label in edits])
    if apply:
        import psutil
        assert not any('pcsx2' in x.info['name'].lower() for x in psutil.process_iter(['name'])),'Close PCSX2 before applying TEST'
        try:
            with OUT.open('r+b') as f:
                for at,old,new,label in edits:
                    assert read(f,at,len(old))==old,label;f.seek(at);f.write(new)
                f.flush();os.fsync(f.fileno())
        except Exception:
            with OUT.open('r+b') as f:
                for at,old,new,label in reversed(edits):f.seek(at);f.write(old)
                f.flush();os.fsync(f.fileno())
            raise
        with OUT.open('rb') as f:feature['target_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
        with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
        feature['applied']=True;m['riese_night_head']=feature
        path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    else:(ART/'riese_night_head_plan.json').write_text(json.dumps(feature,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in feature.items() if k not in ('edits','animation_resources')},ensure_ascii=False,indent=2))

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap=argparse.ArgumentParser();mode=ap.add_mutually_exclusive_group()
    mode.add_argument('--riese-night-head-update',action='store_true')
    mode.add_argument('--riese-night-head-preview',action='store_true')
    mode.add_argument('--build',action='store_true')
    mode.add_argument('--update',action='store_true',help='Update the existing guarded TEST ISO only')
    mode.add_argument('--shishio-power',action='store_true')
    mode.add_argument('--shishio-add',action='store_true')
    mode.add_argument('--status-frame-fix',action='store_true')
    mode.add_argument('--hp-match',action='store_true')
    mode.add_argument('--story-fix',action='store_true')
    mode.add_argument('--balance-fix',action='store_true')
    mode.add_argument('--voice-chunk-fix',action='store_true')
    mode.add_argument('--attack-display-fix',action='store_true')
    mode.add_argument('--playable-voice-fix',action='store_true')
    mode.add_argument('--episode6-ally-test',action='store_true')
    mode.add_argument('--episode6-test',action='store_true',help='Add Mk-III to episode 6 initial enemies in the existing TEST ISO only')
    mode.add_argument('--episode6-test-fix',action='store_true',help='Correct the test enemy to the playable battle group and difficulty flags')
    mode.add_argument('--animation-palette-fix',action='store_true',help='Preserve native animation texture indices and recolour close-up body palettes')
    mode.add_argument('--status-portrait-fix',action='store_true',help='Replace Beowulf-only status thumbnail with his native evil expression')
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    ART.mkdir(exist_ok=True)
    if args.riese_night_head_update:
        riese_night_head_update(args.apply);return
    if args.riese_night_head_preview:
        riese_night_head_preview();return
    if args.status_portrait_fix:
        status_portrait_fix(args.apply);return
    if args.animation_palette_fix:
        animation_palette_fix(args.apply);return
    if args.shishio_power:
        shishio_power(args.apply);return
    if args.shishio_add:
        shishio_add(args.apply);return
    if args.status_frame_fix:
        status_frame_fix(args.apply);return
    if args.hp_match:
        hp_match(args.apply);return
    if args.story_fix:
        story_fix(args.apply);return
    if args.balance_fix:
        balance_fix(args.apply);return
    if args.voice_chunk_fix:
        voice_chunk_fix(args.apply);return
    if args.attack_display_fix:
        attack_display_fix(args.apply);return
    if args.playable_voice_fix:
        playable_voice_fix(args.apply);return
    if args.episode6_ally_test:
        episode6_ally_test(args.apply);return
    if args.episode6_test_fix:
        episode6_test_fix();return
    if args.episode6_test:
        episode6_test();return
    edits,report=plan()
    if args.build or args.update:
        if args.update:
            previous=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'))
            assert previous.get('built') and previous['output']==str(OUT)
            for path,expected in ((SOURCE,previous['source_sha256']),(OUT,previous['target_sha256'])):
                with path.open('rb') as checked:
                    assert hashlib.file_digest(checked,'sha256').hexdigest()==expected, str(path)
        else:
            assert not OUT.exists(),'Refusing to overwrite an existing test image'
        shutil.copyfile(SOURCE,OUT)
        try:
            with OUT.open('r+b') as f:
                for at,old,new,label in edits:
                    assert read(f,at,len(old))==old,label
                    f.seek(at);f.write(new)
                f.flush()
            # Validate all bytes outside planned edits, not merely a header.
            source_hash=hashlib.sha256();target_hash=hashlib.sha256()
            with SOURCE.open('rb') as src,OUT.open('rb') as dst:
                pos=0
                for at,old,new,label in edits:
                    while pos<at:
                        n=min(4<<20,at-pos);a=src.read(n);b=dst.read(n);assert a==b
                        source_hash.update(a);target_hash.update(b);pos+=n
                    assert src.read(len(old))==old and dst.read(len(new))==new,label
                    source_hash.update(old);target_hash.update(new);pos+=len(old)
                while a:=src.read(4<<20):
                    b=dst.read(len(a));assert a==b;source_hash.update(a);target_hash.update(b)
            report.update(source_sha256=source_hash.hexdigest(),target_sha256=target_hash.hexdigest(),built=True)
        except Exception:
            OUT.unlink(missing_ok=True);raise
    (ART/'prototype_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='edits'},ensure_ascii=False,indent=2))

def normalize_beowulf_spelling(apply=False):
    """Equal-length Korean spelling repair with reversible whole-image verification."""
    import os,psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    old=encode('베어울프');new=encode('베오울프');assert len(old)==len(new)==8
    expected={SOURCE:('80a9a37bdc0ddb0322a4d72a57610d34edd88d26a5270cf35b160e0b8eedc509',32),
        OUT:('8bd677be7aa67d3e84432cfc06b52ceeb815422c7379a21c0436868e91ece856',62)}
    result=dict(old='베어울프',new='베오울프',files=[],applied=apply)
    for path,(digest,count) in expected.items():
        edits=[];pos=0;tail=b''
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==digest;f.seek(0)
            while chunk:=f.read(16<<20):
                data=tail+chunk;start=0
                while (i:=data.find(old,start))>=0:
                    at=pos-len(tail)+i
                    if not edits or at>edits[-1]['offset']:edits.append(dict(offset=at,before=old.hex(),after=new.hex()))
                    start=i+len(old)
                tail=data[-7:];pos+=len(chunk)
        assert len(edits)==count
        if apply:
            with path.open('r+b') as f:
                for e in edits:
                    f.seek(e['offset']);assert f.read(8)==old;f.seek(e['offset']);f.write(new)
                f.flush();os.fsync(f.fileno())
            reverse=hashlib.sha256();actual=hashlib.sha256();pos=0
            with path.open('rb') as f:
                for e in edits:
                    while pos<e['offset']:
                        b=f.read(min(4<<20,e['offset']-pos));reverse.update(b);actual.update(b);pos+=len(b)
                    assert f.read(8)==new;reverse.update(old);actual.update(new);pos+=8
                while b:=f.read(4<<20):reverse.update(b);actual.update(b)
            assert reverse.hexdigest()==digest,'Unexpected changes outside spelling edits'
            after=actual.hexdigest()
        else:after=None
        result['files'].append(dict(path=str(path),before_sha256=digest,after_sha256=after,count=count,edits=edits))
    (ROOT/'runtime/beowulf_spelling_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({**result,'files':[{k:v for k,v in x.items() if k!='edits'} for x in result['files']]},ensure_ascii=False,indent=2))


if __name__=='__main__':
    if '--name-spelling' in sys.argv:normalize_beowulf_spelling('--apply' in sys.argv)
    else:main()
