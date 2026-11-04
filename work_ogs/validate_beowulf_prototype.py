"""Independent container bounds, original resource preservation and native CPU checks."""
from pathlib import Path
import hashlib,json,struct
import numpy as np
from build_beowulf_prototype import SOURCE,ART,BANK,PILOT,UNIT,Archive,pages,plan,read,u32

class Overlay:
    def __init__(self,f,edits):self.f=f;self.edits=edits;self.pos=0
    def seek(self,p):self.pos=p
    def read(self,n):
        at=self.pos;self.f.seek(at);b=bytearray(self.f.read(n));self.pos+=len(b)
        for start,old,new,label in self.edits:
            lo=max(start,at);hi=min(start+len(new),at+len(b))
            if lo<hi:b[lo-at:hi-at]=new[lo-start:hi-start]
        return bytes(b)

def main():
    edits,report=plan()
    checks={}
    with SOURCE.open('rb') as src:
        patched=Overlay(src,edits)
        for name,base in [('idle',0x27D66800),('attack',0x2970D000),('portraits',0x1A2F3000),('small_portraits',0x1B12D800)]:
            old=Archive(src,base);new=Archive(patched,base)
            assert new.mapping[:old.slots]==old.mapping or name in ('idle','portraits')
            if name=='idle':
                assert all(a==b for i,(a,b) in enumerate(zip(old.mapping,new.mapping)) if i!=BANK)
            if name=='portraits':assert new.mapping[:old.slots]==old.mapping
            for i,(at,n) in enumerate(old.entries):
                other,z=new.entries[i];assert n==z
                assert read(src,at,n)==read(patched,other,z),(name,i)
            checks[name+'_original_payloads_preserved']=len(old.entries)
        old=Archive(src,0x2970D000);new=Archive(patched,0x2970D000)
        oldrow=read(src,0x859F9000+42*144,144);newrow=read(patched,0x859F9000+BANK*144,144)
        assets=dict(zip(struct.unpack_from('<70H',oldrow,4),struct.unpack_from('<70H',newrow,4)))
        total=0
        for key,other in assets.items():
            if key==0xffff:assert other==0xffff;continue
            a=old.get(src,key);b=new.get(patched,other);assert len(a)==len(b)
            ranges=[]
            for (slot,start,im),(slot2,start2,im2) in zip(pages(a),pages(b)):
                assert slot==slot2 and start==start2 and im.shape==im2.shape
                assert np.array_equal(im[:,:,3],im2[:,:,3]),key
                # Palette-dependent frame commands require original index bytes,
                # CLUT entry positions and alpha, not only a decoded mask.
                assert a[start+1024:start+1024+im.shape[0]*256]==b[start+1024:start+1024+im.shape[0]*256],key
                assert a[start+3:start+1024:4]==b[start+3:start+1024:4],key
                ranges.append((start,start+1024+im.shape[0]*256))
            pos=0
            for start,end in sorted(ranges):assert a[pos:start]==b[pos:start];pos=end
            assert a[pos:]==b[pos:];total+=1
        checks['animation_programs_UVs_transforms_original']=total
        for base in (0x5DA000,0x83F000):
            for off,n in ((0x11F8A4+0x44*100,100),(0x13B490+114*148,148)):
                assert read(src,base+off,n)==read(patched,base+off,n)
        # Execute the real R5900 getters/resolver, not a Python reimplementation.
        from validate_hidden_rewards import ram
        from r5900_scalar_check import CPU
        c=CPU(ram);c.mem[0x100000:0x49A778]=read(src,0x94880,0x39A778)
        # Initializer compression must reproduce all registers, FPR values
        # and writes before any helper is allowed to occupy reclaimed bytes.
        for seed in (0,1,0x12345678):
            oldcpu=CPU(ram);newcpu=CPU(ram)
            oldcpu.mem[0x100000:0x49A778]=read(src,0x94880,0x39A778)
            newcpu.mem[0x100000:0x49A778]=read(patched,0x94880,0x39A778)
            for cpu in (oldcpu,newcpu):
                for r in range(2,11):cpu.r[r]=0x540000
                cpu.fpr=[(seed+i*12347)&0xffffffff for i in range(32)]
                cpu.run(0x200104,stop=0x200270)
            assert oldcpu.r==newcpu.r and oldcpu.fpr==newcpu.fpr
            addresses={(a,n) for a,n,pc in oldcpu.writes}|{(a,n) for a,n,pc in newcpu.writes}
            for a,n in addresses:assert oldcpu.mem[a:a+n]==newcpu.mem[a:a+n],hex(a)
            assert {(a,n) for a,n,pc in oldcpu.writes}=={(a,n) for a,n,pc in newcpu.writes}
        checks['reclaimed_initializer_GPR_FPR_all_stores_equivalent']=True
        master=u32(ram,0x59D360)
        blob=read(patched,0x5DA000,0x190000)
        for offset,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),(0x70,0x12BF7C),(0x88,0x13A478),(0xA0,0x13B484)):
            dest=c.read(master+offset,4);size=u32(blob,rel+4)
            c.mem[dest:dest+size]=blob[rel:rel+size]
        assert c.run(0x1A6690,[master,UNIT])==BANK
        assert c.run(0x1A6690,[master,0x578])==BANK
        assert c.run(0x1A37C0,[master,PILOT])==1
        assert c.run(0x1A2900,[master,PILOT])==223
        obj=0x1780000;c.run(0x290E10,[obj]);dest=c.read(obj+0x24,4)
        c.mem[dest:dest+43200]=read(patched,0x859F9000,43200)
        for key in struct.unpack_from('<16H',blob,0x11F8A4+0x19F*100+0x24):
            if key==0xffff:continue
            motion=c.run(0x1A4A20,[master,key]);asset=c.run(0x290C90,[obj,BANK,motion])
            assert asset>=4056 and asset<4106,(hex(key),motion,asset)
        checks['native_unit_pilot_face_animation_getters']=True
        checks['normal_kyosuke_and_riese_records_preserved']=True
        # Every original UNTD record and difficulty mask survives unchanged.
        unit_old=Archive(src,0xC10800+0x5070000)
        unit_new=Archive(patched,0xC10800+0x5070000)
        added=0
        for i,(at,n) in enumerate(unit_old.entries):
            original=read(src,at,n);other,z=unit_new.entries[i];data=read(patched,other,z)
            if original==data:continue
            count=u32(original,40);newcount=u32(data,40)
            assert data[:40]==original[:40] and data[44:44+count*336]==original[44:]
            assert newcount>count and len(data)==44+newcount*336
            for j in range(count,newcount):
                row=data[44+j*336:44+(j+1)*336]
                assert u32(row)==UNIT and u32(row,32)==PILOT and u32(row,8) in (2,3)
                added+=1
        assert added==17
        checks['new_enemy_rows_with_original_stage_rows_preserved']=added
    # The original absent-target branch lands directly on 2D8C20. Exercise
    # the complete native handler so a companion hook cannot be bypassed.
    fixture=ART/'pcsx2/sstates/SLPS-25733 (4F84953E).04.p2s'
    if fixture.exists():
        from validate_hidden_rewards import load_ram,command
        rr=load_ram(fixture);scripts=__import__('build_hidden_rewards').Scripts()
        logo,_=scripts.logos[136];off=u32(scripts.data,logo+0x2c)
        main=rr.find(scripts.data[logo+off:logo+off+192]);assert main>=0
        combined=main-u32(scripts.data,logo+0x20)*96
        found=[];pos=0
        while True:
            pos=rr.find(struct.pack('<I',combined),pos)
            if pos<0:break
            ctx=pos-0x6254;pos+=4
            if 0<ctx<0x1f00000 and 0x100000<u32(rr,ctx+0x310c)<0x2000000:found.append(ctx)
        assert len(found)==1
        ctx=found[0];rec=0x1900000
        with SOURCE.open('rb') as sf:
            native=read(sf,0x94880,0x39a778)
            from build_beowulf_prototype import retirement_hook
            patches,_=retirement_hook(sf)
        for pilot in (0x41f,0x7ff):
            before=CPU(rr);after=CPU(rr)
            for cpu in (before,after):
                cpu.mem[0x100000:0x49a778]=native
                cpu.mem[rec:rec+96]=struct.pack('<24I',*command(0x81,0x100a5,pilot,0xce))
                cpu.write(ctx+0x8ed8,0,4)
                for reg in range(16,24):cpu.r[reg]=(0x123456789abc0000+reg)<<64|reg
            for at,data,label in patches:
                pc=at-0x94880+0x100000;after.mem[pc:pc+len(data)]=data
            assert before.run(0x2d8ac0,[ctx,rec])==5
            assert after.run(0x2d8ac0,[ctx,rec])==5
            assert before.r[16:24]==after.r[16:24]
            assert before.read(ctx+0x8ed8,4)==after.read(ctx+0x8ed8,4)==1
            # Scratch stack and deliberately different executable bytes are
            # excluded; every persistent data byte must remain identical.
            for lo,hi in ((0,0x100000),(0x49a778,0x1ef0000),(0x1f10000,len(rr))):
                assert before.mem[lo:hi]==after.mem[lo:hi]
        checks['native_absent_Alfimi_and_unrelated_actor_handler_preserved']=True
    checks['GPU_playthrough']=False
    checks['GPU_partial_fixture_capture']='gpu_actual_battle.jpg' if (ART/'gpu_actual_battle.jpg').exists() else None
    checks['GPU_partial_fixture_scope']='Bank227 idle/defence displayed; chain-gun attack progressed to damage and counterattack. Temporary actor identity/range override, no Alfimi encounter playthrough.'
    (ART/'validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2))


def validate_riese_night_head():
    from build_beowulf_prototype import OUT,SWIZZLE,read,u16,MAP
    report=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'))
    m=report['riese_night_head']
    assert m['applied']
    ally=report.get('episode6_ally_test',{})
    extra=[ally] if ally.get('applied') else []
    edits=sorted((e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits']+extra)
    target_sha256=ally['target_sha256'] if extra else m['target_sha256']
    if extra:
        assert ally['source_sha256']==m['target_sha256']
        with OUT.open('rb') as f:
            stage=Archive(f,MAP+0x5070000);at,size=stage.entries[78];data=read(f,at,size)
            assert u32(data,40)==41
            rows=[data[44+i*336:44+(i+1)*336] for i in range(41)]
            testrows=[r for r in rows if u32(r)==0x604]
            assert len(testrows)==1
            r=testrows[0]
            assert (u32(r,4),u32(r,8),u32(r,16),u32(r,20),u32(r,32),u32(r,52))==(6,0,16,7,0x603,7)
            template=bytearray(rows[24])
            for off in (0,16,20,32):template[off:off+4]=r[off:off+4]
            assert template==r
    before=hashlib.sha256();after=hashlib.sha256();pos=0
    with OUT.open('rb') as f:
        for at,old,new in edits:
            while pos<at:
                raw=f.read(min(4<<20,at-pos));assert raw;before.update(raw);after.update(raw);pos+=len(raw)
            raw=f.read(len(new));assert raw==new,hex(at);before.update(old);after.update(raw);pos+=len(raw)
        while raw:=f.read(4<<20):before.update(raw);after.update(raw)
    assert before.hexdigest()==m['source_sha256'] and after.hexdigest()==target_sha256
    checked=0;pages_checked=0
    with SOURCE.open('rb') as src,OUT.open('rb') as test:
        assert hashlib.file_digest(src,'sha256').hexdigest()==m['production_sha256']
        original_actor=Archive(src,0x27D66800);new_actor=Archive(test,0x27D66800)
        for key in (40,41,42):assert original_actor.get(src,key)==new_actor.get(test,key)
        original_attack=Archive(src,0x2970D000);new_attack=Archive(test,0x2970D000)
        assert read(src,0x859F9000+42*144,144)==read(test,0x859F9000+42*144,144)
        pairs=[(original_actor.get(src,42),new_actor.get(test,227))]
        for item in m['animation_resources']:
            native=item['native_key'];clone=item['clone_key']
            assert original_attack.get(src,native)==new_attack.get(test,native)
            pairs.append((original_attack.get(src,native),new_attack.get(test,clone)));checked+=1
        for a,b in pairs:
            assert len(a)==len(b);ranges=[]
            for (s,at,im),(s2,at2,newim) in zip(pages(a),pages(b)):
                assert (s,at,im.shape)==(s2,at2,newim.shape)
                assert np.array_equal(im[:,:,3],newim[:,:,3])
                assert a[at+3:at+1024:4]==b[at+3:at+1024:4]
                ranges.append((at,at+1024+im.shape[0]*256));pages_checked+=1
            off=0
            for start,end in sorted(ranges):assert a[off:start]==b[off:start];off=end
            assert a[off:]==b[off:]
        for base in (0x5DA000,0x83F000):
            old=read(src,base,0x1A5800);new=read(test,base,0x1A5800);h=0x11E800
            ou=h+u32(old,h+0x1C);nu=h+u32(new,h+0x1C);ut=h+u32(new,h+0x18)
            assert new[nu+12+0x19F*100:nu+12+0x1A0*100]==old[ou+12+0x19F*100:ou+12+0x1A0*100]
            assert new[nu+12+0x44*100:nu+12+0x45*100]==old[ou+12+0x44*100:ou+12+0x45*100]
            assert u16(new,ut+12+0x604*2)==427 and u16(new,ut+12+0x578*2)==0x19F
    result=dict(passed=True,source_sha256=m['source_sha256'],target_sha256=target_sha256,episode6_ally_verified=bool(extra),
        original_native_actors_preserved=[40,41,42],original_attack_resources_preserved=checked,
        texture_pages_alpha_and_commands_verified=pages_checked,full_inverse_journal_hash_verified=True,
        original_native_unit578_and_Riese_records_preserved=True,Beowulf_is_independent_unit=True,
        live_battle_verified=False)
    (ART/'riese_night_head_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

def validate_story_blob(old,new,notes,ram,allowed_commands=()):
    """Independent index/branch/text preservation checks, using native lookups."""
    from build_beowulf_prototype import u16
    from r5900_scalar_check import CPU
    from ogs_korean_codec import decode
    prefix,count,co=u32(old,0x20),u32(old,0x28),u32(old,0x2c)
    inc={int(k):v for k,v in notes['insert_counts'].items()}
    def moved(i):return i+sum(v for p,v in inc.items() if p<=i)
    extra=sum(inc.values())*96
    assert u32(new,0x28)==count+sum(inc.values())
    for field in (0x10,0x14,0x18,0x1c,0x20,0x24,0x30,0x40,0x48):assert u32(new,field)==u32(old,field)
    assert new[0x70:co]==old[0x70:co]
    branches=0
    for i in range(count):
        r=list(struct.unpack_from('<24I',old,co+i*96));expected=list(r)
        if r[0] in (0x8b,0x8c):
            for field in ((6,7) if r[0]==0x8b else (7,)):
                if r[field]<0x80000000:expected[field]=moved(i+r[field])-moved(i);branches+=1
        actual=struct.unpack_from('<24I',new,co+moved(i)*96)
        assert tuple(expected)==actual,(i,r[0])
    oldend=co+count*96;newend=oldend+extra;aux=bytearray(old[oldend:])
    desc=u32(old,0x34);ndesc=u32(new,0x34)
    for i in range(u32(old,0x30)):
        off=desc+i*16;kind=u32(old,off);target=u32(old,off+8)
        expect=moved(target) if kind else target
        assert new[ndesc+i*16:ndesc+i*16+8]==old[off:off+8]
        assert new[ndesc+i*16+12:ndesc+i*16+16]==old[off+12:off+16]
        assert u32(new,ndesc+i*16+8)==expect
        struct.pack_into('<I',aux,off+8-oldend,expect)
    assert new[newend:newend+len(aux)]==aux,'Existing script auxiliary/text bytes changed'
    hc,nc,kc=u32(old,0x38),u32(old,0x40),u32(old,0x50)
    assert u32(new,0x38)==hc+len(notes['messages'])
    assert u32(new,0x50)==kc+len(notes['messages'])
    assert u32(new,0x58)==u32(old,0x58)+len(notes['messages'])
    assert u32(new,0x54)==u32(new,0x44)+nc*4
    for i in range(hc):
        index=u32(old,u32(old,0x3c)+i*4)
        assert u32(new,u32(new,0x3c)+i*4)==(prefix+moved(index-prefix) if index>=prefix else index)
    # All original shared-pool strings and both language pointer tables survive.
    for i in range(nc+kc-1):
        ptr=u32(old,u32(old,0x44)+i*4);assert u32(new,u32(new,0x44)+i*4)==ptr
        a=u32(old,0x4c)+ptr;b=u32(new,0x4c)+ptr
        end=old.find(b'\0',a);assert end>=a
        assert new[b:b+end-a+1]==old[a:end+1]
    c=CPU(ram);ctx,base=0x1600000,0x1800000;c.mem[base:base+len(new)]=new;c.run(0x2b5c90,[ctx,base])
    for j,msg in enumerate(notes['messages']):
        assert msg['label']==hc+j
        c.run(0x2baf90,[ctx,0,nc+kc-1+j]);raw=bytes.fromhex(msg['encoded'])
        got=bytes(c.mem[ctx+0x85a0:ctx+0x85a0+len(raw)])
        assert got==raw and decode(got)==msg['text']
        c.run(0x2ba420,[ctx,msg['label'],0,0,0],stop=0x2ba478)
        ix=c.r[5]&0xffffffff;off=u32(new,0x24)+ix*96
        assert u32(new,off)==0x30 and u32(new,off+4)==hc+j
        assert u32(new,off+8)==nc+kc-1+j and u32(new,off+16)==msg['speaker']
    # Added operations are dialogue and a Beowulf-only retirement, never a stage advance.
    added=[]
    for point,n in sorted(inc.items()):
        start=point+sum(v for p,v in inc.items() if p<point)
        for i in range(start,start+n):
            r=struct.unpack_from('<24I',new,co+i*96);added.append(r[0])
            assert r[0] in (0x30,0x81) or r in allowed_commands
            if r[0]==0x81:assert r[2:5]==(0x100a5,0x603,0xce)
    assert u32(new,4)==u32(new,0x6c)==len(new)
    return dict(passed=True,old_commands_preserved=count,relative_branch_fields_verified=branches,
        original_shared_strings_preserved=nc+kc,new_native_text_and_backlog_checks=len(notes['messages']),
        added_dialogue_commands=added.count(0x30),added_Beowulf_retirement=added.count(0x81))


def validate_story():
    from build_beowulf_prototype import OUT,MAP
    m=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'))['story_fix'];assert m['applied']
    edits=sorted((e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits'])
    inverse=hashlib.sha256();target=hashlib.sha256();pos=0;checks=[]
    rr=(ART/'current_user_ram.bin').read_bytes()
    with OUT.open('rb') as f:
        for off,b,a in edits:
            while pos<off:
                raw=f.read(min(4<<20,off-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
            assert f.read(len(a))==a;inverse.update(b);target.update(a);pos+=len(a)
        while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
        assert inverse.hexdigest()==m['source_sha256'] and target.hexdigest()==m['target_sha256']
        root=Archive(f,MAP+0x557e800)
        for ch in m['chapters']:
            old=read(f,MAP+ch['source_offset'],ch['source_size']);new=read(f,MAP+ch['target_offset'],ch['target_size'])
            assert hashlib.sha256(old).hexdigest()==ch['source_sha256']
            assert hashlib.sha256(new).hexdigest()==ch['target_sha256']
            assert root.entries[ch['script']]==(MAP+ch['target_offset'],ch['target_size'])
            checks.append(validate_story_blob(old,new,ch,rr))
    with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==m['production_sha256']
    result=dict(passed=True,target_sha256=m['target_sha256'],scripts=len(checks),scenes=m['scenes'],messages=m['messages'],
        original_commands_preserved=sum(x['old_commands_preserved'] for x in checks),
        original_strings_preserved=sum(x['original_shared_strings_preserved'] for x in checks),
        native_string_and_backlog_checks=sum(x['new_native_text_and_backlog_checks'] for x in checks),
        production_unchanged=True,previous_battle_and_balance_fixes_preserved=True,live_playthrough_verified=False)
    (ART/'story_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


def validate_balance():
    from build_beowulf_prototype import OUT,MAP,u16
    j=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'));m=j['balance_fix'];assert m['applied']
    edits=sorted((e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits'])
    inverse=hashlib.sha256();target=hashlib.sha256();pos=0
    with OUT.open('rb') as f:
        for off,b,a in edits:
            while pos<off:
                raw=f.read(min(4<<20,off-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
            assert f.read(len(a))==a;inverse.update(b);target.update(a);pos+=len(a)
        while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
        assert inverse.hexdigest()==m['source_sha256'] and target.hexdigest()==m['target_sha256']
        for base,(off,before,after) in zip((0x5da000,0x83f000),edits):
            assert off==base+0x11e000
            old=bytes(0x11e000)+before;now=read(f,base,0x1a5800);h=0x11e800
            unit=h+u32(old,h+0x1c);wt=h+u32(old,h+0x20);weap=h+u32(old,h+0x24);plot=h+u32(old,h+0x2c)
            wend=weap+u32(old,weap+4);end=h+u32(old,0x11e00c)
            assert u32(now,weap+8)==1633
            for k in range(5):
                oldkey=0x8a0+k;newkey=0xf80+k;idx=u16(old,wt+12+oldkey*2)
                orig=old[weap+12+idx*36:weap+12+(idx+1)*36]
                new=bytearray(now[wend+k*36:wend+(k+1)*36])
                assert u16(new,8)==u16(orig,8)+500;new[8:10]=orig[8:10];assert new==orig
            newplot=h+u32(now,h+0x2c)
            assert now[newplot+12+381*148+0x65:newplot+12+381*148+0x6b]==bytes(x+10 for x in old[plot+12+114*148+0x65:plot+12+114*148+0x6b])
            assert u16(now,newplot+12+381*148+0x48)==223
            # Undo only the declared differences and compare every old master byte.
            normalized=bytearray(now[:end+180]);del normalized[wend:wend+180]
            for field in range(0x18,0x8c,4):normalized[h+field:h+field+4]=old[h+field:h+field+4]
            for at,n in ((weap+4,8),(0x11e00c,4),(unit+12+427*100+0x24,10),(plot+12+381*148+0x65,6),(wt+12+0xf80*2,10)):
                normalized[at:at+n]=old[at:at+n]
            assert normalized[0x11e000:]==old[0x11e000:end]
        spawn=Archive(f,MAP+0x5070000)
        plan=json.loads((ART/'enemy_spawn_plan.json').read_text(encoding='utf-8'))
        for p in plan:
            at,n=spawn.entries[p['table']];d=read(f,at,n);alf=d[44+p['original_alfimi_row']*336:44+(p['original_alfimi_row']+1)*336]
            rows=[d[44+i*336:44+(i+1)*336] for i in range(u32(d,40)) if u32(d,44+i*336)==0x604 and u32(d,44+i*336+4)==p['group']]
            assert len(rows)==1 and rows[0][0x34:0x44]==alf[0x34:0x44]
    with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==m['production_sha256']
    result=dict(passed=True,target_sha256=m['target_sha256'],all_six_base_stats_Kyosuke_plus10=True,
        five_separate_weapons_Riese_plus500=True,all_other_master_data_preserved=True,
        Alfimi_matching_spawn_level_variants=len(plan),previous_voice_and_display_fixes_preserved=True,
        production_unchanged=True,live_playback_verified=False)
    (ART/'balance_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


def validate_voice_chunk():
    from build_beowulf_prototype import OUT
    m=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'))['voice_chunk_fix'];assert m['applied']
    edits=sorted((e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits'])
    inverse=hashlib.sha256();target=hashlib.sha256();pos=0
    with OUT.open('rb') as f:
        for off,b,a in edits:
            while pos<off:
                raw=f.read(min(4<<20,off-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
            assert f.read(len(a))==a;inverse.update(b);target.update(a);pos+=len(a)
        while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
        assert inverse.hexdigest()==m['source_sha256'] and target.hexdigest()==m['target_sha256']
        a=Archive(f,0x8574e800);orig=a.get(f,0x446);clone=a.get(f,0x603)
        assert len(orig)==len(clone);h=struct.unpack_from('<16H',orig)
        assert clone[:h[12]]==orig[:h[12]] and clone[h[13]:]==orig[h[13]:]
        self_rows=other_rows=0
        for off in range(h[12],h[13],2):
            tag=int.from_bytes(orig[off:off+2],'little');new=int.from_bytes(clone[off:off+2],'little')
            if tag&0x7ff==0x446:
                assert new==(tag&0xf800)|0x603;self_rows+=1
            else:assert new==tag;other_rows+=1
        assert (self_rows,other_rows)==(520,20)
        # The previous display metadata repair must remain intact.
        banks=read(f,0x859f9000,43200);at,n=Archive(f,0x85a04000).entries[0];meta=read(f,at,n)
        aa=struct.unpack_from('<70H',banks,42*144+4);bb=struct.unpack_from('<70H',banks,227*144+4)
        for old,new in zip(aa,bb):
            if old!=65535:assert meta[old*16:old*16+16]==meta[new*16:new*16+16]
        end=max(at+n for at,n in a.entries)
        assert u32(read(f,0x25120000+8+5*8+4,4))==end-a.base
    with SOURCE.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==m['production_sha256']
        assert Archive(f,0x8574e800).get(f,0x446)==orig
    result=dict(passed=True,target_sha256=m['target_sha256'],self_speaker_rows=self_rows,
        original_other_speaker_rows=other_rows,selectors_text_and_voice_IDs_identical=True,
        original_Kyosuke_chunk_unchanged=True,previous_attack_display_fix_preserved=True,
        all_other_bytes_preserved=True,production_unchanged=True,live_playback_verified=False)
    (ART/'voice_chunk_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


def validate_attack_display():
    from build_beowulf_prototype import OUT
    from r5900_scalar_check import CPU
    journal=json.loads((ART/'prototype_manifest.json').read_text(encoding='utf-8'))
    m=journal['attack_display_fix'];assert m['applied']
    edits=sorted((e['offset'],bytes.fromhex(e['before']),bytes.fromhex(e['after'])) for e in m['edits'])
    inverse=hashlib.sha256();target=hashlib.sha256();pos=0
    with OUT.open('rb') as f:
        for off,b,a in edits:
            while pos<off:
                raw=f.read(min(4<<20,off-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
            assert f.read(len(a))==a;inverse.update(b);target.update(a);pos+=len(a)
        while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
        assert inverse.hexdigest()==m['source_sha256'] and target.hexdigest()==m['target_sha256']
        banks=read(f,0x859f9000,43200)
        at,n=Archive(f,0x85a04000).entries[0];meta=read(f,at,n)
        native=struct.unpack_from('<70H',banks,42*144+4);clone=struct.unpack_from('<70H',banks,227*144+4)
        pairs=set(zip(native,clone))-{(65535,65535)};assert len(pairs)==50
        for a,b in pairs:assert meta[a*16:(a+1)*16]==meta[b*16:(b+1)*16]
        c=CPU((ART/'current_user_ram.bin').read_bytes());obj=0x1800000;c.run(0x290e10,[obj])
        c.mem[0x93b900:0x93b900+len(banks)]=banks;c.mem[0x946200:0x946200+len(meta)]=meta
        checks=0
        for motion,asset in enumerate(native):
            if asset==65535:continue
            assert c.run(0x290b20,[obj,42,motion,0])==c.run(0x290b20,[obj,227,motion,0])
            for sub in range(5):
                assert c.run(0x290990,[obj,42,motion,sub])==c.run(0x290990,[obj,227,motion,sub])
                checks+=1
    with SOURCE.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==m['production_sha256']
    result=dict(passed=True,target_sha256=m['target_sha256'],cloned_metadata_records=50,
        native_auxiliary_image_lookup_cases=checks,all_other_ISO_bytes_preserved=True,production_unchanged=True,
        live_battle_verified=False)
    (ART/'attack_display_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


def validate_spelling_profiles():
    """Compare every release profile against its old payload; allow name bytes only."""
    import io,zipfile,bisect
    from ogs_korean_codec import encode
    root=Path(__file__).resolve().parent
    def parse(data):
        f=io.BytesIO(data);magic=f.read(8);assert magic in (b'OGSBEO01',b'OGSBEO02')
        size,count,nb=struct.unpack('<QII',f.read(16));assert (size,count)==(4518150144,64)
        pool=[]
        for _ in range(nb):
            n=struct.unpack('<I',f.read(4))[0];b=f.read(n);assert len(b)==n;pool.append(b)
        profiles=[]
        for mask in range(64):
            assert struct.unpack('<I',f.read(4))[0]==mask
            anchor=f.read(32);digest=f.read(32);rows=[]
            for _ in range(struct.unpack('<I',f.read(4))[0]):
                at,n,a,b=struct.unpack('<QIII',f.read(20));assert len(pool[a])==len(pool[b])==n
                rows.append((at,pool[a],pool[b]))
            profiles.append((anchor,digest,rows))
        return profiles
    with zipfile.ZipFile(root/'dist/OGS_AxelSwap_QuickPatch_v20261101.zip') as z:
        old=parse(z.read('OGS_AxelSwap_QuickPatch_v20261101/OGS_beowulf_options.bin'))
    new=parse((root/'iso_quickpatch/OGS_beowulf_options.bin').read_bytes())
    before=encode('\ubca0\uc5b4\uc6b8\ud504');after=encode('베오울프');counts=[]
    with (root/'build/SRWOGS_K.iso').open('rb') as f:
        for mask,((anchor,oh,aa),(anchor2,nh,bb)) in enumerate(zip(old,new)):
            assert anchor==anchor2 and oh!=nh
            starts={id(rows):[x[0] for x in rows] for rows in (aa,bb)}
            regions=[]
            for at,a,b in sorted(aa+bb):
                lo=max(0,at-8);hi=min(4518150144,at+len(a)+8)
                if regions and lo<=regions[-1][1]:regions[-1][1]=max(regions[-1][1],hi)
                else:regions.append([lo,hi])
            changed=0
            for lo,hi in regions:
                f.seek(lo);base=bytearray(f.read(hi-lo))
                def apply(buf,rows,index):
                    keys=starts[id(rows)];left=bisect.bisect_left(keys,lo);right=bisect.bisect_left(keys,hi)
                    if left and rows[left-1][0]+len(rows[left-1][1])>lo:left-=1
                    for at,a,b in rows[left:right]:
                        left=max(lo,at);right=min(hi,at+len(a))
                        if left<right:buf[left-lo:right-lo]=(a,b)[index][left-at:right-at]
                apply(base,aa,0);apply(base,bb,0)
                x=bytearray(base);y=bytearray(base);apply(x,aa,1);apply(y,bb,1)
                assert bytes(x).replace(before,after)==y,('Non-name change',mask,hex(lo))
                changed+=bytes(x).count(before)
            assert changed>0;counts.append(changed)
            if mask%16==15:print('Name-only comparison:',mask+1,'/64',flush=True)
    result=dict(passed=True,profiles_checked=64,only_equal_length_name_replacements=True,replacements_per_profile=counts)
    (root/'runtime/beowulf_spelling_profiles_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: 64 profiles differ from v20261101 only in Korean name spelling.',flush=True)


def validate_ingram_profiles():
    """Read the emitted pack independently; verify common Ingram data in all 64 profiles."""
    import io
    from build_beowulf_prototype import u16
    from build_hidden_rewards import MAP
    root=Path(__file__).resolve().parent;data=(root/'iso_quickpatch/OGS_beowulf_options.bin').read_bytes();f=io.BytesIO(data)
    assert f.read(8)==b'OGSBEO02';size,count,nb=struct.unpack('<QII',f.read(16));assert count==64
    pool=[]
    for _ in range(nb):n=struct.unpack('<I',f.read(4))[0];pool.append(f.read(n));assert len(pool[-1])==n
    current=__import__('build_hidden_rewards').Scripts();cp,cn=current.logos[79];chapter=current.data[cp:cp+cn]
    verified=[]
    with (root/'build/SRWOGS_K.iso').open('rb') as iso:
        for mask in range(64):
            assert struct.unpack('<I',f.read(4))[0]==mask;f.read(64);rows=[]
            for _ in range(struct.unpack('<I',f.read(4))[0]):
                at,n,a,b=struct.unpack('<QIII',f.read(20));assert len(pool[a])==len(pool[b])==n;rows.append((at,pool[b]))
            def get(at,n):
                iso.seek(at);out=bytearray(iso.read(n))
                for p,b in rows:
                    lo,hi=max(p,at),min(p+len(b),at+n)
                    if lo<hi:out[lo-at:hi-at]=b[lo-p:hi-p]
                return bytes(out)
            for base in (0x5da000,0x83f000):
                b=get(base,0x1a5800);h=0x11e800;ut,u,wt,w,pt,p=[h+u32(b,h+k) for k in (0x18,0x1c,0x20,0x24,0x28,0x2c)]
                ui,pi=u16(b,ut+12+0x605*2),u16(b,pt+12+0x604*2);assert pi==382
                unit=b[u+12+ui*100:u+12+(ui+1)*100];pilot=b[p+12+pi*148:p+12+(pi+1)*148]
                assert u32(unit,0)==8300 and u16(unit,0x1a)==2100 and unit[0x53]==120
                assert list(pilot[0x65:0x67])==[146,151]
                assert (pilot[0x71],pilot[0x77],pilot[0x7d])==(6,15,16)
                vi=u16(b,ut+12+0x606*2);valcion=b[u+12+vi*100:u+12+(vi+1)*100]
                assert (u32(valcion,0),u16(valcion,0x18),u16(valcion,0x1a),valcion[0x53],u16(valcion,0x22))==(9000,300,2100,120,65535)
                assert struct.unpack_from('<4H',valcion,0x24)==tuple(range(0xfa0,0xfa4))
                for key,power in zip(range(0xfa0,0xfa4),(3900,5000,2700,3100)):
                    wi=u16(b,wt+12+key*2);assert u16(b,w+12+wi*36+8)==power
                assert struct.unpack_from('<3H',unit,0x24)==(0xf90,0xf91,0xf92)
                for key,power in zip((0xf90,0xf91,0xf92),(3900,4100,4900)):
                    wi=u16(b,wt+12+key*2);rec=b[w+12+wi*36:w+12+(wi+1)*36]
                    assert u16(rec,8)==power and (rec[3]&63)==key-0xf90
                    if key==0xf91:assert rec[0x19]==15
            import build_ingram_rivale as newest
            for base in (0x5da000,0x83f000):
                b=get(base,0x1a5800);h=0x11e800;ut=h+u32(b,h+0x18);unit_table=h+u32(b,h+0x1c)
                for key,source,name in newest.LEGACY_UNITS:
                    i=u16(b,ut+12+key*2);assert i!=65535
                    row=b[unit_table+12+i*100:unit_table+12+(i+1)*100];original=b[unit_table+12+source*100:unit_table+12+(source+1)*100]
                    if key==0x607:original=bytearray(original);struct.pack_into('<H',original,0x22,65535)
                    assert row==original
            cost=get(0x94880+0x534e30-0x100000,320)
            assert list(struct.unpack('<80I',cost))==[step*i for step in (1600,1600,1920,3200,3200) for i in range(16)]
            enemy=json.loads((root/'runtime/enemy_strength_manifest.json').read_text(encoding='utf-8'))
            pc=enemy['layout']['spawn_helper']+28;at=0x94880+pc-0x100000
            original=next(e for e in enemy['edits'] if e['offset']<=at<e['offset']+len(bytes.fromhex(e['before'])))
            expected=bytes.fromhex(original['before'])[at-original['offset']:at-original['offset']+4]
            # Pack rows are relative to the old per-option anchor, not the
            # current all-ON ISO used for unrelated read fallbacks.
            word=bytearray(struct.pack('<I',0x24420001) if mask&8 else expected);covered=False
            for q,raw in rows:
                lo,hi=max(q,at),min(q+len(raw),at+4)
                if lo<hi:word[lo-at:hi-at]=raw[lo-q:hi-q];covered=True
            assert bytes(word)==(struct.pack('<I',0x24420002) if mask&8 else expected)
            if mask&8:assert covered
            wp=MAP+0x557f800
            for script,keys in ((77,(0x60a,)),(82,(0x60a,0x60b)),(86,(0x60b,)),(89,(0x608,)),(90,(0x609,)),(91,(0x609,)),(103,(0x607,))):
                pointer=get(wp+8+script*8,8);offset,length=struct.unpack('<II',pointer);raw=get(wp+offset,length)
                co=u32(raw,0x2c);rs=[struct.unpack_from('<24I',raw,co+i*96) for i in range(u32(raw,0x28))]
                for key in keys:assert sum(r[:3]==(0x5a,0xdeaddead,key) for r in rs)==1
                if script in (77,82):
                    for key in (0xde5,0xde6):assert sum(r[:4]==(0x5f,0xdeaddead,key,0) for r in rs)==2
                if script==89:
                    condition=rs[1184];assert condition[0]==0x8c
                    if mask&1:assert condition[2:5]==(1,0x8000,1)
                    else:assert condition[2:5]!=(1,0x8000,1),'Hidden reward leaked into OFF profile'
            wp=MAP+0x557f800;dp=get(wp+8+79*8,8);off,n=struct.unpack('<II',dp);got=get(wp+off,n)
            assert got==chapter,'11화 공통 시나리오가 옵션에 따라 달라짐'
            co=u32(got,0x2c);nr=u32(got,0x28);rs=[struct.unpack_from('<24I',got,co+i*96) for i in range(nr)]
            assert sum(r[:4]==(0xc5,0xdeaddead,0x25,0xffffffff) for r in rs)==1
            assert [(r[0],r[2]) for r in rs[-8:-3]]==[(0x5f,0xdac),(0x5f,0xdc2),(0x5f,0xdba),(0x5b,21),(0x5b,35)]
            assert rs[-3][:4]==(0x9c,0xdeaddead,7,0);verified.append(mask)
            dp=get(wp+8+96*8,8);off,n=struct.unpack('<II',dp);got=get(wp+off,n);orig,z=current.logos[96]
            assert got==current.data[orig:orig+z]
            co=u32(got,0x2c);nr=u32(got,0x28);last=[struct.unpack_from('<24I',got,co+i*96) for i in range(nr-4,nr)]
            assert last[0][:3]==(0x5a,0xdeaddead,0x606) and last[1][:4]==(0x9c,0xdeaddead,24,0)
    result=dict(passed=True,profiles_checked=len(verified),both_masters_verified=True,
        ingram_recruitment_stats_spirits_weapons_preserved=True,chapter11_clear_rewards_preserved=True,
        all_profile_chapter11_bytes_identical=True,valcion_refurbishment_and_chapter30_grant_verified=True,legacy_five_units_and_support_grants_verified=True,price_tables_and_rivale_tiers_verified=True,enemy_plus2_conditional_verified=True,hidden_off_branch_preserved=True,live_playthrough=False)
    (root/'runtime/ingram_profiles_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: Ingram/Rivale and episode11 rewards in all 64 patch profiles.',flush=True)


def validate_patcher_e2e():
    import shutil,subprocess,time
    root=Path(__file__).resolve().parent
    profiles=json.loads((root/'runtime/beowulf_options_profiles.json').read_text(encoding='utf-8'))
    exe=root/'iso_quickpatch/OGS_AxelSwap_QuickPatch.exe'
    scratch=root/'runtime/BEOWULF_PATCHER_VERIFY.iso'
    baseline=root/'baseline/srwogs-v1.4.3s1.iso'
    assert baseline.exists() and not scratch.exists(), 'Scratch file already exists or baseline missing'
    chain=subprocess.run([str(exe),'--self-test-beowulf'],cwd=exe.parent,capture_output=True,text=True)
    (root/'runtime/beowulf_patcher_transitions.log').write_text(chain.stdout+chain.stderr,encoding='utf-8')
    assert chain.returncode==0,(chain.stdout,chain.stderr)
    print(chain.stdout.strip(),flush=True)
    shutil.copyfile(baseline,scratch)
    cases=[]
    for name,flags,mask in [('base_to_off',[],0),('off_to_all_on',['--hidden','--bundle','--rewards','--enemy','--spirits','--beowulf'],63),('all_on_to_off',[],0),('restore',['--restore'],63)]:
        start=time.time()
        r=subprocess.run([str(exe),str(scratch),'--cli']+flags,cwd=exe.parent,capture_output=True,text=True)
        (root/'runtime'/('beowulf_patcher_'+name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
        assert r.returncode==0,(name,r.stdout[-2000:],r.stderr)
        with scratch.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        assert digest.lower()==profiles['hashes'][mask].lower(),(name,digest,profiles['hashes'][mask])
        cases.append(dict(name=name,mask=mask,sha256=digest,seconds=round(time.time()-start,2)))
        print('PASS actual ISO:',name,digest,flush=True)
    # Reconstruct the public .1 profile by reversing only the local feature layers.
    spelling=json.loads((root/'runtime/beowulf_spelling_manifest.json').read_text(encoding='utf-8'))
    prior=next(x for x in spelling['files'] if Path(x['path']).name=='SRWOGS_K.iso')
    shutil.copyfile(root/'build/SRWOGS_K.iso',scratch)
    ingram=json.loads((root/'runtime/ingram_rivale_manifest.json').read_text(encoding='utf-8'))
    hangar=json.loads((root/'runtime/soulgain_hangar_dialogue.json').read_text(encoding='utf-8'))
    with scratch.open('r+b') as f:
        layers=[next(x['edits'] for x in ingram[layer]['files'] if Path(x['path']).name=='SRWOGS_K.iso') for layer in ('enemy_upgrade_plus2','weapon_cost_rebalance','legacy_recruitment','valcion_custom','mobility_fix','clear_bonus','balance_fix','loading_fix')]
        layers+=[next(x['edits'] for x in hangar['plans'] if Path(x['path']).name=='SRWOGS_K.iso'),
            next(x['edits'] for x in ingram['files'] if Path(x['path']).name=='SRWOGS_K.iso')]
        for es in layers:
            for e in es:
                a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                f.seek(e['offset']);assert f.read(len(b))==b;f.seek(e['offset']);f.write(a)
    with scratch.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==prior['after_sha256']
    for name,flags,expected in [('v20261101.1_upgrade',['--hidden','--bundle','--rewards','--enemy','--spirits','--beowulf'],profiles['hashes'][63]),
                              ('restore_previous_release',['--restore'],prior['after_sha256'])]:
        start=time.time();r=subprocess.run([str(exe),str(scratch),'--cli']+flags,cwd=exe.parent,capture_output=True,text=True)
        assert r.returncode==0,(name,r.stdout,r.stderr)
        with scratch.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        assert digest.lower()==expected.lower();cases.append(dict(name=name,sha256=digest,seconds=round(time.time()-start,2)))
        print('PASS actual ISO:',name,digest,flush=True)
    with scratch.open('r+b') as f:
        for e in prior['edits']:
            a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
            f.seek(e['offset']);assert f.read(len(b))==b;f.seek(e['offset']);f.write(a)
    with scratch.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==prior['before_sha256']
    start=time.time()
    r=subprocess.run([str(exe),str(scratch),'--cli','--hidden','--bundle','--rewards','--enemy','--spirits','--beowulf'],cwd=exe.parent,capture_output=True,text=True)
    (root/'runtime/beowulf_patcher_legacy_upgrade.log').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,(r.stdout,r.stderr)
    with scratch.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    assert digest.upper()==profiles['hashes'][63]
    cases.append(dict(name='v20261101_upgrade',mask=63,sha256=digest,seconds=round(time.time()-start,2)))
    print('PASS actual ISO: v20261101 update',digest,flush=True)
    shutil.copyfile(root/'build/SRWOGS_K.iso',scratch)
    with scratch.open('r+b') as f:
        for layer in ('enemy_upgrade_plus2','weapon_cost_rebalance','legacy_recruitment'):
            es=next(x['edits'] for x in ingram[layer]['files'] if Path(x['path']).name=='SRWOGS_K.iso')
            for e in es:
                a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);f.seek(e['offset']);assert f.read(len(b))==b;f.seek(e['offset']);f.write(a)
    previous='e6ec0400446b6d08a72e28b4571808860449c135c17fc77539cfe84a7cda9387'
    with scratch.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==previous
    for name,flags,expected in [('v20261102_upgrade',['--hidden','--bundle','--rewards','--enemy','--spirits','--beowulf'],profiles['hashes'][63]),('v20261102_restore',['--restore'],previous)]:
        r=subprocess.run([str(exe),str(scratch),'--cli']+flags,cwd=exe.parent,capture_output=True,text=True);assert r.returncode==0,(name,r.stdout,r.stderr)
        with scratch.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        assert digest.upper()==expected.upper();cases.append(dict(name=name,sha256=digest));print('PASS actual ISO:',name,digest,flush=True)
    result=dict(passed=True,actual_iso_cases=cases,legacy_option_byte_transitions=5120,
        beowulf_profile_hash_chains=16384,profile_count=64,baseline_and_legacy_anchors_verified=True,
        episode6_test_excluded=profiles['episode6_test_excluded'],gameplay_ISO_modified=False)
    (root/'runtime/beowulf_patcher_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    # Only remove the explicitly named scratch artifacts created by this verifier.
    for p in [scratch,Path(str(scratch)+'.ogsbak')]:
        assert p.resolve().parent==(root/'runtime').resolve()
        if p.exists():p.unlink()



def validate_public_startup():
    """Audit the shipped ZIP, never the later in-development gameplay ISO."""
    import io,zipfile
    from r5900_scalar_check import CPU
    root=Path(__file__).resolve().parent;zip_path=root/'dist/SRWOGS_AxelRoleSwap_kr_v20261102.1.zip'
    with zip_path.open('rb') as f:zip_hash=hashlib.file_digest(f,'sha256').hexdigest()
    assert zip_hash=='07835b71f605d082b921e31618ebbc2bc781e092975d90ceb73b8a5cb83517ee'
    z=zipfile.ZipFile(zip_path);verified=[]
    for line in z.read('SHA256SUMS.txt').decode('utf-8-sig').splitlines():
        if not line.strip():continue
        digest,name=line.split(None,1);name=name.strip();assert hashlib.sha256(z.read(name)).hexdigest()==digest.lower(),name;verified.append(name)
    def U(f):return struct.unpack('<I',f.read(4))[0]
    def rows(f):
        out=[];end=0
        for _ in range(U(f)):
            at,n=struct.unpack('<QI',f.read(12));a,b=f.read(n),f.read(n)
            assert at>=end and n>0 and at+n<=4518150144 and len(a)==len(b)==n
            out.append((at,a,b));end=at+n
        return out
    def option(name):
        f=io.BytesIO(z.read('patcher/'+name));assert f.read(8)==b'OGSHID01';f.read(72);r=rows(f);assert f.tell()==len(f.getbuffer());return r
    f=io.BytesIO(z.read('patcher/OGS_ISO_ranges.bin'));assert f.read(9)==b'OGSAXLRNG';assert U(f)==1
    f.read(struct.unpack('<H',f.read(2))[0]);size=struct.unpack('<Q',f.read(8))[0];source=f.read(32);target=f.read(32);base=[]
    for _ in range(U(f)):
        at,n=struct.unpack('<QI',f.read(12));b=f.read(n);assert len(b)==n;base.append((at,b))
    assert f.tell()==len(f.getbuffer()) and size==4518150144
    hidden,bundle,both=[option(n) for n in ('OGS_hidden_rewards.bin','OGS_ouka_zengar.bin','OGS_ouka_zengar_hidden.bin')]
    f=io.BytesIO(z.read('patcher/OGS_optional_features.bin'));assert f.read(8)==b'OGSOPT02';f.read(40);assert U(f)==32;f.read(36*32);assert U(f)==3
    features={}
    for _ in range(3):bit=U(f);features[bit]=rows(f)
    f=io.BytesIO(z.read('patcher/OGS_common_fix.bin'));assert f.read(8)==b'OGSFIX02';f.read(8);assert U(f)==32;common=[];anchors=[]
    for mask in range(32):assert U(f)==mask;f.read(32);anchors.append(f.read(32));common.append(rows(f))
    f=io.BytesIO(z.read('patcher/OGS_beowulf_options.bin'));assert f.read(8)==b'OGSBEO02';assert struct.unpack('<Q',f.read(8))[0]==size;assert U(f)==64
    pool=[f.read(U(f)) for _ in range(U(f))];profiles=[]
    for mask in range(64):
        assert U(f)==mask;anchor=f.read(32);digest=f.read(32);rr=[];end=0
        for _ in range(U(f)):
            at,n,a,b=struct.unpack('<QIII',f.read(20));assert at>=end and at+n<=size and len(pool[a])==len(pool[b])==n
            rr.append((at,pool[a],pool[b]));end=at+n
        assert anchor==anchors[mask&31];profiles.append((digest,rr))
    class View:
        def __init__(self,f,es):
            self.f=f;self.es=[];self.bins={}
            for at,b in es:self.put(at,b)
        def put(self,at,data):
            idx=len(self.es);self.es.append((at,data))
            for block in range(at>>16,((at+len(data)-1)>>16)+1):self.bins.setdefault(block,[]).append(idx)
        def get(self,at,n):
            self.f.seek(at);b=bytearray(self.f.read(n));assert len(b)==n
            indices=set()
            for block in range(at>>16,((at+n-1)>>16)+1):indices.update(self.bins.get(block,()))
            for idx in sorted(indices):
                p,data=self.es[idx];lo,hi=max(at,p),min(at+n,p+len(data))
                if lo<hi:b[lo-at:hi-at]=data[lo-p:hi-p]
            return bytes(b)
        def apply(self,rs):
            for at,a,b in rs:assert self.get(at,len(a))==a,('guard',hex(at));self.put(at,b)
    findings=[];details=[];fixed_checks=0;fixture=(root/'runtime/beowulf/current_user_ram.bin').read_bytes()
    with (root/'baseline/srwogs-v1.4.3s1.iso').open('rb') as bf:
        baseline_elf=read(bf,0x94880,0x482980)
        from build_beowulf_prototype import retirement_hook
        closure,helper=retirement_hook(bf)
        for mask in range(64):
            v=View(bf,base)
            if mask&1:v.apply(hidden)
            if mask&2:v.apply(both if mask&1 else bundle)
            for bit,rr in features.items():
                if mask&bit:v.apply(rr)
            v.apply(common[mask&31]);v.apply(profiles[mask][1]);elf=v.get(0x94880,0x482980)
            # Native compressed initializer must exactly preserve all output state.
            result=[]
            for seed in (0,1,93):
                a=CPU(fixture);b=CPU(fixture)
                errors=[]
                for c,code in ((a,baseline_elf),(b,elf)):
                    c.mem[0x100000:0x582980]=code
                    c.r=[((i+seed+1)<<64)|(i*151+seed) for i in range(32)]
                    c.r[0]=0;c.r[28]=0x5879f0
                    for reg in range(2,11):c.r[reg]=(c.r[reg]&(~((1<<64)-1)))|0x540000
                    c.fpr=[(i*0x1010123+seed)&0xffffffff for i in range(32)]
                    try:
                        broken=(code[0x100104:0x100114]==baseline_elf[0x100104:0x100114] and code[0x1001b4:0x1001c4]!=baseline_elf[0x1001b4:0x1001c4])
                        c.run(0x200104,stop=0x2001b4 if broken else 0x200270,limit=20000)
                        if broken:errors.append('Startup falls through into Alfimi retreat helper at 002001B4')
                    except RuntimeError as error:errors.append(str(error))
                badregs=[i for i in range(32) if a.r[i]!=b.r[i]];badfpr=[i for i in range(32) if a.fpr[i]!=b.fpr[i]]
                # Code bytes differ by construction, compare every actual store's destination.
                addresses={(p,n) for c in (a,b) for p,n,pc in c.writes}
                badmemory=[(hex(p),n) for p,n in addresses if a.mem[p:p+n]!=b.mem[p:p+n]]
                result.append(dict(seed=seed,execution_errors=errors,gpr_differences=badregs,fpr_differences=badfpr,memory_differences=badmemory))
            if any(r['execution_errors'] or r['gpr_differences'] or r['fpr_differences'] or r['memory_differences'] for r in result):findings.append(dict(mask=mask,initializer=result))
            # Replay the fixed, indivisible startup+retreat block independently.
            fixed=bytearray(elf)
            if mask&32:
                for at,code,label in closure:fixed[at-0x94880:at-0x94880+len(code)]=code
            for seed in (0,1,93):
                machines=[]
                for code in (baseline_elf,fixed):
                    c=CPU(fixture);c.mem[0x100000:0x582980]=code
                    c.r=[((i+seed+1)<<64)|(i*151+seed) for i in range(32)];c.r[0]=0;c.r[28]=0x5879f0
                    for reg in range(2,11):c.r[reg]=(c.r[reg]&(~((1<<64)-1)))|0x540000
                    c.fpr=[(i*0x1010123+seed)&0xffffffff for i in range(32)]
                    c.run(0x200104,stop=0x200270,limit=10000);machines.append(c)
                a,b=machines;assert a.r==b.r and a.fpr==b.fpr,(mask,'fixed register mismatch')
                for at,n in {(p,n) for c in machines for p,n,pc in c.writes}:assert a.mem[at:at+n]==b.mem[at:at+n]
                if mask&32:assert b.visits[helper]==0,(mask,'retreat helper executed during startup')
                fixed_checks+=1
            # Check table offset/count/lookup integrity for both master copies.
            master=[]
            for at in (0x5da000,0x83f000):
                blob=v.get(at,0x1a5800);h=0x11e800;fields=list(range(0x18,0x8c,4));pts=[h+u32(blob,h+k) for k in fields];end=h+u32(blob,0x11e00c)
                assert pts==sorted(pts) and pts[0]>=h+0x8c and end<=len(blob)
                for lookup,table,stride in ((0x18,0x1c,100),(0x20,0x24,36),(0x28,0x2c,148)):
                    lp=h+u32(blob,h+lookup);tp=h+u32(blob,h+table);count=u32(blob,tp+8)
                    assert u32(blob,tp+4)==12+count*stride
                    for i in range(u32(blob,lp+8)):
                        idx=struct.unpack_from('<H',blob,lp+12+i*2)[0];assert idx==65535 or idx<count,(mask,hex(lookup),i,idx,count)
                master.append(dict(copy=hex(at),payload_end=hex(end),unit_count=u32(blob,h+u32(blob,h+0x1c)+8)))
            details.append(dict(mask=mask,sha256=profiles[mask][0].hex(),initializer=result,master=master))
            if mask%16==15:print('Public startup/static profiles checked',mask+1,'/64',flush=True)
    report=dict(version='v20261102.1',zip_sha256=zip_hash,zip_member_checksums_verified=len(verified),profiles_checked=64,
        findings=findings,profiles=details,fixed_initializer_equivalence_cases=fixed_checks,actual_emulator_boot_test=False,gameplay_iso_modified=False)
    (root/'runtime/public_startup_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Initializer differences',json.dumps(findings[:2]),'total profiles',len(findings),flush=True)


if __name__=='__main__':
    import sys
    if '--public-startup' in sys.argv:validate_public_startup()
    elif '--ingram-profiles' in sys.argv:validate_ingram_profiles()
    elif '--spelling-profiles' in sys.argv:validate_spelling_profiles()
    elif '--patcher-e2e' in sys.argv:validate_patcher_e2e()
    elif '--story' in sys.argv:validate_story()
    elif '--balance' in sys.argv:validate_balance()
    elif '--voice-chunk' in sys.argv:validate_voice_chunk()
    elif '--attack-display' in sys.argv:validate_attack_display()
    elif '--riese-night-head' in sys.argv:validate_riese_night_head()
    else:main()
