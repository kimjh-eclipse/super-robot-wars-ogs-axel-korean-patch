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
    for j,v in enumerate(command(0x5E,0x24)):c.write(REC+j*4,v,4)
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
if __name__=='__main__':main()
