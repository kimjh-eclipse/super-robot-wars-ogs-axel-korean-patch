"""Beowulf TEST-only native cut-in addition and non-destructive HD pack.

Texture names reproduce PCSX2 v1.7.4005 PSMT8 block/CLUT XXH3 hashing.
Existing dumps are the independent oracle; no original replacement is overwritten.
"""
from pathlib import Path
import argparse, json, hashlib, struct, os, shutil
import numpy as np
from PIL import Image, ImageDraw
import xxhash
import build_beowulf_prototype as b

ART=b.ART
EMU=Path(r'C:\Users\OXP2\Desktop\슈퍼로봇대전 2차, 3파 알파 hd버전\pcsx2-v1.7.4005-windows-64bit-AVX2-Qt')
TEX=EMU/'textures/SLPS-25733'
STAGE=ART/'hd_pack'
COLS=np.array(json.loads((ART/'gs_psmt8_columns.json').read_text()),dtype=np.int32)
EXPECTED='44f6d62d707a6c35728927a4b03dff66fc32c97d60df9e2eb1cfd6d9142e3fed'

def indexed(data,at,h):
    pal=np.frombuffer(data[at:at+1024],np.uint8).reshape(256,4)[b.SWIZZLE].copy()
    idx=np.frombuffer(data[at+1024:at+1024+256*h],np.uint8).reshape(h,256).copy()
    return pal,idx

def texname(pal,idx,tcc=1,psm=19):
    h,w=idx.shape;assert w%16==h%16==0
    hs=xxhash.xxh3_64()
    for y in range(0,h,16):
        for x in range(0,w,16):
            z=np.empty(256,np.uint8);z[COLS]=idx[y:y+16,x:x+16].ravel();hs.update(z.tobytes())
    if psm==27:hs=xxhash.xxh3_64(idx.tobytes())
    else:assert psm==19
    bits=psm+(int(np.log2(w))<<6)+(int(np.log2(h))<<10)+(tcc<<14)
    return f'{hs.intdigest():x}-{xxhash.xxh3_64_intdigest(pal.tobytes()):x}-{bits:08x}.png'

def rgba(pal,idx):
    out=pal[idx].copy();out[:,:,3]=np.minimum(out[:,:,3].astype(np.uint16)*2,255);return out

def maskkey(im):
    im=np.array(im,dtype=np.uint8).copy();im[im[:,:,3]==0]=0;im[:,:,3]=np.where(im[:,:,3]>0,255,0)
    return (im.shape,b.sha(im.tobytes()))

def crop_scaled(im,box,scale=4):
    return im.crop(tuple(x*scale for x in box))

def palette_recolour(hd,original,target):
    """Transfer palette hue, rather than retaining the donor's red RGB residual.

    Preserve HD shading as a luminance ratio and preserve alpha byte-for-byte.
    Local native eye/jaw edits override only their own native pixel positions.
    Extrude the corrected RGB into transparent padding to prevent filter halos.
    """
    image=np.array(hd);visible=image[:,:,3]>0;native=original[:,:,3]>0
    colors,groups=np.unique(original[native,:3],axis=0,return_inverse=True)
    targets=[]
    for i in range(len(colors)):
        values,counts=np.unique(target[native,:3][groups==i],axis=0,return_counts=True)
        targets.append(values[counts.argmax()])
    targets=np.array(targets,np.uint8)
    unique,inverse=np.unique(image[visible,:3],axis=0,return_inverse=True)
    nearest=[]
    cf=colors.astype(np.float32)
    for start in range(0,len(unique),4096):
        dif=unique[start:start+4096,None,:].astype(np.float32)-cf[None,:,:]
        nearest.append(np.argmin(np.sum(dif*dif,axis=2),axis=1))
    nearest=np.concatenate(nearest)
    # Dark warm HD outlines can otherwise be mistaken for neutral native black.
    warm=(unique[:,0]>unique[:,1]*1.25)&(unique[:,0]>unique[:,2]*1.15)&(unique[:,0]>12)
    choices=np.flatnonzero((colors[:,0]>colors[:,1]*1.25)&(colors[:,0]>colors[:,2]*1.15)&(targets[:,2]>targets[:,0]))
    if len(choices) and warm.any():
        for start in range(0,len(unique),4096):
            stop=min(start+4096,len(unique));selected=np.flatnonzero(warm[start:stop])+start
            if not len(selected):continue
            dif=unique[selected,None,:].astype(np.float32)-cf[choices][None,:,:]
            nearest[selected]=choices[np.argmin(np.sum(dif*dif,axis=2),axis=1)]
    weights=np.array([.2126,.7152,.0722],np.float32)
    ratio=np.clip((unique.astype(float)@weights+1)/(colors[nearest].astype(float)@weights+1),0,2.5)
    mapped=np.clip(targets[nearest].astype(float)*ratio[:,None],0,255).astype(np.uint8)
    image[visible,:3]=mapped[inverse]
    # Keep actual native red eye glow/fangs, which intentionally differ from
    # the dominant old-index palette mapping used over most armour pixels.
    local=np.zeros(native.shape,bool);local[native]=np.any(target[native,:3]!=targets[groups],axis=1)
    special=np.array(Image.fromarray(local).resize(hd.size,Image.Resampling.NEAREST),bool)&visible
    if special.any():
        op=np.array(Image.fromarray(original[:,:,:3]).resize(hd.size,Image.Resampling.NEAREST))
        tp=np.array(Image.fromarray(target[:,:,:3]).resize(hd.size,Image.Resampling.NEAREST))
        source=np.array(hd)
        scale=np.clip((source[special,:3].astype(float)@weights+1)/(op[special].astype(float)@weights+1),0,2.5)
        image[special,:3]=np.clip(tp[special].astype(float)*scale[:,None],0,255)
    # Straight-alpha PNGs still sample RGB from zero-alpha neighbours.
    # Never leave the original red donor RGB hidden in those neighbours.
    image[~visible,:3]=0;covered=visible.copy()
    for _ in range(4):
        padded=np.pad(image[:,:,:3].astype(np.float32),((1,1),(1,1),(0,0)))
        mask=np.pad(covered,1);total=np.zeros(image.shape[:2]+(3,),np.float32);count=np.zeros(covered.shape,np.float32)
        for dy,dx in ((0,1),(2,1),(1,0),(1,2)):
            m=mask[dy:dy+image.shape[0],dx:dx+image.shape[1]]
            total+=padded[dy:dy+image.shape[0],dx:dx+image.shape[1]]*m[:,:,None];count+=m
        add=~covered&(count>0);image[add,:3]=(total[add]/count[add,None]).astype(np.uint8);covered|=add
    assert np.array_equal(image[:,:,3],np.array(hd)[:,:,3])
    intent=np.array(Image.fromarray((target[:,:,0]>target[:,:,2]*1.2)&(target[:,:,0]>target[:,:,1]*1.2)).resize(hd.size,Image.Resampling.NEAREST),bool)
    changed_warm=np.zeros(visible.shape,bool);changed_warm[visible]=warm[inverse]&(targets[nearest[inverse],2]>targets[nearest[inverse],0])
    check=changed_warm&~intent&~special
    assert np.all(image[check,2]>=image[check,0])
    return Image.fromarray(image),dict(palette_transfer='native hue + HD luminance; no donor RGB residual',
        warm_outline_pixels_corrected=int(check.sum()),alpha_identical=True,transparent_RGB_padding_corrected=True)

def aligned_cutin(data,key):
    """Only face/mouth image regions change; programs, UVs and alpha stay native."""
    out=bytearray(data);high={};changed=[]
    atlas=Image.open(ART/'beowulf_cutin_hd_generated.png').convert('RGBA').resize((2048,1024),Image.Resampling.LANCZOS)
    head=crop_scaled(atlas,(257,3,367,123))
    mouths=[crop_scaled(atlas,z) for z in ((401,1,455,29),(456,1,512,30))]
    eyes=Image.open(ART/'beowulf_cutin_eyes_hd_generated.png').convert('RGBA').resize((2048,1024),Image.Resampling.LANCZOS)
    for slot,at,original in b.pages(data):
        im=Image.fromarray(original).resize((1024,original.shape[0]*4),Image.Resampling.LANCZOS)
        area=np.zeros(original.shape[:2],bool)
        def paste(piece,box):
            x,y,r,t=box;piece=piece.resize(((r-x)*4,(t-y)*4),Image.Resampling.LANCZOS)
            im.paste(piece,(x*4,y*4));area[y:t,x:r]=original[y:t,x:r,3]>0
        if key in (592,593,600,602) and slot==1:
            paste(head,(1,3,110,123));paste(mouths[0],(145,1,199,29));paste(mouths[1],(200,1,256,30))
        elif key in (588,589,590,591,594,596,597,598,599) and slot==1:
            paste(head,(1,129,95,255));paste(mouths[0],(4,97,61,126));paste(mouths[1],(195,1,252,31))
        elif key==601 and slot in (0,1):
            im=eyes.crop((slot*1024,0,(slot+1)*1024,original.shape[0]*4));area=original[:,:,3]>0
        if not area.any():continue
        # Exact source alpha and untouched RGB outside the edited face rectangles.
        small=np.array(im.resize((256,original.shape[0]),Image.Resampling.LANCZOS))
        target=original.copy();target[area,:3]=small[area,:3]
        assert np.array_equal(target[:,:,3],original[:,:,3])
        assert np.array_equal(target[~area],original[~area])
        pal,idx=indexed(data,at,original.shape[0]);active=original[:,:,3]>0
        assert set(np.unique(pal[idx,3]))<={0,128}
        q=Image.fromarray(target[:,:,:3]).quantize(colors=255,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        colors=np.array(q.getpalette(),np.uint8).reshape(-1,3)[:255]
        npal=np.zeros((256,4),np.uint8);npal[1:len(colors)+1,:3]=colors;npal[1:,3]=128
        ni=np.array(q,dtype=np.uint16)+1;ni[~active]=0;ni=ni.astype(np.uint8)
        assert np.array_equal(npal[ni,3],pal[idx,3])
        out[at:at+1024]=npal[b.SWIZZLE].tobytes();out[at+1024:at+1024+ni.size]=ni.tobytes()
        hi=np.array(Image.fromarray(original).resize(im.size,Image.Resampling.LANCZOS))
        bigarea=np.repeat(np.repeat(area,4,axis=0),4,axis=1);paint=np.array(im)
        hi[bigarea,:3]=paint[bigarea,:3]
        hi[:,:,3]=np.array(Image.fromarray(original[:,:,3]).resize(im.size,Image.Resampling.NEAREST))
        high[slot]=Image.fromarray(hi);changed.append(slot)
    return bytes(out),high,changed

def verify_dump_hashes(f):
    dumps={p.name for p in (TEX/'dumps').glob('*.png')};hits=set()
    for archive,keys in ((b.Archive(f,0x27d66800),[227]),(b.Archive(f,0x2970d000),range(4056,4106))):
        for key in keys:
            data=archive.get(f,key)
            for slot,at,im in b.pages(data):
                pal,idx=indexed(data,at,im.shape[0]);name=texname(pal,idx,psm=27 if key==227 else 19)
                if name in dumps:hits.add(name)
    assert len(hits)>=13,len(hits)
    return len(hits)

def prepare_cutin():
    STAGE.mkdir(exist_ok=True);(ART/'cutin_native').mkdir(exist_ok=True)
    report=[]
    with b.OUT.open('rb') as f:
        current=hashlib.file_digest(f,'sha256').hexdigest()
        journal=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'))
        assert current in (EXPECTED,journal.get('pilot_cutin_hd',{}).get('target_sha256'))
        checks=verify_dump_hashes(f);a=b.Archive(f,0x758d1000)
        for key in range(588,603):
            old=a.get(f,key);new,high,slots=aligned_cutin(old,key);newkey=634+key-588
            (ART/f'cutin_native/{newkey}.bin').write_bytes(new)
            # Preserve all programs/UVs/descriptors, including unchanged images.
            rr=sorted((at,at+1024+im.shape[0]*256) for slot,at,im in b.pages(old));pos=0
            for lo,hi in rr:assert old[pos:lo]==new[pos:lo];pos=hi
            assert old[pos:]==new[pos:]
            for slot,at,im in b.pages(new):
                pal,idx=indexed(new,at,im.shape[0]);name=texname(pal,idx)
                if slot in high:
                    hi=np.array(high[slot]);hi[:,:,3]=((hi[:,:,3].astype(np.uint16)+1)//2).astype(np.uint8)
                    Image.fromarray(hi).save(STAGE/name)
                    Image.fromarray(hi).save(STAGE/texname(pal,idx,psm=27))
            report.append(dict(original=key,clone=newkey,changed_face_pages=slots,native_sha256=b.sha(new)))
    info=dict(source_sha256=EXPECTED,validated_existing_dump_hashes=checks,resources=report,
        programs_UVs_transforms_preserved=True,all_native_alpha_masks_preserved=True,original_resources_untouched=True)
    (ART/'cutin_hd_prepared.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    # Source/generated/registered, not a misleading assembled game screenshot.
    with b.OUT.open('rb') as f:
        data=b.Archive(f,0x758d1000).get(f,600);new,high,_=aligned_cutin(data,600)
        source=Image.fromarray(b.pages(data)[1][2]).crop((0,0,112,128)).resize((448,512))
        aligned=high[1].crop((0,0,448,512));sheet=Image.new('RGBA',(896,540),(45,45,45,255))
        sheet.alpha_composite(source,(0,28));sheet.alpha_composite(aligned,(448,28));d=ImageDraw.Draw(sheet)
        d.text((5,5),'Original Kyosuke',fill='white');d.text((453,5),'Beowulf / native bounds + alpha',fill='white')
        sheet.save(ART/'beowulf_cutin_alignment.png')
    print(json.dumps({k:v for k,v in info.items() if k!='resources'},indent=2))

def apply_cutin():
    import psutil
    assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    prep=json.loads((ART/'cutin_hd_prepared.json').read_text());journal=ART/'prototype_manifest.json';m=json.loads(journal.read_text(encoding='utf-8'))
    with b.SOURCE.open('rb') as f:production=hashlib.file_digest(f,'sha256').hexdigest()
    with b.OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==EXPECTED
        a=b.Archive(f,0x758d1000);assert a.count==a.slots==634
        plan=b.Plan(f);plan.cursor=max(at+n for base in (0x25120800,0x27d66800,0x2970d000,0x758d1000,0x7e67e800,0x8574e800) for at,n in b.Archive(f,base).entries)
        additions=[]
        for r in prep['resources']:
            data=(ART/f"cutin_native/{r['clone']}.bin").read_bytes();assert b.sha(data)==r['native_sha256']
            additions.append((r['clone'],data,'Independent Beowulf pilot cut-in'))
        size=plan.archive(a,additions)
        root=b.Archive(f,b.BATTLE);plan.add(root.directory+12+3*8,struct.pack('<I',size),'Cut-in child span')
        at=0x85a2f800;old=b.read(f,at,24000);row=bytearray(old[251*60:252*60]);empty=old[223*60:224*60]
        assert struct.unpack_from('<20H',empty)==(65535,)*20
        for i in range(20):
            key=b.u16(row,i*2)
            if key!=65535:
                assert 588<=key<=602;struct.pack_into('<H',row,i*2,634+key-588)
        plan.add(at+223*60,row,'Beowulf face223 now has a separate pilot cut-in list')
        from r5900_scalar_check import CPU
        c=CPU((ART/'current_user_ram.bin').read_bytes());c.mem[0x100000:0x582980]=b.read(f,0x94880,0x482980)
        obj=0x1800000;c.run(0x290e10,[obj]);table=bytearray(old);table[223*60:224*60]=row;c.mem[0x96f900:0x96f900+len(table)]=table
        assert c.run(0x290f30,[obj,58])==251 and c.run(0x290f30,[obj,223])==0
        # 290F30 returns0 for an un-special-cased group; caller retains223.
        for i in range(20):assert c.run(0x290030,[obj,223,i])&0xffff==b.u16(row,i*2)
        edits=sorted(plan.edits)
    entry=dict(applied=False,source_sha256=EXPECTED,production_sha256=production,resources=prep['resources'],
        native_cutin_getter_checks=20,validated_dump_hashes=prep['validated_existing_dump_hashes'],
        edits=[dict(offset=o,before=x.hex(),after=y.hex(),label=l) for o,x,y,l in edits])
    m['pilot_cutin_hd']=entry;journal.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        with b.OUT.open('r+b') as f:
            end=0
            for off,old,new,label in edits:
                assert off>=end;end=off+len(old);assert b.read(f,off,len(old))==old;f.seek(off);f.write(new)
            f.flush();os.fsync(f.fileno());f.seek(0);inv=hashlib.sha256();target=hashlib.sha256();pos=0
            for off,old,new,label in edits:
                while pos<off:
                    z=f.read(min(4<<20,off-pos));assert z;pos+=len(z);inv.update(z);target.update(z)
                assert f.read(len(new))==new;pos+=len(new);inv.update(old);target.update(new)
            while z:=f.read(4<<20):inv.update(z);target.update(z)
            assert inv.hexdigest()==EXPECTED
            aa=b.Archive(f,0x758d1000)
            for r in prep['resources']:assert b.sha(aa.get(f,r['clone']))==r['native_sha256']
            for key in range(634):
                assert aa.entries[key]==a.entries[key]
        with b.SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==production
    except Exception:
        with b.OUT.open('r+b') as f:
            for off,old,new,label in edits:f.seek(off);f.write(old)
        raise
    entry.update(applied=True,target_sha256=target.hexdigest(),original634_cutin_resources_preserved=True,live_playback_verified=False)
    journal.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in entry.items() if k not in ('edits','resources')},indent=2))

def prepare_pack():
    """Retain existing HD line work, transfer only the new native palette/head delta."""
    STAGE.mkdir(exist_ok=True)
    existing={p.name:p for p in (TEX/'replacements').rglob('*.png') if p.parent.name!='beowulf_mk3'}
    dumps={p.name:p for p in (TEX/'dumps').glob('*.png')}
    rows=[];done=set();missing=[];cache={}
    with b.OUT.open('rb') as f,b.SOURCE.open('rb') as src:
        newrow=struct.unpack('<70H',b.read(f,0x859f9000+227*144+4,140));oldrow=struct.unpack('<70H',b.read(f,0x859f9000+42*144+4,140));mapping=dict(zip(newrow,oldrow))
        pairs=[(b.Archive(f,0x27d66800),227,b.Archive(src,0x27d66800),42)]
        a=b.Archive(f,0x2970d000);oa=b.Archive(src,0x2970d000)
        pairs.extend((a,k,oa,mapping[k]) for k in range(4056,4106))
        for ar,key,original_ar,original_key in pairs:
            data=ar.get(f,key);old=original_ar.get(src,original_key);oldpages={s:(at,p) for s,at,p in b.pages(old)}
            for slot,at,target in b.pages(data):
                pal,idx=indexed(data,at,target.shape[0]);psm=27 if key==227 else 19;name=texname(pal,idx,psm=psm)
                if name in done:continue
                done.add(name);opos,original=oldpages[slot];op,oi=indexed(old,opos,original.shape[0]);oname=texname(op,oi,psm=psm)
                if name==oname:continue
                if oname not in existing:
                    missing.append(dict(resource=key,slot=slot,name=name));continue
                source=existing[oname]
                if source not in cache:cache[source]=Image.open(source).convert('RGBA')
                hd=cache[source];assert hd.width%256==0 and hd.height%original.shape[0]==0
                assert hd.width//256==hd.height//original.shape[0]>=2
                image,proof=palette_recolour(hd,original,target)
                image.save(STAGE/name)
                rows.append(dict(kind='machine',name=name,source_HD=str(source),size=list(hd.size),observed_dump=name in dumps,colour_validation=proof))
        # Captured face textures: actual GPU128x128 canvases, including CLUT debris.
        files=[Path(x) for x in json.loads((ART/'hd_dump_index.json').read_text(encoding='utf-8'))]
        portrait=Image.open(ART/'beowulf_portrait_hd_generated.png').convert('RGB')
        talking=portrait.copy();mouth=Image.open(ART/'beowulf_portrait_talking_hd_generated.png').convert('RGB').resize(portrait.size,Image.Resampling.LANCZOS)
        box=tuple(int(k*portrait.width) for k in (.36,.70,.69,.86));talking.paste(mouth.crop(box),box[:2])
        face=b.Archive(f,0x1a2f3000);raw=[]
        for key in (1874,1875):
            z=face.get(f,key);pal=np.frombuffer(z[:1024],np.uint8).reshape(256,4)[b.SWIZZLE]
            raw.append(pal[np.frombuffer(z[1024:],np.uint8).reshape(112,112)])
        for index in (9,24,30):
            source=files[index];im=np.array(Image.open(source).convert('RGBA'));assert im.shape==(128,128,4)
            if index in (9,24):
                which=1 if index==9 else 0;assert np.array_equal(im[:100,:100,:3],raw[which][:100,:100,:3])
                size=400
            else:
                small=b.Archive(f,0x1b12d800).get(f,2230);pal=np.frombuffer(small[:1024],np.uint8).reshape(256,4)[b.SWIZZLE]
                assert np.array_equal(im[:,:,:3],pal[np.frombuffer(small[1024:],np.uint8).reshape(128,128),:3]);size=512
            hi=np.array(Image.fromarray(im).resize((512,512),Image.Resampling.NEAREST))
            image=talking if index==9 else portrait
            hi[:size,:size,:3]=np.array(image.resize((size,size),Image.Resampling.LANCZOS))
            Image.fromarray(hi).save(STAGE/source.name)
            rows.append(dict(kind='portrait',name=source.name,size=[512,512],observed_dump=True))
    # Include the new native cut-in pages under reproducible emulator filenames.
    cutin=json.loads((ART/'cutin_hd_prepared.json').read_text())
    with b.OUT.open('rb') as f:
        aa=b.Archive(f,0x758d1000)
        for rr in cutin['resources']:
            data=aa.get(f,rr['clone'])
            for slot,at,im in b.pages(data):
                if slot not in rr['changed_face_pages']:continue
                p,idx=indexed(data,at,im.shape[0])
                for psm in (19,27):
                    name=texname(p,idx,psm=psm)
                    if any(r['name']==name for r in rows):continue
                    assert (STAGE/name).exists();image=Image.open(STAGE/name);assert image.getextrema()[-1][1]<=128
                    rows.append(dict(kind='pilot_cutin',name=name,size=list(image.size),observed_dump=False,native_asset=rr['clone'],slot=slot,GS_pixel_format=psm))
    assert sum(r['observed_dump'] and r['kind']=='machine' for r in rows)>=12
    report=dict(files=rows,missing_existing_HD_sources=missing,overwrite_original_HD_files=False,
        GS_alpha_range=[0,128],live_HD_playback_verified=False)
    (ART/'hd_pack_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(files=len(rows),machine=sum(r['kind']=='machine' for r in rows),portraits=3,
        pilot_cutin=sum(r['kind']=='pilot_cutin' for r in rows),observed_dump_files=sum(r['observed_dump'] for r in rows),
        missing_existing_HD_sources=len(missing)),indent=2))

def install_pack():
    report=json.loads((ART/'hd_pack_manifest.json').read_text(encoding='utf-8'))
    destination=TEX/'replacements/beowulf_mk3';destination.mkdir(exist_ok=True)
    originals={p.name:p for p in (TEX/'replacements').rglob('*.png') if p.parent!=destination}
    for r in report['files']:
        assert r['name'] not in originals,('Would conflict with an original HD texture',r['name'])
        source=STAGE/r['name'];image=Image.open(source);assert image.mode=='RGBA' and list(image.size)==r['size']
        target=destination/r['name'];shutil.copy2(source,target);assert b.sha(source.read_bytes())==b.sha(target.read_bytes())
    report.update(installed=True,destination=str(destination),installed_count=len(report['files']))
    (ART/'hd_pack_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(installed_count=report['installed_count'],destination=str(destination),original_HD_files_preserved=True),ensure_ascii=False,indent=2))

def story_display_fix(apply=False):
    """Complete scenario portrait metadata and reflow only added dialogue."""
    from build_hidden_rewards import Scripts,MAP
    from r5900_scalar_check import CPU
    ram=(ART/'story_portrait_ram.bin').read_bytes()
    edits=[];notes=[]
    with b.OUT.open('rb') as f:
        source_hash=hashlib.file_digest(f,'sha256').hexdigest()
        table=0x1e7ee000;stride=760
        native=b.read(f,table+58*stride,stride)
        old=b.read(f,table+223*stride,stride)
        assert not any(old),'Unexpected existing scenario portrait metadata'
        normal,talking=struct.unpack_from('<2H',native,18*2)
        assert (normal,talking)==(348,349)
        new=bytearray(native)
        for expr in range(32):struct.pack_into('<H',new,expr*2,talking if expr%2 else normal)
        edits.append((table+223*stride,old,bytes(new),'Scenario face223 expression metadata'))
        c=CPU(ram);obj=0x86ab70;ptr=c.read(obj+8,4)
        assert c.read(obj+0xb94,4)==3
        assert c.run(0x2ab970,[obj,223,0,0])==-1,'Reproduce missing scenario face'
        c.mem[ptr+223*stride:ptr+224*stride]=new
        for expr in range(32):
            want=c.run(0x2ab970,[obj,58,19 if expr%2 else 18,0])
            assert c.run(0x2ab970,[obj,223,expr,0])==want
        scripts=Scripts(b.OUT)
        journal=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'))
        for chapter in journal['story_fix']['chapters']:
            n=chapter['script'];at,size=scripts.logos[n]
            ts=scripts.texts(n);nc=b.u32(scripts.data,at+0x40)
            bylabel={r[1]:r for off,r in scripts.records(n) if r[0]==0x30}
            for msg in chapter['messages']:
                r=bylabel[msg['label']];assert r[4]==msg['speaker']
                off,oldtext=ts[r[2]-nc]
                text=oldtext.replace('@','　');lines=[]
                while len(text)>20:
                    cut=text.rfind('　',6,21)
                    assert cut>=0,'Never split a word or enlarge a string slot'
                    lines.append(text[:cut]);text=text[cut+1:]
                lines.append(text);assert len(lines)<=3
                newtext='@'.join(lines);oldraw=b.encode(oldtext)+b'\0';newraw=b.encode(newtext)+b'\0'
                assert b.decode(newraw[:-1])==newtext and len(newraw)<=len(oldraw)
                if oldtext!=newtext:
                    edits.append((MAP+off,oldraw,newraw.ljust(len(oldraw),b'\0'),'Added story line width'))
                notes.append(dict(script=n,label=msg['label'],speaker=msg['speaker'],old=oldtext,new=newtext))
        assert len(notes)==60
        for off,old,new,label in edits:assert b.read(f,off,len(old))==old
    edits.sort()
    report=dict(applied=False,source_sha256=source_hash,scenario_portrait_queries=32,
        original_face58_preserved=True,added_dialogue_checked=60,max_line_characters=20,
        commands_pointers_branches_and_other_dialogue_unchanged=True,messages=notes,
        edits=[dict(offset=o,before=x.hex(),after=y.hex(),label=l) for o,x,y,l in edits])
    journal['story_display_fix']=report
    (ART/'prototype_manifest.json').write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if not apply:
        print(json.dumps({k:v for k,v in report.items() if k not in ('edits','messages')},indent=2));return
    import psutil
    assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    with b.OUT.open('r+b') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==source_hash
        for off,old,new,label in edits:
            assert b.read(f,off,len(old))==old;f.seek(off);f.write(new)
        f.flush();os.fsync(f.fileno());f.seek(0)
        inverse=hashlib.sha256();target=hashlib.sha256();pos=0
        for off,old,new,label in edits:
            while pos<off:
                chunk=f.read(min(4<<20,off-pos));assert chunk;inverse.update(chunk);target.update(chunk);pos+=len(chunk)
            assert f.read(len(new))==new;inverse.update(old);target.update(new);pos+=len(new)
        while chunk:=f.read(4<<20):inverse.update(chunk);target.update(chunk)
        assert inverse.hexdigest()==source_hash
    report.update(applied=True,target_sha256=target.hexdigest(),only_planned_bytes_changed=True)
    (ART/'prototype_manifest.json').write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('edits','messages')},indent=2))

def verify_installed():
    journal=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'));m=journal['pilot_cutin_hd']
    edits=sorted((e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits'])
    with b.OUT.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==m['target_sha256'];f.seek(0)
        inverse=hashlib.sha256();pos=0
        for at,old,new in edits:
            while pos<at:
                z=f.read(min(4<<20,at-pos));assert z;pos+=len(z);inverse.update(z)
            assert f.read(len(new))==new;inverse.update(old);pos+=len(new)
        while z:=f.read(4<<20):inverse.update(z)
        assert inverse.hexdigest()==m['source_sha256'];matches=verify_dump_hashes(f)
        a=b.Archive(f,0x758d1000);assert a.count==649
        with b.SOURCE.open('rb') as src:
            assert hashlib.file_digest(src,'sha256').hexdigest()==m['production_sha256']
            original=b.Archive(src,0x758d1000);assert original.count==634
            for key in range(634):assert a.get(f,key)==original.get(src,key)
        row=b.read(f,0x85a2f800+223*60,60)
        for k in struct.unpack_from('<20H',row):assert k==65535 or 634<=k<=648
        for r in m['resources']:
            old=a.get(f,r['original']);new=a.get(f,r['clone']);assert b.sha(new)==r['native_sha256']
            for op,npag in zip(b.pages(old),b.pages(new)):
                assert op[:2]==npag[:2] and np.array_equal(op[2][:,:,3],npag[2][:,:,3])
    pack=json.loads((ART/'hd_pack_manifest.json').read_text(encoding='utf-8'));destination=Path(pack['destination'])
    assert pack['installed'] and len(pack['files'])==27
    for r in pack['files']:
        path=destination/r['name'];assert b.sha(path.read_bytes())==b.sha((STAGE/r['name']).read_bytes())
        im=Image.open(path);assert list(im.size)==r['size'] and im.mode=='RGBA' and im.getextrema()[-1][1]<=128
    result=dict(passed=True,TEST_sha256=m['target_sha256'],original634_cutins_byte_identical=True,
        clone_programs_and_all_alpha_masks_preserved=True,actual_dump_filename_hash_matches=matches,
        installed_HD_textures=27,production_ISO_unchanged=True,live_battle_verified=False)
    (ART/'hd_installed_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

def package_hd():
    """Ship the verified final additions without rebuilding or modifying an ISO."""
    import zipfile
    manifest=json.loads((ART/'hd_pack_manifest.json').read_text(encoding='utf-8'))
    assert manifest['outline_colour_fix']['installed']
    assert len(manifest['files'])==27
    installed=Path(manifest['destination']);payload={};rows=[]
    for row in manifest['files']:
        name=row['name'];assert Path(name).name==name and name.endswith('.png')
        source=STAGE/name;raw=source.read_bytes()
        assert raw==(installed/name).read_bytes(),f'Final installed texture differs: {name}'
        with Image.open(source) as im:
            im.verify()
        with Image.open(source) as im:
            assert im.mode=='RGBA' and list(im.size)==row['size']
            assert im.getextrema()[-1][1]<=128,'Preserve GS alpha convention'
        target='textures/SLPS-25733/replacements/beowulf_mk3/'+name
        assert target not in payload;payload[target]=raw
        rows.append(dict(file=target,kind=row['kind'],size=row['size'],sha256=hashlib.sha256(raw).hexdigest()))
    guide='''OGs 액셀 패치 — 베오울프·게슈펜스트 Mk-Ⅲ HD 추가팩 v20261106

이 파일은 PCSX2용 선택 설치 HD 텍스처 추가팩입니다.
기존 OGs 전체 HD팩을 포함하지 않습니다. 기존 HD팩과 함께 사용할 수 있습니다.
기체 이미지 16개, 베오울프 초상화 3개, 컷인 텍스처 8개(형식별 변형 포함), 총 PNG 27개입니다.
붉은 외곽선 보정본을 포함합니다. ISO·세이브·에뮬레이터는 포함하지 않습니다.

1. 먼저 게임 패치 적용
v20261105 액셀 패치를 적용한 ISO를 사용하세요.
베오울프가 적으로 등장하도록 하려면 빠른 패처에서 '베오울프 등장' 옵션도 켜세요.
이 HD팩 자체는 캐릭터를 합류시키거나 시나리오를 변경하지 않습니다.
ISO에 xdelta를 한 번 더 적용하는 파일이 아닙니다.

2. 텍스처 경로 확인
PCSX2를 종료하기 전에 Settings(설정) → Graphics(그래픽) → Texture Replacement에서
Search Directory(검색 폴더)를 확인하거나 Open을 눌러 실제 폴더를 확인하세요.
본 팩의 파일명·폴더 구성은 PCSX2 1.7.4005 환경 기준입니다. 에뮬레이터를 바꿀 필요는 없습니다.

3. 파일 복사
PCSX2를 종료하고 이 ZIP을 임시 폴더에 풉니다.
검색 폴더가 기본 textures 폴더라면 ZIP의 textures 폴더를 에뮬레이터 폴더에 합쳐 복사합니다.
검색 폴더를 따로 지정했다면 ZIP의 textures 안에 있는 SLPS-25733 폴더를 그 검색 폴더에 넣습니다.

최종 구조:
<실제 검색 폴더>/SLPS-25733/replacements/beowulf_mk3/*.png

예: pcsx2-qt.exe 옆 textures를 사용하는 경우
<PCSX2 폴더>/textures/SLPS-25733/replacements/beowulf_mk3/*.png

textures/textures처럼 폴더를 두 번 만들지 마세요.
PNG 이름은 게임의 텍스처 해시이므로 바꾸지 마세요.
기존 replacements 폴더를 삭제하거나 통째로 교체하지 말고 폴더를 합쳐 주세요.
같은 beowulf_mk3 폴더가 이미 있다면 먼저 검색 폴더 밖에 백업하고 이 팩으로 교체하세요.

4. PCSX2 설정
Settings → Graphics → Texture Replacement의 Load Textures를 켭니다.
한국어 UI에서는 '텍스처 불러오기/텍스처 교체 불러오기'에 해당합니다.
게임별 그래픽 설정을 쓰는 경우 그 설정에서도 활성화되어 있는지 확인하세요.
Direct3D 11/12, Vulkan, OpenGL 등 하드웨어 렌더러를 사용하세요.
Dump Textures는 제작용 덤프 기능이므로 설치·사용에 켤 필요가 없습니다.
확인한 1.7.4005 설정 키는 LoadTextureReplacements = true입니다.
기존 해상도·HD팩·나머지 그래픽 설정은 그대로 사용하시면 됩니다.

5. 실행 및 확인
게임을 새로 부팅하고 게임 내 메모리카드 세이브로 불러오세요.
ISO 패치도 업데이트했다면 이전 세이브 스테이트는 사용하지 마세요.
베오울프가 등장하는 화면에서 기체·초상화·컷인의 HD 교체를 확인합니다.
컷인은 해당 공격 연출에서만 나오며 모든 무장·모든 프레임에서 표시되는 것은 아닙니다.

6. 적용되지 않을 때
실제 검색 폴더와 SLPS-25733/replacements/beowulf_mk3 위치부터 확인하세요.
ZIP을 풀지 않고 그대로 두거나 폴더를 이중으로 넣으면 적용되지 않습니다.
Load Textures가 게임별 설정에서 꺼져 있지 않은지 확인하세요.
다른 추가팩에 같은 PNG 이름이 있다면 중복 파일을 검색 폴더 밖으로 옮겨 비교하세요.
이 팩은 베오울프·Mk-Ⅲ 추가 이미지용이며 다른 기체의 HD 적용 여부와 별개입니다.

7. 제거 및 복원
PCSX2를 종료하고 beowulf_mk3 폴더만 텍스처 검색 폴더 밖으로 옮기거나 삭제하세요.
이름만 바꾸어 replacements 안에 두면 계속 읽힐 수 있습니다.
기존 beowulf_mk3를 백업했다면 백업을 복원합니다.
ISO와 게임 내 세이브는 수정되지 않으며 기본 게임 그래픽으로 돌아갑니다.

다운로드 및 ISO 패치:
https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/tag/v20261105

검증: 27개 PNG 열기·해상도·RGBA/GS 알파·설치본 동일성, ZIP CRC와 SHA256 검증.
모든 무장·모든 화면을 새로 실플레이한 검증을 뜻하지는 않습니다.
'''
    payload['설치방법.txt']=guide.replace('\n','\r\n').encode('utf-8-sig')
    info=dict(version='v20261106',game_serial='SLPS-25733',ISO_patch='v20261105',texture_count=27,
        machine=16,portrait=3,pilot_cutin=8,outline_colour_fix=True,files=rows)
    payload['텍스처_목록.json']=json.dumps(info,ensure_ascii=False,indent=2).encode('utf-8')
    sums=''.join(hashlib.sha256(raw).hexdigest().upper()+'  '+name+'\n' for name,raw in sorted(payload.items()))
    payload['SHA256SUMS.txt']=sums.encode('utf-8-sig')
    out=b.ROOT/'dist/SRWOGS_Beowulf_MkIII_HD_Addon_v20261106.zip'
    assert not out.exists(),'Do not overwrite a published artifact'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(payload.items()):z.writestr(name,raw)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(payload)
        for name,raw in payload.items():assert z.read(name)==raw
    report=dict(version='v20261106',file=str(out),bytes=out.stat().st_size,
        sha256=hashlib.sha256(out.read_bytes()).hexdigest().upper(),texture_count=27,
        installed_files_identical=True,ZIP_and_checksums_verified=True,status='PREPARED')
    (ART/'hd_release_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ART/'HD_INSTALL.txt').write_text(guide,encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare-cutin',action='store_true');ap.add_argument('--apply-cutin',action='store_true');ap.add_argument('--prepare-pack',action='store_true');ap.add_argument('--install-pack',action='store_true');ap.add_argument('--verify-installed',action='store_true');ap.add_argument('--story-display-fix',action='store_true');ap.add_argument('--apply',action='store_true');ap.add_argument('--package-hd',action='store_true');args=ap.parse_args()
    if args.package_hd:package_hd();raise SystemExit(0)
    if args.story_display_fix:story_display_fix(args.apply)
    if args.prepare_cutin:prepare_cutin()
    if args.apply_cutin:apply_cutin()
    if args.prepare_pack:prepare_pack()
    if args.install_pack:install_pack()
    if args.verify_installed:verify_installed()
