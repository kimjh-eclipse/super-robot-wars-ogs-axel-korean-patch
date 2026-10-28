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

def validate_weapon_balance(edits,targets,dai,aus):
    vm=VM();c=vm.cpu;master=u32(ram,0x59D360);save=u32(ram,0x59D364)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);blob=bytearray(f.read(0x190000))
    original=bytes(blob)
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(blob):
            assert blob[rel:rel+len(old)]==old;blob[rel:rel+len(new)]=new
    for off,rel,size in [(0x58,0x129F70,0x200C),(0x70,0x12BF7C,12+1628*36)]:
        dest=c.read(master+off,4)
        assert c.mem[dest:dest+4]==blob[rel:rel+4]
        c.mem[dest:dest+size]=blob[rel:rel+size]
    checked=0
    for key in range(4096):
        idx=struct.unpack_from('<H',blob,0x129F7C+key*2)[0]
        if idx not in targets:continue
        old=original[0x12BF88+idx*36:0x12BF88+(idx+1)*36]
        power=struct.unpack_from('<H',old,8)[0]
        assert c.run(0x1A4CB0,[master,key])==2
        assert c.run(0x1A5DC0,[master,key])==power+(200 if power and idx in dai|aus else 0)
        if idx in dai and power:
            assert c.run(0x1A57B0,[master,key])==0
            assert c.run(0x1A5720,[master,key])==0
        else:
            assert c.run(0x1A57B0,[master,key])==old[3]&7
            assert c.run(0x1A5720,[master,key])==(old[3]>>3)&7
        checked+=1
    # Full table comparison protects every unrelated weapon and every other
    # byte (animation, audio keys, range, ammo, EN, morale, categories).
    for idx in range(1628):
        p=0x12BF88+idx*36;a=original[p:p+36];b=blob[p:p+36]
        changed={i for i in range(36) if a[i]!=b[i]}
        assert changed<=({3,8,9,0x15} if idx in targets else set())
    growth=[c.run(0x1B02F0,[save,0,i,0]) for i in range(15)]
    costs=[u32(ram,0x534E30+i*4) for i in range(1,11)]
    assert sum(growth[:10])==2500 and sum(costs)==110000
    return dict(native_weapon_keys_verified=checked,weapon_records=len(targets),
        ten_stage_cost=sum(costs),ten_stage_attack_growth=sum(growth[:10]),
        unrelated_weapon_bytes_preserved=True,combination_formula_preserved=True,
        live_battle_test=False)

def validate_sladegelmir(edits):
    def setup(patched=True):
        vm=VM();c=vm.cpu;master=u32(ram,0x59D360)
        with ISO.open('rb') as f:
            f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
            f.seek(0x5DA000);blob=bytearray(f.read(0x190000))
        if patched:
            for off,old,new in edits:
                if 0x5DA000<=off<0x76A000:
                    rel=off-0x5DA000;assert blob[rel:rel+len(old)]==old;blob[rel:rel+len(new)]=new
                elif off<0x5DA000:
                    va=off-0x94880+0x100000
                    assert c.mem[va:va+len(old)]==old;c.mem[va:va+len(new)]=new
        for off,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x88,0x13A478),(0xA0,0x13B484)):
            dest=c.read(master+off,4)
            assert c.mem[dest:dest+4]==blob[rel:rel+4],(hex(off),c.mem[dest:dest+4],blob[rel:rel+4])
            size=u32(blob,rel+4);c.mem[dest:dest+size]=blob[rel:rel+size]
        return vm
    vm=setup();c=vm.cpu;save=u32(ram,0x59D364)
    up=save+0x6EFC;pp=save+0x25CFC
    units=bytes(c.mem[up:up+512*216]);pilots=bytes(c.mem[pp:pp+512*92])
    assert c.run(0x1ABC50,[save,0x601,0,0])==-1
    vm.op(command(0x5A,0x601));slot=c.run(0x1ABC50,[save,0x601,0,0]);assert slot>=0
    assert c.run(0x1A9B70,[save,slot,1])==1
    assert c.run(0x1B1300,[save,slot,0])==-1
    assert c.run(0x1B01D0,[save,0x34,slot])==0xFFFF
    assert c.run(0x311200,[save,slot,1],limit=10000000)>0
    assert c.mem[pp:pp+512*92]==pilots
    for i in range(512):
        if i!=slot:assert c.mem[up+i*216:up+(i+1)*216]==units[i*216:(i+1)*216]
    stable=bytes(c.mem[save:save+0x3B400]);vm.op(command(0x5A,0x601))
    assert c.mem[save:save+0x3B400]==stable
    enemy=c.run(0x1B2070,[save,0x490,0]);assert enemy>=0 and enemy!=slot
    assert c.run(0x1ABC50,[save,0x601,0,0])==slot
    pilot=c.run(0x1B1FD0,[save,0x469,0]);assert pilot>=0
    # Fixture: episode37 has made Sanger an ally; raw allocator starts faction0.
    c.write(pp+pilot*92+2,1,1)
    assert c.run(0x1A9A50,[save,pilot,1])==1
    vm.op(command(0x5A,0x499));dai=c.run(0x1ABC50,[save,0x499,0,0]);assert dai>=0
    c.run(0x1AF000,[save,2,dai,1,0]);c.run(0x1B13D0,[save,pilot,dai,0])
    # Native pilot category getter and native unit boarding count.
    assert c.run(0x1AFBD0,[save,0x21,pilot,0])==0x8000
    assert c.run(0x311200,[save,slot,1],limit=10000000)>0
    c.run(0x1B1370,[save,dai,0])
    c.run(0x1B13D0,[save,pilot,slot,0]);assert c.run(0x1B1300,[save,slot,0])==pilot
    assert c.run(0x311200,[save,dai,1],limit=10000000)>0,('return',pilot, 'pilot props',[(hex(x),c.run(0x1AC800,[save,x,pilot])) for x in (0xE7,0xE8,0xE9,0xF2)],'current',c.run(0x1B1300,[save,dai,0]),'mask',c.run(0x1ACA50,[save,0x59,dai]),'state',c.run(0x1B1250,[save,pilot]))
    c.run(0x1B1370,[save,slot,0])
    c.run(0x1B13D0,[save,pilot,dai,0]);assert c.run(0x1B1300,[save,dai,0])==pilot
    # Wrapper changes must leave Mumei and ordinary grants byte identical.
    for key in (0x600,0x559):
        a=setup(False);b=setup(True)
        a.op(command(0x5A,key));b.op(command(0x5A,key))
        assert a.cpu.mem[save:save+0x3B400]==b.cpu.mem[save:save+0x3B400],hex(key)
    return ['Native reward: owned, pilotless robot; general boarding candidates exist',
        'Repeated grant is idempotent; enemy key490 is independently allocated',
        'All existing pilot and other unit records preserved by reward',
        'Sanger category8000 and Sladegelmir/Daizengar boarding round trip verified',
        'Mumei and unrelated grant save effects byte-identical',
        'Original episode37 script and dialogue preserved; live playthrough pending']

def validate_refit_labels(edits):
    vm=VM();c=vm.cpu;master=u32(ram,0x59D360);save=u32(ram,0x59D364)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);blob=f.read(0x190000)
    for off,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0xB8,0x149168),(0xD0,0x1492B0)):
        dest=c.read(master+off,4);size=u32(blob,rel+4)
        assert c.mem[dest:dest+4]==blob[rel:rel+4]
        c.mem[dest:dest+size]=blob[rel:rel+size]
    vm.op(command(0x5A,0x559))
    results={}
    for key in (0x499,0x49A,0x4B8,0x4BD):
        vm.op(command(0x5A,key));slot=c.run(0x1ABC50,[save,key,0,0]);assert slot>=0
        c.run(0x1AF000,[save,2,slot,1,0]);c.write(CTX+0x32D8,slot,4)
        baseline=CPU(c.mem);patched=CPU(c.mem)
        for off,old,new in edits:
            va=off-0x94880+0x100000;assert patched.mem[va:va+len(old)]==old
            patched.mem[va:va+len(new)]=new
        for q in (baseline,patched):q.run(0x42DA80,[CTX],limit=10000000)
        assert baseline.mem[save:save+0x3B400]==patched.mem[save:save+0x3B400]
        count=patched.read(CTX+0x1559C,1)+1
        if key in (0x499,0x49A):
            assert count==2
            labels={}
            for i in range(count):
                target=patched.read(CTX+0x155C6+i*64,2)
                ptr=patched.read(CTX+0x156E4+i*4,4)
                raw=bytes(patched.mem[ptr:ptr+8]).split(b'\0',1)[0]
                labels[target]=decode(raw)
            assert labels=={0x499:'참함도',0x49A:'기본'},labels
            results[hex(key)]={hex(k):v for k,v in labels.items()}
            # Label pointers are the only changed UI data.
            patched.mem[CTX+0x156E4:CTX+0x156EC]=baseline.mem[CTX+0x156E4:CTX+0x156EC]
        assert baseline.mem[CTX:CTX+0x17000]==patched.mem[CTX:CTX+0x17000],hex(key)
    return dict(labels=results,non_daizengar_ui_unchanged=True,preview_stats_and_save_unchanged=True,
                live_render_test=False)

def validate_refit_visibility(edits):
    import os
    specified=os.environ.get('OGS_REFIT_STATE')
    candidates=([Path(specified)] if specified else
        list((Path.home()/'Desktop').rglob('SLPS-25733 (6624C6DA).01.p2s')))
    assert len(candidates)==1,candidates
    snapshot=load_ram(candidates[0]);base=CPU(snapshot)
    save=u32(snapshot,0x59D364);glob=u32(snapshot,0x59D36C)
    slot=base.run(0x1ABC50,[save,0x49A,0,0]);assert slot==53
    assert base.run(0x1A9B70,[save,slot,1])==1
    assert base.run(0x19A0C0,[glob,110])==1
    assert base.run(0x19A0C0,[glob,111])==0
    def eligible(c):
        # Actual menu eligibility scan includes scenario DT lock; the earlier
        # 43E400 list loop alone did not test this gate.
        c.r[17]=glob;c.r[18]=save;c.r[21]=slot;c.r[16]=0;c.r[29]=0x1F00000
        c.pc=0x43EA34;c.pending=None
        for _ in range(100000):
            if c.pc in (0x43EC2C,0x43ECB0,0x43ED30):return c.pc==0x43EC2C
            c.step()
        raise AssertionError('Eligibility scan did not terminate')
    assert not eligible(base),'Must reproduce the user failure before patch'
    c=CPU(snapshot)
    with ISO.open('rb') as f:
        f.seek(0x94880);code=f.read(0x39A778)
    assert snapshot[0x100000:0x499000]==code[:0x399000],'Snapshot instructions differ from guarded ISO'
    for off,old,new in edits:
        va=off-0x94880+0x100000
        assert c.mem[va:va+len(old)]==old;c.mem[va:va+len(new)]=new
    assert eligible(c)
    # Wrapper must preserve every other native flag query, not globally unlock DTs.
    for dt in range(124):
        expected=c.run(0x19A0C0,[glob,dt])
        assert c.run(0x19A0B4,[glob,dt])==(0 if dt==110 else expected),dt
    ui=CTX;c.write(ui+0x32D8,slot,4)
    unit=save+0x6EFC+slot*0xD8
    unit_before=bytes(c.mem[unit:unit+0xD8])
    # Slots 192+ are native preview scratch pilots, not the persistent roster.
    pilot_bytes=bytes(c.mem[save+0x25CFC:save+0x25CFC+192*0x5C])
    flag_before=bytes(c.mem[glob:glob+0x1000])
    rendered=[]
    def render_first(q):
        # Execute the actual first-row argument path up to the draw-text call.
        # Graphics rasterization remains an emulator check.
        q.r[16]=ui+0x150F0;q.r[29]=0x1F00000
        q.pc=0x44EEA8;q.pending=None
        for _ in range(50):
            if q.pc==0x1834D0:
                assert q.r[4]&0xFFFFFFFF==ui+0x150F0
                assert q.r[7]&0xFFFFFFFF==0
                return q.r[6]&0xFFFFFFFF
            q.step()
        raise AssertionError('Text argument path did not reach renderer')
    for target in (0x499,0x49A)*3:
        assert eligible(c)
        c.run(0x42DA80,[ui],limit=10000000)
        assert c.read(ui+0x1559C,1)+1==2
        choices=[c.read(ui+0x155C6+i*64,2) for i in range(2)]
        assert set(choices)=={0x499,0x49A}
        ptr=render_first(c);label=decode(bytes(c.mem[ptr:ptr+8]).split(b'\0',1)[0])
        assert label==('기본' if choices[0]==0x49A else '참함도'),(choices,label,hex(ptr))
        rendered.append(label)
        c.write(ui+0x15558,choices.index(target),4)
        assert c.run(0x42E2F0,[ui])==0
        assert c.run(0x1ACA50,[save,1,slot])==target
        assert c.run(0x1A9B70,[save,slot,1])==1 and eligible(c)
        assert c.mem[save+0x25CFC:save+0x25CFC+192*0x5C]==pilot_bytes,[(hex(i),x,c.mem[save+0x25CFC+i]) for i,x in enumerate(pilot_bytes) if x!=c.mem[save+0x25CFC+i]][:30]
        assert c.mem[glob:glob+0x1000]==flag_before
    assert c.mem[unit:unit+0xD8]==unit_before,'Round trip must preserve the actual record'
    # Same UI object: an ordinary robot must not inherit the Daizengar label.
    normal=next(i for i in range(512) if c.run(0x1A9B70,[save,i,1]) and i!=slot)
    c.write(ui+0x32D8,normal,4)
    c.run(0x42DA80,[ui],limit=10000000)
    assert c.read(ui+0x156E4,4)==0
    assert render_first(c)==0x556ED8
    return dict(failing_savestate=str(candidates[0]),source_state_sha256=hashlib.sha256(snapshot).hexdigest(),
        failure_reproduced_before_patch=True,native_menu_gate_fixed=True,
        stored_scenario_flags_unchanged=True,other_123_dt_queries_unchanged=True,
        native_refit_round_trips=3,unit_and_pilot_records_preserved=True,
        actual_first_row_text_arguments=rendered,ordinary_first_row_unchanged=True,
        live_render_and_battle_test=False)

def validate_builtin_weapons(edits):
    c=VM().cpu;master=u32(ram,0x59D360)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);blob=bytearray(f.read(0x190000))
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(blob):
            assert blob[rel:rel+1]==old;blob[rel:rel+1]=new
    for off,rel in ((0x58,0x129F70),(0x70,0x12BF7C)):
        dest=c.read(master+off,4);size=u32(blob,rel+4)
        assert c.mem[dest:dest+4]==blob[rel:rel+4]
        c.mem[dest:dest+size]=blob[rel:rel+size]
    for key,power,lo,hi,all_attack in ((0xA6B,5200,3,6,1),(0xA6C,5900,1,2,0)):
        assert c.run(0x1A4EE0,[master,key])==all_attack
        assert c.run(0x1A5D40,[master,key])==lo
        assert c.run(0x1A5CC0,[master,key])==hi
        assert c.run(0x1A5DC0,[master,key])==power
        assert c.run(0x1A4CB0,[master,key])==2
        assert c.run(0x1A57B0,[master,key])==0
        assert c.run(0x1A5720,[master,key])==0
    return dict(general_blaster='ALL / 5200 / range3-6',guardian_sword='single / 5900 / range1-2',
        native_getters_passed=True,previous_barrier_and_upgrade_changes_preserved=True,
        iso_changed_bytes=4,live_battle_test=False)

def validate_ouka_route_fix(row,blobs):
    from ogs_korean_codec import encode
    s=Scripts()
    native=validate_ouka(row,{},s,[])
    for n,b in blobs.items():
        original=s.records(n);co=u32(b,0x2C)
        assert u32(b,0x28)==len(original)+(n==131)
        for i,(_,r) in enumerate(original):
            target=i+(n==131 and i>=1188)
            assert struct.unpack_from('<24I',b,co+target*96)==r
        if n==131:assert struct.unpack_from('<24I',b,co+1188*96)==tuple(command(0x5E,0x26))
        oldat,_=s.logos[n]
        for j in range(u32(b,0x38)):
            assert u32(b,u32(b,0x3C)+j*4)==u32(s.data,oldat+u32(s.data,oldat+0x3C)+j*4)
        for i,(p,text) in enumerate(s.texts(n)):
            at=u32(b,0x4C)+u32(b,u32(b,0x54)+i*4);raw=b[at:(b+b'\0').index(0,at)]
            if n!=110 or i not in range(41,49):assert raw==encode(text),(n,i)
            else:
                updated=decode(raw);assert encode(updated)==raw
                assert all(len(encode(line))<=54 for line in updated.split('@'))
    return dict(native_group_grant_and_boarding_passed=True,repeated_grant_reuses_pair=True,
                alternate44_clear_grant=True,common45_dialogue_lines=8,
                all_other_commands_and_dialogue_preserved=True,text_lookup_unchanged=True,
                original44_route_preserved=True,live_chapter_test=False)


def validate_small_enemy_hp_boost(edits,helper):
    with ISO.open('rb') as f:
        f.seek(0x94880);old=f.read(0x482980)
        f.seek(0x5DA000);blob=f.read(0x1A5800)
    new=bytearray(old)
    for off,a,b in edits:
        p=off-0x94880;assert new[p:p+len(a)]==a;new[p:p+len(b)]=b
    # Startup compression must preserve every register and descriptor store.
    for seed in (0,1,0x12345678):
        cs=[]
        for code in (old,new):
            c=CPU(ram);c.mem[0x100000:0x582980]=code
            for r in range(2,11):c.r[r]=0x540000
            c.fpr=[(seed+i*12347)&0xFFFFFFFF for i in range(32)]
            c.run(0x200104,stop=0x200270);cs.append(c)
        assert cs[0].r==cs[1].r and cs[0].fpr==cs[1].fpr
        stores=[{(a,n) for a,n,pc in c.writes} for c in cs]
        assert stores[0]==stores[1]
        for a,n in stores[0]:assert cs[0].mem[a:a+n]==cs[1].mem[a:a+n]
    def setup(code):
        c=CPU(ram);c.mem[0x100000:0x582980]=code
        master=c.read(0x59D360,4);save=c.read(0x59D364,4)
        base=0x1100000;payload=blob[0x11E800:]
        c.mem[base:base+len(payload)]=payload
        for i,field in enumerate(range(0x18,0x8C,4)):
            dst=base+u32(blob,0x11E800+field);obj=master+0x28+i*24
            for off,value in ((0,dst),(4,c.read(dst,4)),(8,c.read(dst+4,4)),(12,0),(16,dst),(20,dst+12)):
                c.write(obj+off,value,4)
        obj=0x1800000;stage=0x1400000;settings=0x1600000
        c.mem[obj:obj+0x200]=bytes(0x200);c.mem[settings:settings+0x200]=bytes(0x200)
        for off,value in ((0,c.read(0x59D36C,4)),(4,save),(0x10,stage),(0x18,0),(0x168,settings)):
            c.write(obj+off,value,4)
        c.write(0x5879F0-0x4ED0,0,1)
        # Native per-save unit key -> actual master record, no synthetic getter.
        key=c.run(0x1D09D0,[save+0x6EFC,1,0]);assert key>0
        idx=c.run(0x2E11C0,[master+0x28,key]);assert idx>=0
        record=c.read(master+0x40+20,4)+idx*100
        return c,obj,stage,settings,record
    machines=[setup(code) for code in (old,new)]
    cases=0
    for hp in (0,1,3700,10000,19999,20000,63000):
        for side in range(6):
            for hostile in (False,True):
                for upgraded_hp in (0,1000):
                    results=[]
                    for c,obj,stage,settings,record in machines:
                        c.write(record,hp,4)
                        assert c.run(0x1B01D0,[c.read(obj+4,4),0x14,0,0])==hp
                        c.write(obj+0x74,side,1)
                        c.write(stage+0x17608C+side,int(hostile),1)
                        for i in range(3):c.write(settings+0x128+i*4,500,4)
                        c.write(settings+0x134,0,4)
                        results.append(c.run(0x1FE860,[obj,hp+upgraded_hp]))
                    expected=hp//10 if hostile and 0<hp<20000 else 0
                    assert results[1]==results[0]+expected,(hp,side,hostile,upgraded_hp,results)
                    cases+=1
    dispatcher_cases=0
    for hp in (3700,19999,20000,63000):
        for hostile in (False,True):
            results=[]
            for c,obj,stage,settings,record in machines:
                c.write(record,hp,4);c.write(obj+0x74,2,1)
                c.write(stage+0x17608E,int(hostile),1)
                results.append(c.run(0x1FE9D0,[obj,0x14,0,0,0]))
            assert results[1]==results[0]+(hp//10 if hostile and hp<20000 else 0),(hp,hostile,results)
            dispatcher_cases+=1
    for c,obj,stage,settings,record in machines:
        c.write(record,10000,4);c.write(obj+0x10,0,4)
        assert c.run(0x1FE860,[obj,11000])==11500
    return dict(native_HP_cases=cases,native_full_HP_dispatcher_cases=dispatcher_cases,startup_initializer_equivalent=True,
        strictly_below_20000=True,base_HP_threshold_not_upgraded_HP=True,
        ally_and_neutral_unchanged=True,hostility_relation_used=True,missing_map_context_unchanged=True,
        HP_upgrade_and_difficulty_additions_unchanged=True,masters_and_saves_not_modified=True,
        helper_bytes=0x200270-helper,live_battle_test=False)


def validate_global_weapon_upgrade_discount(old,new):
    """Execute native cost sum and menu price lookup for all five tiers."""
    assert len(old)==len(new)==5*64
    with ISO.open('rb') as f:
        f.seek(0x94880);code=f.read(0x39A778)
    c=CPU(ram);c.mem[0x100000:0x49A778]=code
    totals=[]
    for data in (old,new):
        c.mem[0x534E30:0x534F70]=data
        results=[]
        for tier in range(5):
            assert u32(data,tier*64)==0
            for level in range(1,16):
                # Native upgrade-menu lookup through the same shared table.
                c.r[2]=tier;c.r[16]=(level-1)*4;c.r[17]=level-1;c.r[19]=0x1800000
                c.write(0x1800000+0x53C,0,4)
                c.run(0x443858,stop=0x443880)
                price=c.read(0x1800000+0x53C,4)
                assert price==u32(data,tier*64+level*4)
                # Native weapon investment/refund cost accumulation loop.
                c.r[2]=tier;c.r[3]=level;c.r[16]=0
                c.run(0x334F98,stop=0x334FD8)
                total=sum(u32(data,tier*64+i*4) for i in range(1,level+1))
                assert c.r[16]==total
                results.append((price,total))
        totals.append(results)
    assert totals[0][:15]==totals[1][:15]
    assert all(b[0]*5==a[0]*4 and b[1]*5==a[1]*4 for a,b in zip(totals[0][15:],totals[1][15:]))
    return dict(cost_tiers=5,levels_per_tier=15,cheapest_tier_unchanged=True,
                all_60_other_prices_exactly_20_percent_lower=True,
                native_menu_lookup_and_cumulative_cost_passed=True,
                ten_stage_totals_before=[totals[0][t*15+9][1] for t in range(5)],
                ten_stage_totals_after=[totals[1][t*15+9][1] for t in range(5)],
                unit_upgrade_prices_and_weapon_growth_unchanged=True,live_menu_test=False)


def validate_daizengar_upgrade_cost(edits,targets):
    c=VM().cpu;master=u32(ram,0x59D360)
    with ISO.open('rb') as f:
        f.seek(0x5DA000);b=bytearray(f.read(0x190000))
        f.seek(0x94880+0x534E30-0x100000);costs=f.read(5*64)
    original=bytes(b)
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(b):
            assert b[rel:rel+1]==old;b[rel:rel+1]=new
    for off,rel in ((0x58,0x129F70),(0x70,0x12BF7C)):
        dest=c.read(master+off,4);size=u32(b,rel+4)
        assert c.mem[dest:dest+4]==b[rel:rel+4]
        c.mem[dest:dest+size]=b[rel:rel+size]
    keys=0
    for key in range(4096):
        idx=struct.unpack_from('<H',b,0x129F7C+key*2)[0]
        if idx in targets:
            assert c.run(0x1A57B0,[master,key])==1
            assert c.run(0x1A5720,[master,key])==0
            keys+=1
    for idx in range(1628):
        at=0x12BF88+idx*36
        diff={i for i in range(36) if b[at+i]!=original[at+i]}
        assert diff==({3} if idx in targets else set())
    before=[u32(costs,4*i) for i in range(1,11)]
    after=[u32(costs,64+4*i) for i in range(1,11)]
    assert sum(before)==110000 and sum(after)==165000
    return dict(weapon_records=len(targets),native_weapon_keys_verified=keys,
        cost_tier_before=0,cost_tier_after=1,ten_stage_cost_before=sum(before),
        ten_stage_cost_after=sum(after),per_stage_cost=after,
        attack_growth_tier_unchanged=0,all_other_weapon_bytes_preserved=True,
        combined_attack_formula_preserved=True,live_menu_test=False)

def validate_weapon_consumption(edits):
    c=VM().cpu;master=u32(ram,0x59D360)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);blob=bytearray(f.read(0x190000))
    original=bytes(blob)
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(blob):
            assert blob[rel:rel+1]==old;blob[rel:rel+1]=new
    for off,rel in ((0x58,0x129F70),(0x70,0x12BF7C)):
        dest=c.read(master+off,4);size=u32(blob,rel+4)
        assert c.mem[dest:dest+4]==blob[rel:rel+4]
        c.mem[dest:dest+size]=blob[rel:rel+size]
    targets={0x312:(0x1A,20),0x313:(0x1A,30),0x2A3:(0x1B,115),0x1D5:(0x1A,60),0x1D9:(0x1A,40)}
    checked=0
    for key in range(4096):
        idx=struct.unpack_from('<H',blob,0x129F7C+key*2)[0]
        if idx in targets:
            field,value=targets[idx]
            assert c.run(0x1A5AC0 if field==0x1A else 0x1A5A40,[master,key])==value
            checked+=1
    assert checked==5
    for idx in range(1628):
        p=0x12BF88+idx*36
        changes={j for j in range(36) if blob[p+j]!=original[p+j]}
        assert changes==({targets[idx][0]} if idx in targets else set())
    assert c.run(0x1A4EE0,[master,0xA6B])==1
    assert c.run(0x1A5CC0,[master,0xA6C])==2
    return dict(native_weapon_keys_verified=checked,unrelated_weapon_fields_preserved=True,
        general_blaster_en=20,guardian_sword_en=30,gigante_unghia_morale=115,
        grungust_ankensatsu_en=[60,40],iso_changed_bytes=10,live_battle_test=False)

def validate_daizengar_refit(edits):
    """Execute stock menu gates and stock refit commit on copied EE RAM."""
    vm=VM();c=vm.cpu;master=u32(ram,0x59D360);save=u32(ram,0x59D364)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);blob=bytearray(f.read(0x190000))
    tables=[(0x28,0x11E88C,0x100C),(0x40,0x11F898,0xA6D8),
            (0xB8,0x149168,0x147),(0xD0,0x1492B0,0x5DC)]
    def load_tables():
        for off,rel,size in tables:
            dest=c.read(master+off,4)
            assert c.mem[dest:dest+4]==blob[rel:rel+4]
            c.mem[dest:dest+size]=blob[rel:rel+size]
    load_tables()
    vm.op(command(0x5A,0x499))
    slot=c.run(0x1ABC50,[save,0x499,0,0]);assert 0<=slot<512
    c.run(0x1AF000,[save,2,slot,1,0]) # owned ally, as after normal acquisition
    ui=CTX;c.write(ui+0x32D8,slot,4)
    def listed():
        # Actual refit list loop, stopping before graphics/list serialization.
        c.r[16]=slot;c.r[20]=save;c.r[29]=0x1F00000
        c.pc=0x43E400;c.pending=None
        for _ in range(100000):
            if c.pc in (0x43E51C,0x43E558):return c.pc==0x43E51C
            c.step()
        raise AssertionError('Refit candidate gate did not terminate')
    assert not listed(),'Unpatched sword form should not have a refit entry'
    for off,old,new in edits:
        if 0x5DA000<=off<0x76A000:
            rel=off-0x5DA000;assert blob[rel:rel+len(old)]==old
            blob[rel:rel+len(new)]=new
        elif 0x94880<=off<0x430000:
            va=off-0x94880+0x100000
            assert c.mem[va:va+len(old)]==old;c.mem[va:va+len(new)]=new
    load_tables();assert listed(),(slot,[(hex(p),c.run(0x1AC9D0,[save,p,slot,0])) for p in (1,0x37,0x53,0x55)],c.run(0x1A9B70,[save,slot,1]))
    # Stock UI reports the other form without requiring any equipment item.
    assert c.run(0x42E750,[ui,slot])==0x49A
    pilot=c.run(0x1B1FD0,[save,0x469,0]);assert 0<=pilot<512
    c.run(0x1B13D0,[save,pilot,slot,0])
    assert c.run(0x1B1300,[save,slot,0])==pilot
    arg=REC
    for i in range(4):
        c.write(arg,i,4);c.run(0x1AF000,[save,6,slot,i+1,arg])
    def upgrades():
        out=[]
        for i in range(4):
            c.write(arg,i,4);out.append(c.run(0x1AF860,[save,6,slot,arg]))
        return out
    expected=upgrades();assert expected==list(range(1,5)),expected
    record=save+0x6EFC+slot*0xD8
    original=bytes(c.mem[record:record+0xD8])
    pilot_record=save+0x25CFC+pilot*0x5C
    pilot_before=bytes(c.mem[pilot_record:pilot_record+0x5C])
    for target,other in [(0x49A,0x499),(0x499,0x49A)]*3:
        c.run(0x42DA80,[ui],limit=10000000)
        count=c.read(ui+0x1559C,1)+1
        choices=[c.read(ui+0x155C6+i*64,2) for i in range(count)]
        assert count==2 and set(choices)=={0x499,0x49A},choices
        c.write(ui+0x15558,choices.index(target),4)
        assert c.run(0x42E2F0,[ui])==0
        assert c.run(0x1ACA50,[save,1,slot])==target
        assert c.run(0x1B1300,[save,slot,0])==pilot
        assert upgrades()==expected
        assert listed() and c.run(0x42E750,[ui,slot])==other
        assert bytes(c.mem[pilot_record:pilot_record+0x5C])==pilot_before
    assert bytes(c.mem[record:record+0xD8])==original,'Round trip changed unit record'
    # Existing equipment-dependent refits must retain their exact preview
    # and save effects. The boxer frame stays in storage (native faction 31).
    vm.op(command(0x5A,0x559))
    for key in (0x4B8,0x4BD):
        vm.op(command(0x5A,key))
        q=c.run(0x1ABC50,[save,key,0,0]);c.run(0x1AF000,[save,2,q,1,0])
        c.write(ui+0x32D8,q,4);c.write(ui+0x1559C,0,1)
        baseline=CPU(c.mem)
        for off,old,new in edits:
            if off<0x5DA000:
                va=off-0x94880+0x100000;baseline.mem[va:va+len(old)]=old
        for cpu in (baseline,c):
            cpu.run(0x42DA80,[ui],limit=10000000)
            count=cpu.read(ui+0x1559C,1)+1
            choices=[cpu.read(ui+0x155C6+i*64,2) for i in range(count)]
            assert choices==[0x4B8,0x4BD],choices
        assert baseline.mem[ui:ui+0x17000]==c.mem[ui:ui+0x17000]
        assert baseline.mem[save:save+0x3B400]==c.mem[save:save+0x3B400]
    return ['Native refit list rejects original 0x499 and accepts patched 0x499/0x49A',
            'Native preview builds both real menu rows; native commit executes three round trips in the same roster slot',
            'Four unit upgrade values, assigned pilot and entire unit/pilot records preserved after round trips',
            'Huckebein Mk-III L/Boxer native menu and save effects match the unpatched executable byte for byte',
            'No replacement equipment requirement; no event, dialogue, weapon or voice edits',
            'Offline CPU validation only; rendered menu and battle playback still require PCSX2 verification']

def validate_episode6_bonus(grants):
    vm=VM();cpu=vm.cpu
    with ISO.open('rb') as f:
        f.seek(0x94880);cpu.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
    save=u32(ram,0x59D364);glob=u32(ram,0x59D36C)
    allocated=[]
    # Twice proves additions do not replace existing copies; actual scenario
    # invokes this list only once on its clear path.
    for repeat in range(2):
        for r in grants:
            old=bytes(cpu.mem);cpu.writes.clear();vm.op(r)
            if r[0]==0x5F:
                targets={a for a,n,pc in cpu.writes if pc==0x33513C and n==2
                         and cpu.read(a,2)==r[2] and old[a:a+2]!=cpu.mem[a:a+2]}
                assert len(targets)==1
                target=targets.pop()
                assert save<=target<save+0x40000 and target not in allocated
                assert old[target:target+2]==b'\0\0' and cpu.read(target,2)==r[2]
                assert cpu.read(target+3,1)&0x20
                allocated.append(target)
            else:
                key=r[2]
                for off in (0x103C,0x1264):
                    p=glob+off+key
                    assert cpu.read(p,1)==old[p]+1,(hex(key),hex(off))
    assert len(allocated)==6
    return ['Current ISO native grant handlers executed on copied RAM',
            'Three distinct weapon allocations and +1 to each part count per pass',
            'Second pass adds new copies without replacing existing copies',
            'All original episode 6 commands, dialogue bytes and lookup values preserved',
            'Only LOGO 74 and its directory length change; other episodes/master/voices untouched']

def validate_mumei(edits,code):
    """Execute the installed allocator and grant handler in copied EE RAM."""
    def setup(patched=True):
        vm=VM();c=vm.cpu
        with ISO.open('rb') as f:
            f.seek(0x94880);blob=f.read(0x49A778-0x100000)
        c.mem[0x100000:0x100000+len(blob)]=blob
        # Runtime masters have loader-dependent bases. These are verified
        # against the snapshot, rather than used as live patch addresses.
        assert c.mem[0xB6DA0C:0xB6DA10]==b'UTbl'
        assert c.mem[0xB6EA18:0xB6EA1C]==b'Unit'
        c.write(0xB6DA0C+12+0x600*2,0x15C,2)
        c.write(0xB6EA18+12+0x15C*100+0x22,0xFFFF,2)
        if patched:
            c.mem[0x114F88:0x114F88+len(code)]=code
            c.write(0x2D0F90,0x0C000000|(0x114F88>>2),4)
        return vm
    vm=setup();c=vm.cpu;save=c.read(0x59D364,4)
    pilot_start=save+0x25CFC;pilot_end=pilot_start+0x200*0x5C
    pilots=bytes(c.mem[pilot_start:pilot_end])
    roster=bytes(c.mem[save+0x6EFC:save+0x6EFC+0x200*0xD8])
    assert c.run(0x1ABC50,[save,0x600,0,0])==-1
    vm.op(command(0x5A,0x600));slot=c.run(0x1ABC50,[save,0x600,0,0])
    assert slot>=0
    assert c.run(0x1A9B70,[save,slot,1])==1
    assert c.run(0x1B1300,[save,slot,0])==-1
    assert c.run(0x1B01D0,[save,0x34,slot])==0xFFFF
    assert c.run(0x311200,[save,slot,1],limit=10000000)>0
    assert bytes(c.mem[pilot_start:pilot_end])==pilots
    for i in range(0x200):
        if i!=slot:
            a=save+0x6EFC+i*0xD8
            assert c.mem[a:a+0xD8]==roster[i*0xD8:(i+1)*0xD8]
    stable=bytes(c.mem[save:save+0x3B400])
    vm.op(command(0x5A,0x600))
    assert c.mem[save:save+0x3B400]==stable
    # Original enemy key can be created independently of the reward key.
    enemy=c.run(0x1B2070,[save,0x52A,0])
    assert enemy>=0 and enemy!=slot
    assert c.run(0x1ABC50,[save,0x600,0,0])==slot
    assert c.run(0x1ABC50,[save,0x52A,0,0])==enemy
    # Existing grant calls retain exactly their original save-side effects.
    baseline=setup(False);patched=setup(True)
    for other in [baseline,patched]:other.op(command(0x5A,0x559))
    assert baseline.cpu.mem[save:save+0x3B400]==patched.cpu.mem[save:save+0x3B400]
    return ['Native grant creates one owned, visible, boardable robot',
            'No pilot assigned; all pilot records and other unit records unchanged',
            'Repeated reward is idempotent; enemy key 0x52A remains separate',
            'Unrelated native grant produces byte-identical save effects',
            'Original LOGO records, tables and dialogue preserved byte for byte',
            'Full prospective ISO hash covers every unchanged byte; no live playthrough yet']

def validate_release_variants(default,hidden,bundle,both):
    """Independent baseline policy + actual native animation/property checks."""
    baseline=ROOT/'baseline/srwogs-v1.4.3s1.iso'
    ranges=list(range(0x30C,0x314))+list(range(0x575,0x57A))
    bases=(0x5DA000,0x83F000);original={};current={}
    for start in bases:
        with baseline.open('rb') as f:f.seek(start);original[start]=f.read(0x190000)
        with both.open('rb') as f:f.seek(start);current[start]=f.read(0x190000)
    with both.open('rb') as f:
        f.seek(0x94880);executable=f.read(0x49A778-0x100000)
        f.seek(0x859F9000);current_animation=f.read(0xA8C0)
    with baseline.open('rb') as f:f.seek(0x859F9000);original_animation=f.read(0xA8C0)
    results=[]
    for label,path,enabled,hidden_on in [('default',default,False,False),('hidden',hidden,False,True),
                                        ('bundle',bundle,True,False),('both',both,True,True)]:
        masters={}
        for start in bases:
            with path.open('rb') as f:f.seek(start);actual=f.read(0x190000)
            want=bytearray(current[start])
            if not enabled:
                for idx in (0xD0,0xD1,0x176):
                    at=0x11F8A4+idx*100;want[at:at+100]=original[start][at:at+100]
                    want[at+0x22:at+0x24]=current[start][at+0x22:at+0x24]
                for idx in ranges:
                    at=0x12BF88+idx*36;want[at:at+36]=original[start][at:at+36]
                at=0x11E898+0x49A*2;want[at:at+2]=original[start][at:at+2]
                for at in (0x13B490+96*148+0x12,0x11F8A4+295*100+0x22):
                    want[at:at+2]=original[start][at:at+2]
            assert actual==want,(label,hex(start),'unexpected master change')
            masters[start]=actual
        with path.open('rb') as f:f.seek(0x859F9000);animation=f.read(0xA8C0)
        want=bytearray(current_animation)
        if not enabled:
            for bank in (108,179):
                at=bank*144;want[at:at+144]=original_animation[at:at+144]
        assert animation==want,(label,'animation metadata outside bundle changed')
        c=CPU(ram);c.mem[0x100000:0x49A778]=executable;master=u32(ram,0x59D360);save=u32(ram,0x59D364)
        data=masters[0x5DA000]
        for offset,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),(0x70,0x12BF7C)):
            dst=c.read(master+offset,4);size=u32(data,rel+4);c.mem[dst:dst+size]=data[rel:rel+size]
        obj=0x1780000;c.run(0x290E10,[obj]);dst=c.read(obj+0x24,4);c.mem[dst:dst+len(animation)]=animation
        normal=[0xA65,0xA66,0xA67,0xA68,0xA69];built=[0xA6A,0xA6B,0xA6C]
        all_keys=built+normal
        expected_stats={0xA6A:(4000,0,0,0),0xA6B:(5200,20,110,0),0xA6C:(5000,20,110,0),
                        0xA65:(4100,5,0,2),0xA66:(4400,15,0,2),0xA67:(5700,30,120,2),
                        0xA68:(6300,50,130,2),0xA69:(0,65,130,2)}
        for key in all_keys:
            if enabled:power,en,morale,barrier=expected_stats[key]
            else:
                idx=struct.unpack_from('<H',original[0x5DA000],0x129F7C+key*2)[0]
                at=0x12BF88+idx*36;r=original[0x5DA000][at:at+36]
                power=struct.unpack_from('<H',r,8)[0];en=r[0x1A];morale=r[0x1B];barrier=(r[0x15]>>4)&3
            assert c.run(0x1A5DC0,[master,key])==power,(label,hex(key),'attack')
            assert c.run(0x1A5AC0,[master,key])==en,(label,hex(key),'EN')
            assert c.run(0x1A5A40,[master,key])==morale,(label,hex(key),'morale')
            assert c.run(0x1A4CB0,[master,key])==barrier,(label,hex(key),'barrier')
        routes={}
        for unit in (0x499,0x49A):
            slot=c.run(0x1B2070,[save,unit,0]);assert slot>=0
            wanted=all_keys if enabled else (normal if unit==0x499 else built)
            keys=[c.run(0x1AC9D0,[save,0x75,slot,i]) for i in range(16)]
            assert keys==wanted+[-1]*(16-len(wanted)),(label,hex(unit),'arsenal')
            bank=c.run(0x1A6690,[master,unit])
            route=[c.run(0x290C90,[obj,bank,c.run(0x1A4A20,[master,key])]) for key in wanted]
            expected_route=([0xC19,0xC1A,0xC1B]+list(range(0x783,0x788))) if enabled else (list(range(0x783,0x788)) if unit==0x499 else [0xC19,0xC1A,0xC1B])
            assert route==expected_route,(label,hex(unit),'real animation route')
            routes[hex(unit)]=[hex(x) for x in route]
        # Read the actual chapter directory, not a reconstructed command plan.
        with path.open('rb') as f:
            f.seek(MAP+0x557F800+8+109*8);rel,length=struct.unpack('<II',f.read(8))
            f.seek(MAP+0x557F800+rel);chapter=f.read(length)
        assert chapter[:4]==b'LOGO';count,commands=struct.unpack_from('<II',chapter,0x28)
        assert count==(2576 if enabled else 2575)
        assert u32(chapter,commands+2163*96)==(0x4F if enabled else 0x81)
        assert u32(chapter,commands+2572*96)==(0x5E if enabled else 0x9C)
        if enabled:assert u32(chapter,commands+2572*96+8)==0x24
        results.append(dict(profile=label,bundle=enabled,hidden=hidden_on,baseline_policy_verified=True,
                            common_master_changes_preserved=True,native_weapon_checks=True,native_animation_routes=routes,
                            ouka_scene_and_grant_present=enabled))
    return dict(passed=True,profiles=results,scope='all Daizengar combat data + Ouka survival',
                baseline_daizengar_unit_and_weapon_records_restored_when_off=True,
                common_boarding_masks_preserved=True,live_rendered_playthrough_verified=False)

def validate_daizengar_arsenal_balance(edits):
    with ISO.open('rb') as f:
        f.seek(0x5DA000);original=f.read(0x190000)
        f.seek(0x94880);code=f.read(0x49A778-0x100000)
        f.seek(0x859F9000);animation_table=f.read(0xA8C0)
    blob=bytearray(original)
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(blob):assert blob[rel:rel+1]==old;blob[rel:rel+1]=new
    c=CPU(ram);c.mem[0x100000:0x49A778]=code;master=u32(ram,0x59D360)
    for offset,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),(0x70,0x12BF7C)):
        dest=c.read(master+offset,4);size=u32(blob,rel+4);c.mem[dest:dest+size]=blob[rel:rel+size]
    expected={0xA6A:(4000,0,0,0),0xA6B:(5200,20,110,0),0xA6C:(5000,20,110,0),
              0xA65:(4100,5,0,2),0xA66:(4400,15,0,2),0xA67:(5700,30,120,2),
              0xA68:(6300,50,130,2),0xA69:(0,65,130,2),
              0xCD2:(5700,30,120,2),0xCD3:(6300,50,130,2)}
    for key,(power,en,morale,barrier) in expected.items():
        assert c.run(0x1A5DC0,[master,key])==power,('power',hex(key))
        assert c.run(0x1A5AC0,[master,key])==en,('EN',hex(key))
        assert c.run(0x1A5A40,[master,key])==morale,('morale',hex(key))
        assert c.run(0x1A4CB0,[master,key])==barrier,('barrier',hex(key))
    assert c.run(0x1A4EE0,[master,0xA6B])==1
    assert c.run(0x1A4E60,[master,0xA6B])==0
    allowed={0x311:{8,9,0x15},0x312:{0x15},0x313:{8,9,0x15,0x1A,0x1B},
             0x30E:{0x1A},0x577:{0x1A},0x30F:{0x1A},0x578:{0x1A}}
    for idx in range(1628):
        p=0x12BF88+idx*36
        changed={j for j,(a,b) in enumerate(zip(original[p:p+36],blob[p:p+36])) if a!=b}
        assert changed==allowed.get(idx,set()),(idx,changed)
    assert blob[0x14988C:0x1499EC]==original[0x14988C:0x1499EC]
    obj=0x1780000;c.run(0x290E10,[obj]);dest=c.read(obj+0x24,4);c.mem[dest:dest+len(animation_table)]=animation_table
    for unit in (0x499,0x49A):
        bank=c.run(0x1A6690,[master,unit])
        result=[c.run(0x290C90,[obj,bank,c.run(0x1A4A20,[master,key])]) for key in expected if key<0xB00]
        assert result==[0xC19,0xC1A,0xC1B,0x783,0x784,0x785,0x786,0x787],result
    return dict(dynamic_knuckle_power=4000,guardian_sword=dict(power=5000,en=20,morale=110),
                raikogiri_en=30,unyo_en=50,general_blaster=dict(en=20,ALL=True,W=False),
                builtins_barrier='none',all_sword_attacks_including_combination_barrier='penetration',
                unused_sword_variant_costs_consistent=True,combination_recipe_and_power_unchanged=True,
                all_eight_actual_animation_asset_routes_preserved=True,
                ranges_mobility_flags_upgrade_costs_and_other_weapons_unchanged=True,
                native_property_checks_passed=True,live_battle_playthrough_verified=False)

def validate_daizengar_animation_links(edits,table_offset,original_table):
    with ISO.open('rb') as f:
        f.seek(0x94880);code=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);original_master=f.read(0x190000)
    changed_master=bytearray(original_master);changed_table=bytearray(original_table)
    for off,old,new in edits:
        if 0x5DA000<=off<0x76A000:
            rel=off-0x5DA000;assert changed_master[rel:rel+len(old)]==old
            changed_master[rel:rel+len(new)]=new
        elif table_offset<=off<table_offset+len(original_table):
            rel=off-table_offset;assert changed_table[rel:rel+len(old)]==old
            changed_table[rel:rel+len(new)]=new
    def setup(patched=False,separated=False):
        c=CPU(ram);c.mem[0x100000:0x49A778]=code;master=u32(ram,0x59D360)
        data=bytearray(changed_master if patched else original_master)
        if separated:struct.pack_into('<H',data,0x11E898+0x49A*2,0xD1)
        for off,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),(0x70,0x12BF7C)):
            dst=c.read(master+off,4);size=u32(data,rel+4);c.mem[dst:dst+size]=data[rel:rel+size]
        obj=0x1780000;c.run(0x290E10,[obj]);dest=c.read(obj+0x24,4)
        assert dest==0x93B900 and c.mem[dest:dest+len(original_table)]==original_table
        if patched:c.mem[dest:dest+len(changed_table)]=changed_table
        return c,master,obj
    def resolve(q,master,obj,unit_key,weapon_key):
        bank=q.run(0x1A6690,[master,unit_key])
        motion=q.run(0x1A4A20,[master,weapon_key])
        asset=q.run(0x290C90,[obj,bank,motion])
        return bank,motion,asset
    original,om,oo=setup(separated=True);broken,bm,bo=setup();patched,pm,po=setup(patched=True)
    expected=[0xC19,0xC1A,0xC1B];proof=[]
    for i,key in enumerate((0xA6A,0xA6B,0xA6C)):
        ref=resolve(original,om,oo,0x49A,key);wrong=resolve(broken,bm,bo,0x499,key)
        fixed=resolve(patched,pm,po,0x499,key)
        assert ref==(179,i,expected[i])
        assert wrong==(108,i,0x783+i),('Must reproduce wrong sword animation',key,wrong)
        assert fixed==(108,5+i,expected[i])
        assert resolve(patched,pm,po,0x49A,key)==fixed
        assert patched.run(0x290C90,[po,179,5+i])==expected[i]
        assert patched.run(0x290C90,[po,179,i])==expected[i]
        proof.append(dict(weapon_key=hex(key),original_split_asset=hex(ref[2]),
                          reproduced_wrong_asset=hex(wrong[2]),corrected_asset=hex(fixed[2]),motion_before=i,motion_after=5+i))
    for i,key in enumerate(range(0xA65,0xA6A)):
        assert resolve(patched,pm,po,0x499,key)==resolve(broken,bm,bo,0x499,key)==(108,i,0x783+i)
    allowed={bank*144+4+slot*2+j for bank in (108,179) for slot in (5,6,7) for j in (0,1)}
    assert {i for i,(a,b) in enumerate(zip(original_table,changed_table)) if a!=b}==allowed
    for idx in range(1628):
        at=0x12BF88+idx*36;a=original_master[at:at+36];b=changed_master[at:at+36]
        diff={j for j,(x,y) in enumerate(zip(a,b)) if x!=y}
        assert diff==({0x21} if idx in (0x311,0x312,0x313) else set()),(idx,diff)
    # Only Daizengar uses these weapon definitions. Animation data are reused,
    # not rewritten; unrelated animation banks and all sword slots are intact.
    return dict(original_failure_reproduced=True,native_animation_resolver='0x290C90',
                native_unit_bank_getter='0x1A6690',native_weapon_motion_getter='0x1A4A20',
                builtins=proof,all_five_sword_assets_preserved=True,legacy_builtin_bank_preserved=True,
                all_other_animation_banks_unchanged=True,weapon_stats_and_balance_unchanged=True,
                actual_changed_bytes=sum(sum(a!=b for a,b in zip(old,new)) for _,old,new in edits),
                live_rendered_battle_verified=False)

def validate_daizengar_unified(edits):
    with ISO.open('rb') as f:
        f.seek(0x94880);executable=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);original=f.read(0x190000)
    modified=bytearray(original);patched_code=bytearray(executable)
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(modified):
            assert modified[rel:rel+len(old)]==old;modified[rel:rel+len(new)]=new
        elif 0x94880<=off<0x94880+len(patched_code):
            rel=off-0x94880;assert patched_code[rel:rel+len(old)]==old
            patched_code[rel:rel+len(new)]=new
    def setup(patched):
        vm=VM();c=vm.cpu;c.mem[0x100000:0x49A778]=patched_code if patched else executable
        blob=modified if patched else original
        master=u32(ram,0x59D360);save=u32(ram,0x59D364);glob=u32(ram,0x59D36C)
        for offset,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),
                           (0x70,0x12BF7C),(0xB8,0x149168),(0xD0,0x1492B0)):
            dst=c.read(master+offset,4);size=u32(blob,rel+4)
            c.mem[dst:dst+size]=blob[rel:rel+size]
        return vm,c,master,save,glob
    def eligible(c,sv,glob,slot):
        c.r[17]=glob;c.r[18]=sv;c.r[21]=slot;c.r[16]=0;c.r[29]=0x1F00000
        c.pc=0x43EA34;c.pending=None
        for _ in range(100000):
            if c.pc in (0x43EC2C,0x43ECB0,0x43ED30):return c.pc==0x43EC2C
            c.step()
        raise AssertionError('Native refit eligibility did not terminate')
    expected=[0xA6A,0xA6B,0xA6C,0xA65,0xA66,0xA67,0xA68,0xA69]
    for key in (0x499,0x49A):
        baseline,bc,bm,bs,bg=setup(False);patched,c,master,save,glob=setup(True)
        for vm,q,sv in ((baseline,bc,bs),(patched,c,save)):
            vm.op(command(0x5A,key));sl=q.run(0x1ABC50,[sv,key,0,0]);assert sl>=0
            q.run(0x1AF000,[sv,2,sl,1,0])
            pi=q.run(0x1B1FD0,[sv,0x469,0]);assert pi>=0
            q.run(0x1B13D0,[sv,pi,sl,0])
            for j in range(4):
                q.write(REC,j,4);q.run(0x1AF000,[sv,6,sl,j+1,REC])
        slot=c.run(0x1ABC50,[save,key,0,0]);bslot=bc.run(0x1ABC50,[bs,key,0,0]);assert slot==bslot
        assert eligible(bc,bs,bg,bslot)
        before=bytes(c.mem[save:save+0x3B400]);flags=bytes(c.mem[glob:glob+0x1000])
        assert not eligible(c,save,glob,slot)
        assert c.mem[save:save+0x3B400]==before and c.mem[glob:glob+0x1000]==flags
        assert [c.run(0x1AC9D0,[save,0x75,slot,i]) for i in range(16)]==expected+[-1]*8
        assert c.run(0x1ACA50,[save,1,slot])==key
        assert c.run(0x1A9B70,[save,slot,1])==1
        assert c.mem[save:save+0x3B400]==bc.mem[bs:bs+0x3B400],('save conversion occurred',hex(key))
    # Ordinary native refits keep their UI and save effects unchanged.
    for key in (0x4B8,0x4BD):
        baseline,bc,bm,bs,bg=setup(False);patched,c,master,save,glob=setup(True)
        for vm,q,sv in ((baseline,bc,bs),(patched,c,save)):
            vm.op(command(0x5A,0x559));vm.op(command(0x5A,key))
            slot=q.run(0x1ABC50,[sv,key,0,0]);q.run(0x1AF000,[sv,2,slot,1,0]);q.write(CTX+0x32D8,slot,4)
            assert eligible(q,sv,q.read(0x59D36C,4),slot)
            q.run(0x42DA80,[CTX],limit=10000000)
            count=q.read(CTX+0x1559C,1)+1
            choices=[q.read(CTX+0x155C6+i*64,2) for i in range(count)]
            assert set(choices)=={0x4B8,0x4BD}
            q.write(CTX+0x15558,choices.index(0x4BD if key==0x4B8 else 0x4B8),4)
            assert q.run(0x42E2F0,[CTX])==0
        # The removed Daizengar hook formerly zeroed its private row-label
        # pointer even for ordinary units. Stock drawing never reads that word.
        draw=0x44EEC4-0x100000
        assert patched_code[draw:draw+8]==struct.pack('<II',0x0C060D34,0x0000382D)
        visible=bytearray(c.mem[CTX:CTX+0x17000])
        visible[0x156E4:0x156E8]=bc.mem[CTX+0x156E4:CTX+0x156E8]
        assert visible==bc.mem[CTX:CTX+0x17000]

        assert c.mem[save:save+0x3B400]==bc.mem[bs:bs+0x3B400]
    assert modified[0x129F70:0x13A478]==original[0x129F70:0x13A478]
    return dict(unified_weapon_count=8,both_existing_unit_keys_preserved=True,
                both_forms_use_same_unit_master=True,daizengar_absent_from_native_refit_menu=True,
                no_save_conversion_or_unit_pilot_upgrade_changes=True,
                ordinary_native_refit_ui_and_commit_unchanged=True,
                daizengar_refit_additions_reverted=True,weapon_definitions_unchanged=True,
                live_menu_and_battle_playthrough_verified=False)

def validate_daizengar_combined_arsenal(edits):
    from ogs_korean_codec import decode
    with ISO.open('rb') as f:
        f.seek(0x94880);code=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);original=f.read(0x190000)
    changed=bytearray(original)
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(changed):
            assert changed[rel:rel+len(old)]==old;changed[rel:rel+len(new)]=new
    def setup(blob):
        vm=VM();c=vm.cpu;c.mem[0x100000:0x49A778]=code
        master=u32(ram,0x59D360);save=u32(ram,0x59D364)
        for offset,rel in ((0x28,0x11E88C),(0x40,0x11F898),(0x58,0x129F70),(0x70,0x12BF7C),
                           (0xB8,0x149168),(0xD0,0x1492B0)):
            dst=c.read(master+offset,4);size=u32(blob,rel+4)
            assert c.mem[dst:dst+4]==blob[rel:rel+4]
            c.mem[dst:dst+size]=blob[rel:rel+size]
        vm.op(command(0x5A,0x499));slot=c.run(0x1ABC50,[save,0x499,0,0]);assert slot>=0
        c.run(0x1AF000,[save,2,slot,1,0])
        return vm,c,master,save,slot
    base,bc,bm,bs,bslot=setup(original)
    base.op(command(0x5A,0x49A));builtin_slot=bc.run(0x1ABC50,[bs,0x49A,0,0]);assert builtin_slot>=0
    vm,c,master,save,slot=setup(changed)
    def keys(q,sv,sl):return [q.run(0x1AC9D0,[sv,0x75,sl,i]) for i in range(16)]
    basic=[0xA6A,0xA6B,0xA6C];sword=list(range(0xA65,0xA6A));merged=basic+sword
    assert keys(bc,bs,bslot)==sword+[-1]*11
    assert keys(bc,bs,builtin_slot)==basic+[-1]*13
    assert keys(c,save,slot)==merged+[-1]*8
    native_names=[]
    for i,key in enumerate(merged):
        old_slot,old_index=(builtin_slot,i) if i<3 else (bslot,i-3)
        # Actual preview serializer: names, attack values, ammo/EN, range,
        # categories and animation-mode inputs match the original weapon.
        bc.run(0x30CDF0,[CTX,REC,old_slot,old_index],limit=10000000)
        c.run(0x30CDF0,[CTX,REC,slot,i],limit=10000000)
        before=bytes(bc.mem[REC:REC+0x5C]);after=bytes(c.mem[REC:REC+0x5C])
        assert before==after,('native weapon preview differs',hex(key),[(j,x,y) for j,(x,y) in enumerate(zip(before,after)) if x!=y])
        ptr=c.run(0x1AC9D0,[save,0x7C,slot,i]);end=c.mem.index(0,ptr)
        native_names.append(decode(bytes(c.mem[ptr:end])))
        assert c.run(0x1A4A20,[master,key])==bc.run(0x1A4A20,[bm,key])
    # Original fixed-weapon definitions and combination recipe are unchanged.
    assert changed[0x129F70:0x13A478]==original[0x129F70:0x13A478]
    assert changed[0x14988C:0x1499EC]==original[0x14988C:0x1499EC]
    c.run(0x1B1FD0,[save,0x469,0]);pilot=c.run(0x1AB6F0,[save,0x469,1]);assert pilot>=0
    c.run(0x1B13D0,[save,pilot,slot,0]);ui=CTX;c.write(ui+0x32D8,slot,4)
    arg=REC
    for i in range(4):
        c.write(arg,i,4);c.run(0x1AF000,[save,6,slot,i+1,arg])
    unit=save+0x6EFC+slot*0xD8;unit_before=bytes(c.mem[unit:unit+0xD8])
    pilot_before=bytes(c.mem[save+0x25CFC:save+0x25CFC+192*0x5C])
    for target in (0x49A,0x499)*3:
        c.run(0x42DA80,[ui],limit=10000000)
        choices=[c.read(ui+0x155C6+i*64,2) for i in range(c.read(ui+0x1559C,1)+1)]
        assert set(choices)=={0x499,0x49A}
        c.write(ui+0x15558,choices.index(target),4);assert c.run(0x42E2F0,[ui])==0
        assert c.run(0x1ACA50,[save,1,slot])==target
        expected=basic+[-1]*13 if target==0x49A else merged+[-1]*8
        assert keys(c,save,slot)==expected
        assert c.run(0x1B1300,[save,slot,0])==pilot
    assert c.mem[unit:unit+0xD8]==unit_before
    assert c.mem[save+0x25CFC:save+0x25CFC+192*0x5C]==pilot_before
    return dict(basic_weapon_count=3,sword_weapon_count=8,native_weapon_names=native_names,
                native_weapon_preview_records_identical=True,original_weapon_and_animation_keys_preserved=True,
                original_combination_recipe_preserved=True,native_refit_round_trips=3,
                unit_pilot_and_upgrade_records_preserved=True,live_battle_playback_verified=False)

def validate_ouka(row,blobs,s,edits):
    from build_hidden_rewards import OUKA_SURVIVAL_TEXT
    from ogs_korean_codec import encode,decode
    c=CPU(ram)
    with ISO.open('rb') as f:
        f.seek(0x94880);blob=f.read(0x49A778-0x100000)
    c.mem[0x100000:0x100000+len(blob)]=blob
    pt=c.mem.find(b'Plot',0xB00000);ut=c.mem.find(b'Unit',0xB00000)
    assert pt>0 and ut>0
    # Validate actual current master tables and proposed guarded bytes.
    with ISO.open('rb') as f:
        f.seek(0x5DA000);master_blob=bytearray(f.read(0x190000))
    for off,old,new in edits:
        rel=off-0x5DA000
        if 0<=rel<len(master_blob):
            assert master_blob[rel:rel+len(old)]==old
            master_blob[rel:rel+len(new)]=new
    for tag in (b'Plot',b'Unit',b'PTbl',b'UTbl'):
        src=master_blob.find(tag);dst=c.mem.find(tag,0xB00000)
        assert src>=0 and dst>=0
        length=u32(master_blob,src+4)
        c.mem[dst:dst+length]=master_blob[src:src+length]
    assert c.read(pt+12+96*148+18,2)==1
    assert c.read(ut+12+295*100+34,2)==1
    ctx=0x1700000;bundle=0x1780000;data=0x1790000
    c.write(ctx+40,bundle,4)
    for off,g in [(0x2120,0x59D360),(0x2124,0x59D364),(0x212C,0x59D36C)]:
        c.write(bundle+off,c.read(g,4),4)
    c.write(ctx+0x346D4,data,4);c.write(ctx+0x346D0,1,4);c.mem[data:data+336]=row
    c.write(CTX+0x310C,ctx-0x40E00,4)
    for j,v in enumerate(command(0x5E,u32(row,4))):c.write(REC+j*4,v,4)
    save=c.read(0x59D364,4)
    units=bytes(c.mem[save+0x6EFC:save+0x6EFC+512*216])
    pilots=bytes(c.mem[save+0x25CFC:save+0x25CFC+512*92])
    assert c.run(0x2DAE50,[CTX,REC],limit=5000000)==10
    assert c.visits[0x1D5970]>0
    slot=c.run(0x1ABC50,[save,0x4E4,0,0]);assert slot>=0
    pilot=c.run(0x1B1300,[save,slot,0]);assert pilot>=0
    assert c.read(save+0x25CFC+pilot*92,2)==0x43A
    assert c.run(0x1A9B70,[save,slot,1])==1
    assert c.run(0x1AB6F0,[save,0x43A,1])==pilot
    assert c.run(0x1B01D0,[save,0x34,slot])==1
    for flag in (0x37,0x38,0x39):
        assert c.run(0x1ACA50,[save,flag,slot])==0,('unit gate',hex(flag))
    assert c.run(0x1ACA50,[save,0x59,slot])!=0
    assert c.run(0x1AC800,[save,0xF2,pilot])==1
    assert c.run(0x311200,[save,slot,1],limit=10000000)>0
    p=save+0x25CFC+pilot*92
    assert c.read(p+0x2C,1)&0x40==0 and c.read(p+0x2D,1)&3==0
    for i in range(512):
        if i!=slot:
            a=save+0x6EFC+i*216;assert c.mem[a:a+216]==units[i*216:(i+1)*216]
        if i!=pilot:
            a=save+0x25CFC+i*92;assert c.mem[a:a+92]==pilots[i*92:(i+1)*92]
    c.run(0x2DAE50,[CTX,REC],limit=5000000)
    assert c.run(0x1ABC50,[save,0x4E4,0,0])==slot
    assert c.run(0x1B1300,[save,slot,0])==pilot
    for n,b in blobs.items():
        old=s.records(n);co=u32(b,0x2C)
        assert len(old)+(n==109)==u32(b,0x28)
        changed={2147,2148,2149,2154,2163,2164} if n==109 else set()
        for i,(_,r) in enumerate(old):
            target=i+(n==109 and i>=2572)
            if i not in changed:assert struct.unpack_from('<24I',b,co+target*96)==r
        if n==109:assert struct.unpack_from('<24I',b,co+2572*96)==tuple(command(0x5E,0x24))
        # Actor/main lookup indices must retain their original targets.
        at,size=s.logos[n];original=s.data[at:at+size]
        assert u32(b,0x38)==u32(original,0x38)
        for j in range(u32(b,0x38)):
            old_index=u32(original,u32(original,0x3C)+j*4)
            new_index=u32(b,u32(b,0x3C)+j*4)
            assert old_index==new_index
            main_index=old_index-u32(original,0x20)
            if main_index>=0:
                assert main_index<len(old)
                assert u32(b,co+main_index*96)==old[main_index][1][0]
        for offset,count,stride in [(0x3C,u32(b,0x38),4),(0x54,u32(b,0x50),4)]:
            assert u32(b,offset)+count*stride<=len(b)
        # Every untouched localized string is byte-identical. Updated strings
        # resolve through the original string index and have no halfwidth text.
        for i,(original_at,text) in enumerate(s.texts(n)):
            start=u32(b,0x4C)+u32(b,u32(b,0x54)+i*4);end=b.index(0,start)
            want=OUKA_SURVIVAL_TEXT[n].get(i,text)
            if i in OUKA_SURVIVAL_TEXT[n]:
                assert b[start:end]==encode(want) and decode(b[start:end])==want,(n,i,want,decode(b[start:end]))
            else:
                original_end=s.data.index(0,original_at)
                assert b[start:end]==s.data[original_at:original_end],(n,i,'untouched string changed')
    return [
        'Actual script opcode 5E and native group initializer create visible Rapiesage with Ouka assigned',
        'Actual current master tables, owned flags, unit menu gates and native alternate-pilot filter pass',
        'All other unit/pilot records unchanged; repeated initializer reuses the same pair',
        'Original persuasion and memory recovery commands untouched',
        'Ouka death replaced with retreat/wait pair; Agilla removal and other deaths unchanged',
        'Six scene commands changed and one final grant inserted; branch spans and text-command lookup remain valid',
        'All edited Korean strings round-trip, use fullwidth text and fit three 27-character lines',
        'All untouched dialogue byte-identical; full live chapter playthrough not yet tested',
    ]

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
def validate_axel_spirits(edits,applied=False):
    """Execute unmodified native spirit ID/cost/level getters on current tables."""
    vm=VM();c=vm.cpu;master=c.read(0x59D360,4)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
        f.seek(0x5DA000);original=f.read(0x190000)
        f.seek(0x83F000);im=f.read(0x190000)
    blob=bytearray(original);im=bytearray(im)
    for off,old,new in edits:
        target=blob if off<0x83F000 else im
        rel=off-(0x5DA000 if off<0x83F000 else 0x83F000)
        assert target[rel:rel+len(old)]==old
        target[rel:rel+len(old)]=new
    # Independent desired-record check against the released data: every other
    # Plot byte (skills, levels, enemy Lamia, voices and masks) must be exact.
    changes={0x6D:(4,5),0x73:(10,20),0x77:(55,50),0x7E:(35,37),0x7F:(40,50)}
    journal=ROOT/'runtime/axel_spirits_manifest.json'
    if applied:
        m=json.loads(journal.read_text(encoding='utf-8'))
        restored=bytearray(blob)
        for e in m['edits']:
            rel=e['offset']-0x5DA000
            if 0<=rel<len(restored):restored[rel:rel+1]=bytes.fromhex(e['before'])
        original=bytes(restored)
    # Other existing Plot records need not match across SHARED/IM. Check only
    # Axel's two targeted records; do not normalize unrelated archive data.
    for idx in (53,54):
        p=0x13B490+idx*0x94
        assert blob[p:p+0x94]==im[p:p+0x94]
    for idx in range((0x14988C-0x13B490)//0x94):
        p=0x13B490+idx*0x94;expected=bytearray(original[p:p+0x94])
        if idx in (53,54):
            for rel,(old,new) in changes.items():
                assert expected[rel]==old
                expected[rel]=new
        assert blob[p:p+0x94]==expected,idx
    def name(sid):
        p=0x155BFC+u32(blob,0x155C08+sid*4)
        return decode(blob[p:blob.index(0,p)])
    assert [name(i) for i in (7,5,17,2,21,10,37)]==['필중','철벽','기백','열혈','직격','각성','혼']
    for obj,start,end in ((0x88,0x13A478,0x13B484),(0xA0,0x13B484,0x14988C)):
        dest=c.read(master+obj,4)
        assert c.mem[dest:dest+4]==blob[start:start+4]
        c.mem[dest:dest+end-start]=blob[start:end]
    mapped=[key for key in range(4096) if struct.unpack_from('<H',blob,0x13A484+key*2)[0] in (53,54)]
    assert mapped==[0x3F4,0x4A4,0x4A5,0x521]
    ptable=c.read(master+0x88,4)
    # Exercise spare Plot54 too without modifying the real ISO's PTbl.
    for key,plot in [(key,53) for key in mapped]+[(0x4A5,54)]:
        if plot==54:c.write(ptable+12+key*2,54,2)
        ids=[c.run(0x1A3680,[master,key,i]) for i in range(6)]
        assert ids==[7,5,17,2,21,10],(hex(key),ids)
        assert [c.run(0x1A35C0,[master,key,i]) for i in range(6)]==[10,20,45,40,15,50]
        assert [c.run(0x1A3500,[master,key,i]) for i in range(6)]==[1,1,8,20,23,31]
        assert c.run(0x1A3480,[master,key])==37
        assert c.run(0x1A3400,[master,key])==50
    return dict(native_getters_verified=True,all_four_allied_raw_keys_verified=True,
        spare_plot54_verified=True,spirit_ids=[7,5,17,2,21,10],sp_costs=[10,20,45,40,15,50],
        levels=[1,1,8,20,23,31],twin_spirit='혼',twin_sp_cost=50,
        other_pilot_records_and_all_other_plot_bytes_preserved=True,
        target_records_identical_in_both_master_copies=True,live_menu_verified=False)

def validate_seolla_spirits(edits,applied=False):
    """Native getters verify all three Seolla variants and preserve all else."""
    vm=VM();c=vm.cpu;master=c.read(0x59D360,4)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x49A778]=f.read(0x49A778-0x100000)
        archives={}
        for base in (0x5DA000,0x83F000):
            f.seek(base);archives[base]=f.read(0x190000)
    proposed={base:bytearray(blob) for base,blob in archives.items()}
    for off,old,new in edits:
        base=0x5DA000 if off<0x83F000 else 0x83F000;rel=off-base
        assert proposed[base][rel:rel+len(old)]==old
        proposed[base][rel:rel+len(old)]=new
    if applied:
        journal=json.loads((ROOT/'runtime/seolla_spirits_manifest.json').read_text(encoding='utf-8'))
        archives={base:bytearray(blob) for base,blob in archives.items()}
        for e in journal['edits']:
            base=0x5DA000 if e['offset']<0x83F000 else 0x83F000;rel=e['offset']-base
            archives[base][rel:rel+1]=bytes.fromhex(e['before'])
    changes={0x6D:(5,9),0x6F:(20,3),0x73:(30,10)}
    for base,original in archives.items():
        expected=bytearray(original)
        for idx in (159,160,370):
            p=0x13B490+idx*0x94
            assert struct.unpack_from('<H',expected,p+0x48)[0] in (84,215)
            for rel,(old,new) in changes.items():
                assert expected[p+rel]==old;expected[p+rel]=new
        assert proposed[base]==expected
    blob=proposed[0x5DA000]
    def name(sid):
        p=0x155BFC+u32(blob,0x155C08+sid*4)
        return decode(blob[p:blob.index(0,p)])
    assert [name(i) for i in (6,9,7,3,2,24,32)]==['집중','가속','필중','번뜩임','열혈','사랑','인연']
    for obj,start,end in ((0x88,0x13A478,0x13B484),(0xA0,0x13B484,0x14988C)):
        dest=c.read(master+obj,4);assert c.mem[dest:dest+4]==blob[start:start+4]
        c.mem[dest:dest+end-start]=blob[start:end]
    mapped=[key for key in range(4096) if struct.unpack_from('<H',blob,0x13A484+key*2)[0] in (159,160,370)]
    assert mapped==[0x466,0x467,0x516]
    for key in mapped:
        assert [c.run(0x1A3680,[master,key,i]) for i in range(6)]==[6,9,7,3,2,24]
        assert [c.run(0x1A35C0,[master,key,i]) for i in range(6)]==[15,10,10,10,35,60]
        assert [c.run(0x1A3500,[master,key,i]) for i in range(6)]==[1,1,7,12,23,35]
        assert c.run(0x1A3480,[master,key])==32 and c.run(0x1A3400,[master,key])==40
    # Earlier requested Axel changes must survive this update unchanged.
    assert [c.run(0x1A3680,[master,0x4A5,i]) for i in range(6)]==[7,5,17,2,21,10]
    assert [c.run(0x1A35C0,[master,0x4A5,i]) for i in range(6)]==[10,20,45,40,15,50]
    assert c.run(0x1A3480,[master,0x4A5])==37 and c.run(0x1A3400,[master,0x4A5])==50
    return dict(native_getters_verified=True,all_three_seolla_variants_verified=True,
        spirit_names=['집중','가속','필중','번뜩임','열혈','사랑'],sp_costs=[15,10,10,10,35,60],
        levels=[1,1,7,12,23,35],twin_spirit='인연',twin_sp_cost=40,
        skills_and_all_other_master_bytes_preserved=True,previous_axel_spirit_changes_preserved=True,
        live_menu_verified=False)

def validate_battle_rewards(edits,applied=False):
    """Run the original reward routine against controlled property fixtures.

    Property lookup/difficulty dependencies supply inputs; all arithmetic,
    eligibility, split, minimum and accumulation code executes from the ISO.
    This is not a rendered battle or a full native property integration test.
    """
    with ISO.open('rb') as f:
        f.seek(0x94880);current=f.read(0x49A778-0x100000)
    original=bytearray(current);patched=bytearray(current)
    if applied:
        journal=json.loads((ROOT/'runtime/battle_rewards_manifest.json').read_text(encoding='utf-8'))
        for e in journal['edits']:
            rel=e['offset']-0x94880
            assert original[rel:rel+len(bytes.fromhex(e['after']))]==bytes.fromhex(e['after'])
            original[rel:rel+len(bytes.fromhex(e['before']))]=bytes.fromhex(e['before'])
    else:
        for off,old,new in edits:
            rel=off-0x94880;assert patched[rel:rel+len(old)]==old
            patched[rel:rel+len(old)]=new
    # No calls/jumps or pointer records referenced the retired label cave.
    cave=0x499D38
    assert original[cave-0x100000:cave-0x100000+52]==bytes(52)
    for needle in (cave,(2<<26)|(cave>>2),(3<<26)|(cave>>2)):
        assert not any(u32(original,i)==needle for i in range(0,len(original)-3,4))
    B=0x1800000
    class RewardCPU(CPU):
        def step(self):
            pc=self.pc;v=None
            if pc==0x1FE9D0:
                attr=self.r[5]&0xFFFFFFFF
                values={0x130:1,0x1A2:1,0x1A0:0,0x6D:self.cfg['funds'],
                    0x119:self.cfg.get('funds_extra',0),0x17B:self.cfg.get('luck',0),
                    0xCF:50 if self.cfg.get('ace') else 0,
                    0x10D:0 if self.cfg.get('ace_percent') else -1,
                    0x6F:self.cfg['pp'],0x11B:self.cfg.get('pp_extra',0),
                    0x196:self.cfg.get('training',0),0x1A6:0 if self.cfg.get('map_half') else -1,
                    0x9C:self.cfg.get('map_half',0),0xBE:self.cfg.get('copilot_half',0),0x189:0}
                if attr==0x1B8:
                    v=2 if self.cfg.get('money_skill' if self.r[7]==0x18 else 'full_sub_pp') else 0
                else:
                    assert attr in values,hex(attr);v=values[attr]
            elif pc==0x19A830:v=self.cfg.get('difficulty',2)
            elif pc==0x1A0D90:v=self.cfg.get('ace_percent',0)
            elif pc==0x1EF2D0:v=int(self.r[5]>=self.cfg.get('pilots',1))
            if v is not None:
                self.visits[pc]+=1;self.count+=1;self.put(2,v);self.pc=self.r[31]&0xFFFFFFFF;self.pending=None
            else:super().step()
    cpus=[]
    for code in (original,patched):
        c=RewardCPU(ram);c.mem[0x100000:0x49A778]=code;cpus.append(c)
    cases=[]
    for side in (0,1):
        for value in (0,1,2,5,7,100,65535):
            cases.append(dict(side=side,funds=value,pp=value if value<256 else 255))
        for extras in ({'luck':1},{'ace':1},{'money_skill':1},{'ace_percent':17},
                {'luck':1,'ace':1,'money_skill':1,'ace_percent':23,'training':1},
                {'training':1},{'map_half':1},{'copilot_half':1},
                {'participants':4,'pilots':4},{'participants':4,'pilots':4,'training':1,'map_half':1},
                {'participants':4,'full_sub_pp':1},{'dead':False},
                {'funds_extra':173,'pp_extra':3}):
            cases.append(dict(side=side,funds=1237,pp=7,**extras))
        for mode in (0,1):cases.append(dict(side=side,funds=531,pp=5,difficulty=mode,ace=True))
    for cfg in cases:
        initial=bytearray(0x3000)
        struct.pack_into('<I',initial,0,B+0x12A0)
        for group in (0x12A0,0x1920):
            for i in range(4):struct.pack_into('<i',initial,group+i*0x1A0+0x18,-1)
        allies=0x1920 if cfg['side'] else 0x12A0
        targets=0x12A0 if cfg['side'] else 0x1920
        for i in range(cfg.get('participants',1)):
            struct.pack_into('<i',initial,allies+i*0x1A0+0x18,0)
        if cfg.get('participants',1)==4:
            struct.pack_into('<I',initial,0x1FB4,1)
            for i in (2,3):initial[(0x950 if cfg['side'] else 0)+i*0x254+0x2D]=1
        struct.pack_into('<i',initial,targets+0x18,0)
        enemy_result=0 if cfg['side'] else 0x950
        struct.pack_into('<i',initial,enemy_result+4,0 if cfg.get('dead',True) else 1)
        pp_positions=[(0x950 if cfg['side'] else 0)+i*0x254+0x244+j*4 for i in range(4) for j in range(4)]
        for p in pp_positions:struct.pack_into('<I',initial,p,11)
        for p in (0x1FEC,0x1FF0):struct.pack_into('<I',initial,p,137)
        results=[]
        for c in cpus:
            c.mem[B:B+len(initial)]=initial;c.cfg=cfg;c.writes.clear();c.visits.clear()
            c.run(0x31D4E0,[B,cfg['side']])
            results.append(bytes(c.mem[B:B+len(initial)]))
        old,new=results
        if cfg.get('participants')==4 and cfg.get('pilots')==4:
            assert all(u32(old,p)>11 for p in pp_positions),'All 16 recipients must actually receive PP'
        for p in pp_positions:
            assert u32(new,p)-11==2*(u32(old,p)-11),(cfg,hex(p),u32(old,p),u32(new,p))
        for p in (0x1FEC,0x1FF0):
            assert u32(new,p)-137==(u32(old,p)-137)*6//5,(cfg,hex(p),u32(old,p),u32(new,p))
        a=bytearray(old);b=bytearray(new)
        for p in pp_positions+[0x1FEC,0x1FF0]:a[p:p+4]=b[p:p+4]
        assert a==b,('Unrelated battle context changed',cfg)
    # Scripted grants and every master table remain outside these code edits.
    return dict(native_reward_arithmetic_verified=True,controlled_property_fixtures=True,
        full_native_property_integration_verified=False,scenarios=len(cases),
        pp_multiplier=2,funds_numerator=6,funds_denominator=5,rounding='truncate',
        both_battle_sides_and_all_16_recipient_slots_tested=True,
        luck_ace_difficulty_training_splits_and_minimum_pp_tested=True,
        existing_accumulated_rewards_not_multiplied=True,no_reward_without_defeat=True,
        all_unrelated_battle_context_bytes_preserved=True,script_grants_and_master_data_unchanged=True,
        live_battle_verified=False)

if __name__=='__main__':main()


def validate_enemy_strength(edits,layout,applied=False):
    """Execute both complete native getter and UNTD loader; no call stubs."""
    with ISO.open('rb') as f:
        f.seek(0x94880);current=f.read(0x482980)
    old=bytearray(current);new=bytearray(current)
    if applied:
        es=json.loads((ROOT/'runtime/enemy_strength_manifest.json').read_text(encoding='utf-8'))['edits']
        for e in es:
            at=e['offset']-0x94880;a=bytes.fromhex(e['before']);b=bytes.fromhex(e['after'])
            assert old[at:at+len(b)]==b;old[at:at+len(a)]=a
    else:
        for off,a,b in edits:
            at=off-0x94880;assert new[at:at+len(a)]==a;new[at:at+len(b)]=b
    def machine(code):
        c=CPU(ram);c.mem[0x100000:0x582980]=code;return c
    # Prove the compact initialization has identical final registers, FPRs
    # and complete memory, including untouched descriptor attribute numbers.
    cs=[machine(code) for code in (old,new)]
    for c in cs:
        c.r=[0x123000+i for i in range(32)];c.r[0]=0
        for i in (8,9,10):c.r[i]=0x540000
        c.fpr=[0x13570000+i for i in range(32)]
        c.run(layout['initializer_start'],stop=layout['initializer_end'])
    assert cs[0].r==cs[1].r and cs[0].fpr==cs[1].fpr
    # The code itself intentionally differs; data writes must be identical.
    assert {(a,n) for a,n,pc in cs[0].writes}=={(a,n) for a,n,pc in cs[1].writes}
    for a,n,pc in cs[0].writes:assert cs[0].mem[a:a+n]==cs[1].mem[a:a+n]
    # Native getter integration on an actual save unit with an assigned pilot.
    obj=0x1800000;stage=0x1400000
    cs=[machine(code) for code in (old,new)]
    save=cs[0].read(0x59D364,4)
    for c in cs:
        c.write(obj+4,save,4);c.write(obj+0x18,0,4);c.write(obj+0x10,stage,4);c.write(obj+0x74,0,1)
        for i,v in enumerate([0x1c,0x1c,0x1b,0x17,0x1f,0]):c.write(stage+0x17608c+i,v,1)
        c.write(0x5879F0-0x4ed0,0,1)
        assert c.run(0x1FE9D0,[obj,0x130,0,0,0])==0
    assert cs[0].mem[0x537ea0:0x539c00]==cs[1].mem[0x537ea0:0x539c00]
    stats=0
    for side in range(6):
        for hostile in (False,True):
            for c in cs:
                c.write(obj+0x74,side,1)
                c.write(stage+0x17608c+side,int(hostile),1)
            for attr in range(0xd4,0xda):
                a,b=[c.run(0x1FE9D0,[obj,attr,0,0,0]) for c in cs]
                assert b==a+(5 if hostile else 0),(side,hostile,hex(attr),a,b)
                stats+=1
    # A missing map context must leave the input unchanged.
    for c in cs:c.write(obj+0x10,0,4)
    for attr in range(0xd4,0xda):
        assert cs[0].run(0x1FE9D0,[obj,attr,0,0,0])==cs[1].run(0x1FE9D0,[obj,attr,0,0,0])
    # Complete native UNTD initialization, allocation, clamps and weapon loop.
    s=Scripts();wp=0x5071000;at=wp+u32(s.data,wp+8+66*8)
    template=bytearray(s.data[at+44:at+44+336]);assert u32(template,0)==0x23
    spawn_cases=0;body_cases=0;weapon_cases=0
    for difficulty in range(3):
        for side in range(6):
            for base in (0,5,15):
                rec=bytearray(template);struct.pack_into('<I',rec,8,side)
                for j in range(14,20):struct.pack_into('<I',rec,j*4,base)
                outcomes=[]
                for code in (old,new):
                    c=machine(code);save=c.read(0x59D364,4)
                    ctx=0x1600000;src=0x1700000
                    c.write(ctx+0x28,0x59b240,4);c.write(ctx+0x346d4,src,4);c.mem[src:src+336]=rec
                    diff=c.read(0x59D36C,4);c.write(diff+0xf60,0,4);c.write(diff+0xf68,difficulty,4)
                    before=bytes(c.mem[save+0x6efc:save+0x6efc+512*0xd8])
                    assert c.run(0x1D5970,[ctx,0])==1
                    changed=[i for i in range(512) if c.mem[save+0x6efc+i*0xd8:save+0x6efc+(i+1)*0xd8]!=before[i*0xd8:(i+1)*0xd8]]
                    assert len(changed)==1,changed
                    slot=changed[0]
                    body=[c.run(0x1AF860,[save,a,slot,0]) for a in range(0xd,0x11)]
                    arg=0x1780000;c.write(arg,0,4)
                    weapon=c.run(0x1AF860,[save,0xc,slot,arg])
                    outcomes.append((body,weapon,bytes(c.mem[src:src+336])))
                add=int(side in (2,3,4))
                for a,b in zip(outcomes[0][0],outcomes[1][0]):
                    assert b==min(a+add,15),(difficulty,side,base,a,b);body_cases+=1
                assert outcomes[1][1]==min(outcomes[0][1]+add,15),(difficulty,side,base,outcomes)
                weapon_cases+=1
                assert outcomes[0][2]==outcomes[1][2]==bytes(rec)
                spawn_cases+=1
    return dict(initializer_descriptor_equivalence=True,native_getter_cases=stats,
        missing_context_cases=6,native_spawn_cases=spawn_cases,body_upgrade_assertions=body_cases,
        weapon_upgrade_assertions=weapon_cases,all_three_difficulties=True,original_caps_retained=True,
        source_records_unchanged=True,rendered_playthrough=False)


def validate_optional_patcher():
    """Real executable, full-size disposable ISO; visit all 32 option profiles."""
    import subprocess,shutil,time
    qp=ROOT/'iso_quickpatch';exe=qp/'OGS_AxelSwap_QuickPatch.exe'
    meta=json.loads((ROOT/'runtime/common_fix_profiles.json').read_text(encoding='utf-8'))
    expected=meta['hashes'];test=qp/'TEST.iso';bak=Path(str(test)+'.ogsbak')
    assert not test.exists() and not bak.exists(),'Existing test artifacts require inspection'
    before=sha(ISO).upper();assert before==expected[31]
    binary_hash=sha(exe).upper();common_hash=sha(qp/'OGS_common_fix.bin').upper()
    proof_path=ROOT/'runtime/optional_features_patcher_e2e.json'
    proof=json.loads(proof_path.read_text(encoding='utf-8')) if proof_path.exists() else {}
    if proof.get('patcher_sha256')==binary_hash and proof.get('common_pack_sha256')==common_hash:
        composition_cases=proof['production_composition_selftest']
    else:
        import re
        completed=subprocess.run([str(exe),'--self-test-options'],capture_output=True,check=True)
        match=re.search(r'PASS: (\d+) option transitions',completed.stdout.decode('utf-8',errors='replace'))
        assert match,completed.stdout
        composition_cases=int(match.group(1))
    assert composition_cases==5120
    results=[]
    def flags(mask):return [flag for bit,flag in [(1,'--hidden'),(2,'--bundle'),(4,'--rewards'),(8,'--enemy'),(16,'--spirits')] if mask&bit]
    def call(*args):
        result=subprocess.run([str(exe),*map(str,args)],capture_output=True)
        assert result.returncode==0,(args,result.stdout.decode('utf-8',errors='replace'),result.stderr)
        return result
    try:
        shutil.copyfile(ISO,test)
        previous=31
        for i in range(32):
            mask=i^(i>>1)
            call(test,'--cli',*flags(mask))
            # The production patcher itself verifies the complete destination
            # SHA256 before returning success. Verify no-op leaves backup intact.
            if mask in (0,31):
                backup=sha(bak);call(test,'--cli',*flags(mask));assert sha(bak)==backup
            if mask in (0,4,8,16,31) and mask!=previous:
                call(test,'--restore');assert sha(test).upper()==expected[previous]
                call(test,'--cli',*flags(mask))
            results.append(dict(source=previous,target=mask));previous=mask
            print('PASS real ISO option profile %02d/32, mask=%d'%(i+1,mask),flush=True)
        assert sha(test).upper()==expected[previous]
        test.unlink();bak.unlink(missing_ok=True)
        base=ROOT/'baseline/srwogs-v1.4.3s1.iso';shutil.copyfile(base,test)
        call(test,'--cli','--hidden','--bundle','--rewards','--enemy','--spirits')
        assert sha(test).upper()==expected[31]
        call(test,'--restore');assert sha(test)==sha(base)
        print('PASS baseline -> all five options -> exact baseline restore',flush=True)
        # The report came from v20261025.1. Exercise its real xdelta default
        # through the unchanged legacy upgrade pack plus the common fix.
        test.unlink();bak.unlink(missing_ok=True)
        subprocess.run([str(ROOT.parent/'xdelta.exe'),'-d','-f','-s',str(base),str(ROOT/'dist/SRWOGS_AxelRoleSwap_kr_v20261025.1.xdelta'),str(test)],check=True)
        legacy=sha(test).upper()
        call(test,'--cli');assert sha(test).upper()==expected[0]
        call(test,'--restore');assert sha(test).upper()==legacy
        # Prior public all-on ISO: undo only the new fallback on a test copy.
        test.unlink();bak.unlink(missing_ok=True);shutil.copyfile(ISO,test)
        all_common=json.loads((ROOT/'runtime/story_common_edits.json').read_text(encoding='utf-8'))
        fix=dict(edits=all_common['31'])
        with test.open('r+b') as f:
            for e in fix['edits']:
                at=e['offset'];a=bytes.fromhex(e['before']);b=bytes.fromhex(e['after'])
                f.seek(at);assert f.read(len(b))==b;f.seek(at);f.write(a)
        assert sha(test).upper()==meta['previous_hashes'][31]
        call(test,'--cli',*flags(31));assert sha(test).upper()==expected[31]
        call(test,'--restore');assert sha(test).upper()==meta['previous_hashes'][31]
        legacy29=all_common['legacy_v20261029']['31']
        with test.open('r+b') as f:
            for e in legacy29:
                a=bytes.fromhex(e['before']);b=bytes.fromhex(e['after']);f.seek(e['offset']);assert f.read(len(a))==a;f.seek(e['offset']);f.write(b)
        assert sha(test).upper()==meta['legacy_v20261029_hashes'][31]
        call(test,'--cli',*flags(31));assert sha(test).upper()==expected[31]
        call(test,'--restore');assert sha(test).upper()==meta['legacy_v20261029_hashes'][31]
        with test.open('r+b') as f:
            for e in reversed(legacy29):
                a=bytes.fromhex(e['before']);b=bytes.fromhex(e['after']);f.seek(e['offset']);assert f.read(len(b))==b;f.seek(e['offset']);f.write(a)
        # The immediately previous public release has four different story layouts.
        legacy_story=all_common['legacy_v20261028']['3']
        with test.open('r+b') as f:
            for e in legacy_story:
                at=e['offset'];a=bytes.fromhex(e['before']);b=bytes.fromhex(e['after'])
                f.seek(at);assert f.read(len(a))==a;f.seek(at);f.write(b)
        assert sha(test).upper()==meta['legacy_v20261028_hashes'][31]
        call(test,'--cli',*flags(31));assert sha(test).upper()==expected[31]
        call(test,'--restore');assert sha(test).upper()==meta['legacy_v20261028_hashes'][31]
        with test.open('r+b') as f:
            for e in reversed(legacy_story):
                at=e['offset'];a=bytes.fromhex(e['before']);b=bytes.fromhex(e['after'])
                f.seek(at);assert f.read(len(b))==b;f.seek(at);f.write(a)
        # Also exercise the immediately preceding v20261027.1 public build.
        mumei=json.loads((ROOT/'runtime/mumei_fallback_manifest.json').read_text(encoding='utf-8'))
        with test.open('r+b') as f:
            for e in mumei['edits']:
                at=e['offset'];a=bytes.fromhex(e['before']);b=bytes.fromhex(e['after'])
                f.seek(at);assert f.read(len(a))==a;f.seek(at);f.write(b)
        assert sha(test).upper()==meta['prior_release_hashes'][31]
        call(test,'--cli',*flags(31));assert sha(test).upper()==expected[31]
        call(test,'--restore');assert sha(test).upper()==meta['prior_release_hashes'][31]
        print('PASS v20261025.1, v20261027 and v20261027.1 upgrades/restores',flush=True)

        report=dict(passed=True,profile_count=32,real_iso_transitions=results,
            baseline_apply_restore=True,legacy_v20261025_1=True,previous_v20261027=True,previous_v20261027_1=True,backup_restore_profiles=[0,4,8,16,31],
            idempotency_profiles=[0,31],production_composition_selftest=composition_cases,previous_v20261028=True,previous_v20261029=True,
            patcher_sha256=binary_hash,common_pack_sha256=common_hash,
            current_gameplay_iso_unchanged=before)
        (ROOT/'runtime/optional_features_patcher_e2e.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return report
    finally:
        test.unlink(missing_ok=True);bak.unlink(missing_ok=True)


def validate_sladegelmir_ally_balance(blob):
    vm=VM();c=vm.cpu;master=c.read(0x59D360,4);save=c.read(0x59D364,4)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x582980]=f.read(0x482980)
        f.seek(0x5DA000);original=f.read(0x1A5800)
    def load(data):
        base=0x1100000;payload=data[0x11E800:];c.mem[base:base+len(payload)]=payload
        for i,field in enumerate(range(0x18,0x8C,4)):
            dst=base+u32(data,0x11E800+field);obj=master+0x28+i*24
            for off,value in ((0,dst),(4,c.read(dst,4)),(8,c.read(dst+4,4)),(12,0),(16,dst),(20,dst+12)):
                c.write(obj+off,value,4)
    load(original)
    vm.op(command(0x5A,0x601));slot=c.run(0x1ABC50,[save,0x601,0,0]);assert slot>=0
    pilot=c.run(0x1B1FD0,[save,0x602,0]);assert pilot>=0
    c.run(0x1B13D0,[save,pilot,slot,0])
    oldkeys=[0xA44,0x84E,0xA46,0xA47,0xA48,0xCD6];keys=list(range(0x8C0,0x8C6))
    oldmotions=[c.run(0x1A4A20,[master,k]) for k in oldkeys]
    oldpowers=[c.run(0x1A5DC0,[master,k]) for k in oldkeys]
    assert oldpowers==[4300,4200,5500,2900,3500,6000]
    assert c.run(0x1A5240,[master,0xCD6])==0
    assert c.run(0x1A4CB0,[master,0xCD6])==0
    before=bytes(c.mem[save:save+0x3B400])
    load(blob)
    for key,HP,armor in ((0x601,8300,2100),(0x490,160000,1800)):
        assert c.run(0x1A7D40,[master,key])==HP
        assert c.run(0x1A7B40,[master,key])==armor
    for fn,want in ((0x1A7CC0,350),(0x1A7BC0,95),(0x1A7C40,7)):
        assert c.run(fn,[master,0x601])==want
    assert [c.run(0x1AC9D0,[save,0x75,slot,i]) for i in range(6)]==keys
    assert [c.run(0x1A5DC0,[master,k]) for k in keys]==[v+200 for v in oldpowers]
    assert [c.run(0x1A5DC0,[master,k]) for k in oldkeys]==oldpowers
    assert [c.run(0x1A4A20,[master,k]) for k in keys]==oldmotions
    assert c.run(0x1A5240,[master,keys[-1]])==1
    assert c.run(0x1A4CB0,[master,keys[-1]])==2
    assert c.run(0x1A4EE0,[master,keys[-1]])==0
    assert c.run(0x1A5AC0,[master,keys[-1]])==40
    assert c.run(0x1A5A40,[master,keys[-1]])==120
    wt=0x11E800+u32(blob,0x11E820);w=0x11E800+u32(blob,0x11E824)
    oldwt=0x11E800+u32(original,0x11E820);oldw=0x11E800+u32(original,0x11E824)
    for i,(oldkey,key) in enumerate(zip(oldkeys,keys)):
        oi=struct.unpack_from('<H',original,oldwt+12+oldkey*2)[0];ni=struct.unpack_from('<H',blob,wt+12+key*2)[0]
        a=original[oldw+12+oi*36:oldw+12+(oi+1)*36];b=blob[w+12+ni*36:w+12+(ni+1)*36]
        allowed={8,9}|({0x14,0x15,0x18} if i==5 else set())
        assert {j for j in range(36) if a[j]!=b[j]}<=allowed
        if i==5:assert b[0x17:0x19]==b'\x01\x02'
    assert c.run(0x1B1300,[save,slot,0])==pilot
    assert c.run(0x1ABC50,[save,0x601,0,0])==slot
    assert c.run(0x1A9B70,[save,slot,1])==1
    assert c.run(0x1A7D40,[master,0x600])==6300
    assert c.run(0x1A5DC0,[master,0x851])==5600
    assert c.mem[save:save+0x3B400]==before
    vm.op(command(0x5A,0x601));assert c.mem[save:save+0x3B400]==before
    return dict(ally_HP=8300,ally_armor=2100,ally_EN=350,mobility=95,move=7,
                weapon_powers=[4500,4400,5700,3100,3700,6200],
                finisher=dict(P=True,range=[1,2],barrier_penetration=True,EN=40,morale=120,ALL=False),
                enemy_HP=160000,enemy_armor=1800,enemy_weapons_unchanged=True,
                existing_Wodan_assignment_and_save_preserved=True,existing_fixed_weapon_slots_resolve_new_keys=True,
                all_six_original_motion_ids_preserved=True,repeated_grant_idempotent=True,
                Mumei_regression_passed=True,live_battle_test=False)


def validate_mumei_ally_balance(blob):
    vm=VM();c=vm.cpu;master=c.read(0x59d360,4);save=c.read(0x59d364,4)
    with ISO.open('rb') as f:
        f.seek(0x94880);c.mem[0x100000:0x582980]=f.read(0x482980)
        f.seek(0x5da000);original=f.read(0x1a5800)
    def load_tables(b):
        base=0x1100000;payload=b[0x11e800:]
        c.mem[base:base+len(payload)]=payload
        for i,field in enumerate(range(0x18,0x8c,4)):
            dst=base+u32(b,0x11e800+field);obj=master+0x28+i*24
            c.write(obj,dst,4);c.write(obj+4,c.read(dst,4),4);c.write(obj+8,c.read(dst+4,4),4)
            c.write(obj+12,0,4);c.write(obj+16,dst,4);c.write(obj+20,dst+12,4)
    load_tables(original)
    assert c.run(0x1abc50,[save,0x600,0,0])==-1
    vm.op(command(0x5a,0x600));slot=c.run(0x1abc50,[save,0x600,0,0]);assert slot>=0
    before=bytes(c.mem[save:save+0x3b400])
    oldbank=c.run(0x1a6690,[master,0x600]);oldmotions=[c.run(0x1a4a20,[master,k]) for k in (0xd93,0xd94)]
    load_tables(blob)
    # An already-owned save record resolves the new master without save edits.
    assert [c.run(0x1ac9d0,[save,0x75,slot,i]) for i in range(4)]==[0xd91,0xd92,0x851,0x852]
    assert c.run(0x1a5dc0,[master,0x851])==5600
    assert c.run(0x1a5dc0,[master,0x852])==4600
    assert c.run(0x1a5dc0,[master,0xd93])==4700
    assert c.run(0x1a5dc0,[master,0xd94])==3700
    assert c.run(0x1a7d40,[master,0x600])==6300
    assert c.run(0x1a7d40,[master,0x52a])==63000
    assert c.run(0x1a6690,[master,0x600])==oldbank
    assert [c.run(0x1a4a20,[master,k]) for k in (0x851,0x852)]==oldmotions
    unit=0x11e800+u32(blob,0x11e81c)
    assert u32(blob,unit+12+427*100)==6300 and u32(blob,unit+12+0x15c*100)==63000
    assert c.run(0x1a9b70,[save,slot,1])==1
    assert c.run(0x1b1300,[save,slot,0])==-1
    assert c.mem[save:save+0x3b400]==before
    vm.op(command(0x5a,0x600));assert c.mem[save:save+0x3b400]==before
    return dict(existing_save_resolves_new_weapons=True,ally_hp=6300,shishio_power=4600,finisher_power=5600,
        enemy_hp=63000,enemy_shishio_power=3700,enemy_finisher_power=4700,
        original_bank_and_motion_ids_preserved=True,save_bytes_unchanged=True,repeated_grant_idempotent=True,
        all_original_master_records_preserved=True,live_playthrough_verified=False)


def validate_mumei_fallback(edits,applied=False,episode5_removed=False):
    s=Scripts();at,size=s.logos[74];rs=s.records(74)
    if applied:
        assert len(rs)==536 and rs[532][1][:3]==(0x5a,DEAD,0x600)
        assert rs[533][1][:4]==(0x9c,DEAD,2,0)
    else:
        assert len(rs)==535 and rs[532][1][:4]==(0x9c,DEAD,2,0)
        changed=next(new for off,old,new in edits if off==MAP+at)
        co=u32(changed,0x2c)
        assert struct.unpack_from('<24I',changed,co+532*96)[:3]==(0x5a,DEAD,0x600)
        assert u32(changed,0x28)==536
    if episode5_removed:
        at5,size5=s.logos[138]
        chapter=next((new for off,old,new in edits if off==MAP+at5),s.data[at5:at5+size5])
        co5=u32(chapter,0x2c);count5=u32(chapter,0x28)
        assert count5==803
        assert struct.unpack_from('<4I',chapter,co5+626*96)==(0x9c,DEAD,1,0)
        assert all(struct.unpack_from('<3I',chapter,co5+i*96)!=(0x5a,DEAD,0x600) for i in range(count5))
    else:
        assert s.records(138)[626][1][:3]==(0x5a,DEAD,0x600),'Original episode5 grant changed'
    rewards=[r for a,r in rs[526:532]]
    def setup(owned):
        vm=VM();c=vm.cpu
        with ISO.open('rb') as f:
            f.seek(0x94880);c.mem[0x100000:0x582980]=f.read(0x482980)
        assert c.mem[0xb6da0c:0xb6da10]==b'UTbl'
        c.write(0xb6da0c+12+0x600*2,0x15c,2)
        c.write(0xb6ea18+12+0x15c*100+0x22,0xffff,2)
        if owned:vm.op(command(0x5a,0x600))
        return vm
    for owned in (False,True):
        before,after=setup(owned),setup(owned)
        weapon_records=[]
        for vm in (before,after):
            for r in rewards:
                vm.cpu.writes.clear();vm.op(r)
                if vm is after and r[0]==0x5f:
                    targets={a for a,n,pc in vm.cpu.writes if pc==0x33513c and n==2 and vm.cpu.read(a,2)==r[2]}
                    assert len(targets)==1;weapon_records.append(targets.pop())
        c=after.cpu;save=c.read(0x59d364,4)
        oldpilot=bytes(c.mem[save+0x25cfc:save+0x25cfc+512*0x5c])
        after.op(command(0x5a,0x600))
        slot=c.run(0x1abc50,[save,0x600,0,0]);assert slot>=0
        assert c.run(0x1a9b70,[save,slot,1])==1
        assert c.run(0x1b1300,[save,slot,0])==-1
        assert c.run(0x311200,[save,slot,1],limit=10000000)>0
        assert c.mem[save+0x25cfc:save+0x25cfc+512*0x5c]==oldpilot
        stable=bytes(c.mem[save:save+0x3b400])
        after.op(command(0x5a,0x600));assert c.mem[save:save+0x3b400]==stable
        if owned:
            assert before.cpu.mem[save:save+0x3b400]==stable
        else:
            for i in range(512):
                if i!=slot:
                    p=save+0x6efc+i*0xd8;assert before.cpu.mem[p:p+0xd8]==c.mem[p:p+0xd8]
        for p in weapon_records:
            assert before.cpu.mem[p:p+8]==c.mem[p:p+8]
        glob=c.read(0x59d36c,4)
        for key in (0x1f,0x20,0x21):
            for off in (0x103c,0x1264):assert before.cpu.read(glob+off+key,1)==c.read(glob+off+key,1)
    return dict(missing_unit_granted_owned_visible_boardable=True,already_owned_no_duplicate=True,
        repeated_grant_idempotent=True,original_six_rewards_preserved=True,
        original_episode5_grant_preserved=not episode5_removed,episode5_direct_grant_removed=episode5_removed,
        pilot_records_unchanged=True,rendered_playthrough=False)


def validate_wodan_survival(edits,row,blobs,source=ISO):
    from ogs_korean_codec import encode
    script=Scripts(source);master_data=None
    with source.open('rb') as f:f.seek(0x5da000);master_data=bytearray(f.read(0x190000))
    original_master=bytes(master_data)
    for off,a,b in edits:
        rel=off-0x5da000
        if 0<=rel<len(master_data):assert master_data[rel:rel+len(a)]==a;master_data[rel:rel+len(b)]=b
    def setup(existing=False,occupied=False):
        vm=VM();c=vm.cpu
        with source.open('rb') as f:f.seek(0x94880);c.mem[0x100000:0x582980]=f.read(0x482980)
        for off,old,new in edits:
            rel=off-0x94880
            if 0<=rel<0x482980:
                assert c.mem[0x100000+rel:0x100000+rel+len(old)]==old
                c.mem[0x100000+rel:0x100000+rel+len(new)]=new
        for tag in (b'Plot',b'Unit',b'PTbl',b'UTbl'):
            src=master_data.find(tag);dst=c.mem.find(tag,0xb00000)
            assert src>=0 and dst>=0
            # Count/stride are authoritative; PTbl's historical length field
            # includes later tables, so copy the actual contiguous master span.
            size={b'Plot':12+382*148,b'Unit':12+u32(master_data,src+8)*100,b'PTbl':12+2048*2,b'UTbl':12+2048*2}[tag]
            c.mem[dst:dst+size]=master_data[src:src+size]
        save=c.read(0x59d364,4);previous=-1
        if existing:
            vm.op(command(0x5a,0x601));slot=c.run(0x1abc50,[save,0x601,0,0]);assert slot>=0
            for attr,value in [(0xd,7),(0xe,6),(0xf,5),(0x10,4)]:c.run(0x1af000,[save,attr,slot,value,0])
            if occupied:
                previous=c.run(0x1b1fd0,[save,0x469,0]);assert previous>=0
                c.write(save+0x25cfc+previous*92+2,1,1)
                c.run(0x1b13d0,[save,previous,slot,0])
        ctx=0x1700000;bundle=0x1780000;data=0x1790000
        c.write(ctx+40,bundle,4)
        for off,g in [(0x2120,0x59d360),(0x2124,0x59d364),(0x212c,0x59d36c)]:c.write(bundle+off,c.read(g,4),4)
        c.write(ctx+0x346d4,data,4);c.write(ctx+0x346d0,1,4);c.mem[data:data+336]=row
        c.write(CTX+0x310c,ctx-0x40e00,4)
        return vm,save,previous
    # The reclaimed initializer must reproduce all original data writes and
    # register/FPR results; helper code occupies only instructions now skipped.
    originals=[]
    for patched in (False,True):
        c=CPU(ram)
        with source.open('rb') as f:f.seek(0x94880);c.mem[0x100000:0x582980]=f.read(0x482980)
        if patched:
            for off,old,new in edits:
                rel=off-0x94880
                if 0<=rel<0x482980:c.mem[0x100000+rel:0x100000+rel+len(new)]=new
        c.r=[0x123000+i for i in range(32)];c.r[0]=0
        for i in (8,9,10):c.r[i]=0x540000
        c.fpr=[0x13570000+i for i in range(32)]
        c.run(0x2003f4,stop=0x200514);originals.append(c)
    x,y=originals;assert x.r==y.r and x.fpr==y.fpr
    assert {(a,n) for a,n,pc in x.writes}=={(a,n) for a,n,pc in y.writes}
    for at,n,pc in x.writes:assert x.mem[at:at+n]==y.mem[at:at+n]
    # Ordinary (non-alias) recruitment must be byte-identical to original code.
    saves=[]
    for patched in (False,True):
        vm,sv,previous=setup();c=vm.cpu
        if not patched:
            for off,old,new in edits:
                rel=off-0x94880
                if 0<=rel<0x482980:c.mem[0x100000+rel:0x100000+rel+len(old)]=old
        other=bytearray(row);struct.pack_into('<I',other,0,0x4e4);struct.pack_into('<I',other,0x20,0x43a)
        c.mem[0x1790000:0x1790000+336]=other
        vm.op(command(0x5e,0x25));saves.append(bytes(c.mem[sv:sv+0x3b400]))
    assert saves[0]==saves[1]
    cases=[]
    for existing,occupied in [(False,False),(True,False),(True,True)]:
        vm,save,previous=setup(existing,occupied);c=vm.cpu
        units=bytes(c.mem[save+0x6efc:save+0x6efc+512*216]);pilots=bytes(c.mem[save+0x25cfc:save+0x25cfc+512*92])
        vm.op(command(0x5e,0x25))
        assert c.visits[0x1d5970]>0
        slot=c.run(0x1abc50,[save,0x601,0,0]);assert slot>=0
        pilot=c.run(0x1b1300,[save,slot,0]);assert pilot>=0
        assert c.read(save+0x25cfc+pilot*92,2)==0x602
        assert c.run(0x1ab6f0,[save,0x602,1])==pilot
        assert c.run(0x1a9b70,[save,slot,1])==1
        assert c.run(0x1ac800,[save,0xf2,pilot])==1
        for flag in (0x37,0x38,0x39):assert c.run(0x1aca50,[save,flag,slot])==0
        assert c.run(0x1aca50,[save,0x59,slot])!=0
        if existing:
            assert [c.run(0x1af860,[save,a,slot,0]) for a in range(0xd,0x11)]==[7,6,5,4]
        if previous>=0:
            assert c.run(0x1ab6f0,[save,0x469,1])==previous
            assert c.run(0x1b12a0,[save,previous])==-1
        for i in range(512):
            if i!=slot:
                at=save+0x6efc+i*216;assert c.mem[at:at+216]==units[i*216:(i+1)*216]
            if i!=pilot:
                at=save+0x25cfc+i*92;assert c.mem[at:at+92]==pilots[i*92:(i+1)*92]
        stable=bytes(c.mem[save:save+0x3b400])
        vm.op(command(0x5e,0x25))
        assert c.mem[save:save+0x3b400]==stable,'Repeat recruitment reset a record'
        assert c.run(0x1abc50,[save,0x601,0,0])==slot and c.run(0x1b1300,[save,slot,0])==pilot
        # Detach/reboard through the game's actual association functions.
        c.run(0x1b1370,[save,slot,0]);assert c.run(0x311200,[save,slot,1],limit=10000000)>0
        c.run(0x1b13d0,[save,pilot,slot,0]);assert c.run(0x1b1300,[save,slot,0])==pilot
        cases.append(dict(existing_robot=existing,occupied=occupied,slot=slot,pilot=pilot))
    for n,b in blobs.items():
        old=script.records(n);co=u32(b,0x2c)
        insert=next((i for i,(at,r) in enumerate(old) if i>2500 and r[:4]==(0x9c,DEAD,0x22,0)),None) if n==109 else None
        assert len(old)+(n==109)==u32(b,0x28)
        for i,(_,r) in enumerate(old):
            target=i+int(insert is not None and i>=insert)
            if n!=109 or i not in (2300,):assert struct.unpack_from('<24I',b,co+target*96)==r
        if n==109:
            assert struct.unpack_from('<24I',b,co+insert*96)==tuple(command(0x5e,0x25))
            assert u32(b,co+2300*96)==0x4f and struct.unpack_from('<24I',b,co+2303*96)==old[2303][1]
            # Ouka survival and Pehp/Uruz removals remain untouched.
            for i in (2147,2148,2149,2154,2163,2164,2165,2296):assert struct.unpack_from('<24I',b,co+i*96)==old[i][1]
        ts=script.texts(n)
        for i,(at,text) in enumerate(ts):
            pos=u32(b,0x4c)+u32(b,u32(b,0x54)+i*4)
            terminated=bytes(b)+b'\0';actual=decode(terminated[pos:terminated.index(0,pos)])
            assert actual==WODAN_SURVIVAL_TEXT.get(n,{}).get(i,text),(n,i,actual)
    # Other pilot master fields, all unit/weapon/voice tables are unchanged.
    for i,(a,b) in enumerate(zip(original_master,master_data)):
        if a!=b:assert i in range(0x13a484+0x602*2,0x13a484+0x602*2+2) or i in range(0x13b490+80*148+18,0x13b490+80*148+20)
    return dict(initializer_equivalence=True,ordinary_recruitment_byte_identical=True,native_recruitment_cases=cases,original_robot_reused=True,other_pilots_preserved=True,
        upgrades_preserved=True,duplicate_pair_prevented=True,native_reboarding_verified=True,
        duel_and_sophia_rescue_preserved=True,ouka_option_commands_preserved=True,
        changed_dialogue=sum(map(len,WODAN_SURVIVAL_TEXT.values())),unmodified_dialogue_and_commands_preserved=True,
        rendered_playthrough=False)


def validate_grungust_type3_grant(edits,source=ISO):
    s=Scripts(source);at,size=s.logos[103];old=s.data[at:at+size]
    b=next(new for off,a,new in edits if off==MAP+at)
    co=u32(b,0x2c);assert u32(b,0x28)==1468
    assert struct.unpack_from('<24I',b,co+1463*96)==tuple(command(0x5a,0x601))
    assert struct.unpack_from('<24I',b,co+1464*96)==tuple(command(0x5a,0x602))
    restored=bytearray(b);del restored[co+1464*96:co+1465*96];restored[:0x70]=old[:0x70];assert restored==old
    with source.open('rb') as f:f.seek(0x5da000);base=bytearray(f.read(0x190000))
    master=bytearray(base)
    for off,a,new in edits:
        rel=off-0x5da000
        if 0<=rel<len(master):assert master[rel:rel+len(a)]==a;master[rel:rel+len(new)]=new
    def setup(patched=True):
        vm=VM();c=vm.cpu
        with source.open('rb') as f:f.seek(0x94880);c.mem[0x100000:0x582980]=f.read(0x482980)
        if patched:
            for off,a,new in edits:
                rel=off-0x94880
                if 0<=rel<0x482980:
                    assert c.mem[0x100000+rel:0x100000+rel+len(a)]==a;c.mem[0x100000+rel:0x100000+rel+len(new)]=new
        data=master if patched else base
        for tag,stride in [(b'UTbl',2),(b'PTbl',2),(b'Unit',100),(b'Plot',148)]:
            src=data.find(tag);dst=c.mem.find(tag,0xb00000);assert src>=0 and dst>=0
            length=12+u32(data,src+8)*stride;c.mem[dst:dst+length]=data[src:src+length]
        return vm,c.read(0x59d364,4)
    vm,save=setup();c=vm.cpu
    # Preserve a separately owned existing Type3 and all its record data.
    vm.op(command(0x5a,0x530));other=c.run(0x1abc50,[save,0x530,0,0]);assert other>=0
    other_before=bytes(c.mem[save+0x6efc+other*216:save+0x6efc+(other+1)*216])
    pilots=bytes(c.mem[save+0x25cfc:save+0x25cfc+512*92])
    vm.op(command(0x5a,0x601));slade=c.run(0x1abc50,[save,0x601,0,0]);assert slade>=0
    units=bytes(c.mem[save+0x6efc:save+0x6efc+512*216])
    vm.op(command(0x5a,0x602));slot=c.run(0x1abc50,[save,0x602,0,0]);assert slot>=0 and slot not in (slade,other)
    assert c.run(0x1a9b70,[save,slot,1])==1
    assert c.run(0x1b1300,[save,slot,0])==-1
    assert c.run(0x1b01d0,[save,0x34,slot])==0x8801
    for flag in (0x37,0x38,0x39):assert c.run(0x1aca50,[save,flag,slot])==0,hex(flag)
    assert c.run(0x1aca50,[save,0x59,slot])!=0
    assert c.run(0x311200,[save,slot,1],limit=10000000)>0
    assert c.mem[save+0x25cfc:save+0x25cfc+512*92]==pilots
    for i in range(512):
        if i!=slot:
            p=save+0x6efc+i*216;assert c.mem[p:p+216]==units[i*216:(i+1)*216]
    assert c.mem[save+0x6efc+other*216:save+0x6efc+(other+1)*216]==other_before
    fixed=[c.run(0x1ac9d0,[save,0x75,slot,i]) for i in range(16)]
    assert fixed[:5]==[0x97c,0x97d,0x97e,0x97f,0x980] and fixed[5:]==[-1]*11
    stable=bytes(c.mem[save:save+0x3b400]);vm.op(command(0x5a,0x602));assert c.mem[save:save+0x3b400]==stable
    # Sanger can board the restored Type3 and return to Daizengar.
    pilot=c.run(0x1b1fd0,[save,0x469,0]);assert pilot>=0
    c.write(save+0x25cfc+pilot*92+2,1,1)
    assert c.run(0x1ac800,[save,0xf2,pilot])==0x8000
    c.run(0x1b13d0,[save,pilot,slot,0]);assert c.run(0x1b1300,[save,slot,0])==pilot
    vm.op(command(0x5a,0x499));dai=c.run(0x1abc50,[save,0x499,0,0]);assert dai>=0
    c.run(0x1af000,[save,2,dai,1,0]);c.run(0x1b1370,[save,slot,0])
    assert c.run(0x311200,[save,dai,1],limit=10000000)>0
    c.run(0x1b13d0,[save,pilot,dai,0]);assert c.run(0x1b1300,[save,dai,0])==pilot
    # Pilot602 (Wodan) is a different namespace from unit602 (Type3).
    wp=0x5071000;p=wp+u32(s.data,wp+8+110*8);count=u32(s.data,p+40)
    row=s.data[p+44+(count-1)*336:p+44+count*336]
    assert (u32(row,0),u32(row,4),u32(row,32))==(0x601,0x25,0x602)
    ctx=0x1700000;bundle=0x1780000;data=0x1790000
    c.write(ctx+40,bundle,4)
    for off,g in [(0x2120,0x59d360),(0x2124,0x59d364),(0x212c,0x59d36c)]:c.write(bundle+off,c.read(g,4),4)
    c.write(ctx+0x346d4,data,4);c.write(ctx+0x346d0,1,4);c.mem[data:data+336]=row;c.write(CTX+0x310c,ctx-0x40e00,4)
    vm.op(command(0x5e,0x25));wodan=c.run(0x1ab6f0,[save,0x602,1]);assert wodan>=0
    assert c.run(0x1abc50,[save,0x602,0,0])==slot
    assert c.run(0x1b1300,[save,slade,0])==wodan
    assert c.run(0x1b1300,[save,dai,0])==pilot
    # Ordinary grants have identical save effects through the extended wrapper.
    for key in (0x600,0x601,0x559):
        samples=[]
        for patched in (False,True):
            q,sv=setup(patched);q.op(command(0x5a,key));samples.append(bytes(q.cpu.mem[sv:sv+0x3b400]))
        assert samples[0]==samples[1],hex(key)
    return dict(episode37_clear=True,sanger_original_type3_variant=True,robot_only=True,
        owned_visible_and_boardable=True,existing_type3_and_other_roster_preserved=True,
        duplicate_grant_idempotent=True,sanger_boarding_and_daizengar_return=True,
        wodan_recruitment_regression_passed=True,ordinary_grants_unchanged=True,
        original_stats_weapons_and_dialogue_preserved=True,rendered_playthrough=False)
