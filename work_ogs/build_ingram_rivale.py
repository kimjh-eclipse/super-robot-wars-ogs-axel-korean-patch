"""OG2 episode-11 parallel-world Ingram recruitment; guarded native resources."""
from pathlib import Path
import argparse,hashlib,json,os,struct
from build_hidden_rewards import Scripts,MAP,command
from build_beowulf_prototype import Archive,Plan,read,u16,u32,rebuild_beowulf_story_logo
from ogs_korean_codec import encode,decode

ROOT=Path(__file__).resolve().parent
UNIT,PILOT,GROUP=0x605,0x604,0x25
SCRIPT,UNIT_TABLE=79,83
JOURNAL=ROOT/'runtime/ingram_rivale_manifest.json'
EXPECTED={'SRWOGS_K.iso':'77b745a8082cede805fe39d38c02cecd859ed69d4765ca9ef76f51065411f7af',
 'SRWOGS_BEOWULF_TEST.iso':'50a7122b2bfb2b01d67a95f8843f59e58fd8b2e3691bdebc4f6db577d98a3fb0'}

def scenes():
    I,R,A,V,M,D,L,K= PILOT,0x4ab,0x41a,0x429,0x424,0x46c,0x49f,0x446
    return [
      (453,'차원의 표류자',[
       (R,'류세이：뭐야！？ 기지 위의 공간이……！'),
       (A,'아야：공간 자체가 갈라지고 있어요！'),
       ('command',command(0xc5,GROUP,0xffffffff)),
       (V,'비렛타：저 기체는……Ｒ－ＧＵＮ 리바레！？'),
       (R,'류세이：리바레라면……설마、잉그램！？'),
       (I,'잉그램：……통신이 살아 있군。 류세이、아야。'),
       (A,'아야：소령님……？ 어떻게 여기에……。'),
       (V,'비렛타：그 이름을 쓰기 전에 대답해。 너는 누구지？'),
       (I,'잉그램：잉그램 프리스켄。 다만、너희가 아는 나는 아니다。'),
       (M,'이름：다른 세계에서 왔다는 건가？'),
       (I,'잉그램：설명은 뒤에 하겠다。 지금은 적의 공격부터 막아야 한다。'),
       (R,'류세이：그 말을、우리가 믿을 것 같아！？'),
       (I,'잉그램：믿으라고 강요하지 않겠다。 내 총구가 어디를 향하는지 지켜봐라。'),
       (V,'비렛타：……기지 방어에 협력해。 우리에게 총을 돌리면 즉시 격추한다。'),
       (I,'잉그램：이해했다。 이번에는、너희와 함께 싸우겠다。')]),
      (1043,'다른 결말을 선택한 잉그램',[
       (D,'다이테츠：전투 협력에는 감사하네。 이제 자네의 사정을 듣도록 하지。'),
       (I,'잉그램：내가 있던 세계에서도、지구는 에어로게이터의 침공을 받았다。'),
       (I,'잉그램：하지만 나는 너희가 아는 잉그램보다 일찍 기억을 되찾았다。'),
       (V,'비렛타：주박에서 벗어난 뒤、어떤 선택을 했지？'),
       (I,'잉그램：모든 것을 밝히고 하가네와 히류개에 남았다。 너희와 끝까지 싸우는 길을 택했지。'),
       (A,'아야：그럼、그 세계의 저희와는……。'),
       (I,'잉그램：동료였다。 류세이도、아야도……。'),
       (R,'류세이：……그렇다면、왜 이 세계로 온 거야？'),
       (I,'잉그램：마지막 결전에서 중추의 전이 장치를 끊었다。 적의 증원이 차원을 넘어오는 것을 막기 위해서였다。'),
       (I,'잉그램：리바레로 전이장을 억제했지만、붕괴하는 공간에 휘말렸다。 다음 순간、이 기지 상공에 있었다。'),
       (L,'라이：우연한 표류라기엔 판단할 자료가 부족합니다。'),
       (V,'비렛타：기록과 기체를 조사하겠어。 기억을 찾았다는 말만으로 신뢰할 수는 없어。'),
       (I,'잉그램：당연하다。 조사와 감시 모두 따르겠다。'),
       (D,'다이테츠：이 세계는 지금도 전란의 한가운데일세。 자네는 어떻게 할 생각인가？'),
       (I,'잉그램：돌아갈 길은 찾겠다。 하지만、그 전에……。'),
       (I,'잉그램：내가 지키겠다고 약속한 이들과 같은 얼굴을、다시 잃고 싶지는 않다。'),
       (R,'류세이：……당장 예전처럼 부를 수는 없어。 그래도、오늘 지켜 준 건 사실이야。'),
       (A,'아야：이 세계에서의 당신은、앞으로의 행동으로 보여 주세요。'),
       (I,'잉그램：알겠다。 이번에야말로、마지막까지 함께 싸우겠다。'),
       (D,'다이테츠：그럼 비렛타의 감독 아래 동행을 허가하겠네。 리바레도 본함의 전력으로 편입하지。'),
       (V,'비렛타：혼자서 모든 것을 짊어지려 하지 마。 지금부터는、명령을 지켜。'),
       (I,'잉그램：알겠다、비렛타。')])]


def story_scenes():
    return scenes()


def master_patch(old):
    h=0x11e800;fields=list(range(0x18,0x8c,4));starts=[h+u32(old,h+k) for k in fields];end=h+u32(old,0x11e00c)
    tables={k:bytearray(old[p:(starts[i+1] if i+1<len(starts) else end)]) for i,(k,p) in enumerate(zip(fields,starts))}
    uc,pc=u32(tables[0x1c],8),u32(tables[0x2c],8)
    assert u16(tables[0x18],12+UNIT*2)==u16(tables[0x28],12+PILOT*2)==65535
    assert u16(tables[0x18],12+0x23*2)==40 and u16(tables[0x28],12+0x3e*2)==72
    body=bytearray(tables[0x1c][12+40*100:12+41*100]);pilot=tables[0x2c][12+72*148:12+73*148]
    assert u32(body,0)==160000 and u16(body,0x1a)==2200
    struct.pack_into('<I',body,0,8300);struct.pack_into('<H',body,0x1a,2100);struct.pack_into('<H',body,0x22,1)
    assert u16(pilot,0x12)==1
    for table,key,stride,record,idx in [(0x1c,UNIT,100,body,uc),(0x2c,PILOT,148,pilot,pc)]:
        assert len(tables[table])==12+u32(tables[table],8)*stride
        tables[table].extend(record);struct.pack_into('<II',tables[table],4,u32(tables[table],4)+stride,idx+1)
        lookup=0x18 if table==0x1c else 0x28
        struct.pack_into('<I',tables[lookup],4,u32(tables[lookup],4)+stride)
        struct.pack_into('<H',tables[lookup],12+key*2,idx)
    out=bytearray(old[:starts[0]])
    for k in fields:struct.pack_into('<I',out,h+k,len(out)-h);out.extend(tables[k])
    struct.pack_into('<I',out,0x11e00c,len(out)-h)
    assert len(out)<=len(old) and not any(old[end:len(out)]);out.extend(old[len(out):])
    for k,stride in [(0x1c,100),(0x2c,148),(0x24,36)]:
        before=starts[fields.index(k)];after=h+u32(out,h+k);n=u32(old,before+8)*stride
        assert out[after+12:after+12+n]==old[before+12:before+12+n]
    return bytes(out),dict(unit_record=uc,pilot_record=pc,HP=8300,armor=2100,original_weapons=[hex(x) for x in struct.unpack_from('<3H',body,0x24)])


def make_plan(path):
    s=Scripts(path);edits=[];details={};ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes()
    with path.open('rb') as f:
        for base in (0x5da000,0x83f000):
            old=read(f,base,0x1a5800);new,note=master_patch(old);edits.append((base,old,new));details[hex(base)]=note
        wp=0x5071000;dp=wp+8+UNIT_TABLE*8;at=wp+u32(s.data,dp);size=u32(s.data,dp+4);original=s.data[at:at+size]
        assert original[24:32].split(b'\0')[0]==b'01016' and u32(original,40)==43
        row=bytearray(original[44+3*336:44+4*336]);assert (u32(row),u32(row,32))==(0x426,0x4ab)
        assert not any(u32(original,44+i*336+4)==GROUP for i in range(43))
        occupied={(u32(original,44+i*336+16),u32(original,44+i*336+20)) for i in range(43)}
        xy=(28,9);assert xy not in occupied
        for o,v in [(0,UNIT),(4,GROUP),(8,0),(16,xy[0]),(20,xy[1]),(28,1),(32,PILOT)]:struct.pack_into('<I',row,o,v)
        for o in (0x60,0x74,0x88):struct.pack_into('<I',row,o,0xffff0000|PILOT)
        new=bytearray(original+row);struct.pack_into('<I',new,40,44)
        dest=0x8e20000;assert not any(read(f,MAP+dest,len(new)))
        edits.extend([(MAP+dest,bytes(len(new)),bytes(new)),(MAP+dp,read(f,MAP+dp,8),struct.pack('<II',dest-wp,len(new)))])
        oldat,size=s.logos[SCRIPT];old=s.data[oldat:oldat+size]
        new,notes=rebuild_beowulf_story_logo(old,story_scenes(),speaker_context=True)
        from validate_beowulf_prototype import validate_story_blob
        proof=validate_story_blob(old,new,notes,ram,allowed_commands=(tuple(command(0xc5,GROUP,0xffffffff)),))
        dest=0x8e30000;assert not any(read(f,MAP+dest,len(new)))
        edits.extend([(MAP+dest,bytes(len(new)),new),(MAP+0x557f800+8+SCRIPT*8,read(f,MAP+0x557f800+8+SCRIPT*8,8),struct.pack('<II',dest-0x557f800,len(new)))])
        for slot,base,end in [(13,0x5070000,0x8e20000+len(original)+336),(14,0x557e800,dest+len(new))]:
            off=MAP+0x800+8+slot*8+4;before=read(f,off,4);size=max(u32(before,0),end-base)
            if size!=u32(before,0):edits.append((off,before,struct.pack('<I',size)))
        voice=Archive(f,0x8574e800);original_voice=voice.get(f,0x3e);clone=bytearray(original_voice);h=struct.unpack_from('<16H',clone)
        retagged=0
        for o in range(h[12],h[13],2):
            tag=u16(clone,o)
            if tag&0x7ff==0x3e:struct.pack_into('<H',clone,o,(tag&0xf800)|PILOT);retagged+=1
        assert retagged>0 and clone[:h[12]]==original_voice[:h[12]] and clone[h[13]:]==original_voice[h[13]:]
        p=Plan(f);p.cursor=0x87300000
        span=p.archive(voice,[(PILOT,bytes(clone),'Original Ingram voice/selector clone')])
        p.add(0x25120000+8+5*8+4,struct.pack('<I',span),'Speech root span')
        edits.extend((o,a,b) for o,a,b,label in p.edits)
    edits.sort()
    for a,b in zip(edits,edits[1:]):assert a[0]+len(a[1])<=b[0]
    return edits,dict(masters=details,script=SCRIPT,unit_table=UNIT_TABLE,position=xy,group=GROUP,
        story=notes,story_validation=proof,voice_rows_retagged=retagged,original_OG1_records_preserved=True),bytes(row)


def validate_spawn(path,edits,row):
    from r5900_scalar_check import CPU
    ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes();c=CPU(ram)
    with path.open('rb') as f:c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
    master=u32(ram,0x59d360);blob=next(b for o,a,b in edits if o==0x5da000);h=0x11e800;dest=0x1100000
    c.mem[dest:dest+len(blob[h:])]=blob[h:]
    for i,field in enumerate(range(0x18,0x8c,4)):
        at=dest+u32(blob,h+field)
        for off,v in [(0,at),(4,c.read(at,4)),(8,c.read(at+4,4)),(12,c.read(at+8,4)),(16,at),(20,at+12)]:c.write(master+0x28+i*24+off,v,4)
    assert c.run(0x1a7d40,[master,UNIT])==8300
    bank=c.run(0x1a6690,[master,UNIT]);face=c.run(0x1a2900,[master,PILOT]);assert face==31
    assert c.run(0x1a6690,[master,0x23])==bank
    ctx,src=0x1600000,0x1700000;c.write(ctx+0x28,0x59b240,4);c.write(ctx+0x346d4,src,4);c.mem[src:src+336]=row
    diff=c.read(0x59d36c,4);c.write(diff+0xf60,0,4);c.write(diff+0xf68,1,4)
    assert c.run(0x1d5970,[ctx,0])==1
    save=c.read(0x59d364,4);slot=c.run(0x1abc50,[save,UNIT,0,0]);pilot=c.run(0x1ab6f0,[save,PILOT,1]);assert slot>=0 and pilot>=0
    owned=c.run(0x1a9b70,[save,slot,1]);occupant=c.run(0x1b1300,[save,slot,0])
    assert owned==1 and occupant==pilot,(owned,occupant,pilot)
    assert c.run(0x1b01d0,[save,0x14,slot,0])==8300
    assert c.run(0x1b01d0,[save,0x34,slot,0])&c.run(0x1afbd0,[save,0x21,pilot,0])
    with path.open('rb') as f:
        for archive,key in [(0x1a2f3000,face*32),(0x1b12d800,face*10)]:
            image=Archive(f,archive).get(f,key);assert len(image)>1024 and any(image[1024:])
        c.mem[0x93b900:0x93b900+43200]=read(f,0x859f9000,43200)
        a=Archive(f,0x85a04000);at,n=a.entries[0];metadata=read(f,at,n);c.mem[0x946200:0x946200+n]=metadata
        obj=0x1800000;c.run(0x290e10,[obj]);animations=[]
        for key in (0x60,0x61,0x62):
            motion=c.run(0x1a4a20,[master,key]);asset=c.run(0x290c90,[obj,bank,motion]);assert asset>=0
            image=Archive(f,0x2970d000).get(f,asset);assert len(image)>64
            animations.append(dict(weapon_key=hex(key),motion=motion,animation_asset=asset))
    return dict(native_spawn_passed=True,owned=True,pilot_assigned=True,unit_slot=slot,pilot_slot=pilot,bank=bank,face=face,
        native_HP_and_boarding_verified=True,original_portrait_resources_verified=True,animations=animations,live_playthrough_verified=False)


def repair_loading(apply=False):
    """Repair main-relative event targets; keep recruitment and hangar text."""
    from r5900_scalar_check import CPU
    from validate_beowulf_prototype import validate_story_blob
    import psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'))
    expected={'SRWOGS_K.iso':'580ba4bae68332f9bee66bc480b03cf0b23179e977f259c669897afeccc804bb',
        'SRWOGS_BEOWULF_TEST.iso':'bfd1a6a7bc4937132b1a7d9644973fb7e7ced475fe3569df0932fb6e2e90afd5'}
    report=dict(applied=False,cause='Event descriptors are main-relative, not prefix/main combined',files=[])
    ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes()
    for item in journal['files']:
        path=Path(item['path']);s=Scripts(path);at,n=s.logos[SCRIPT];current=s.data[at:at+n]
        directory=MAP+0x557f800+8+SCRIPT*8
        original_entry=next(e for e in item['edits'] if e['offset']==directory)
        off,size=struct.unpack('<II',bytes.fromhex(original_entry['before']))
        old=s.data[0x557f800+off:0x557f800+off+size]
        rebuilt,notes=rebuild_beowulf_story_logo(old,story_scenes(),speaker_context=True)
        proof=validate_story_blob(old,rebuilt,notes,ram,allowed_commands=(tuple(command(0xc5,GROUP,0xffffffff)),))
        fixed=bytearray(current);edits=[];desc=u32(current,0x34)
        assert u32(current,0x30)==u32(old,0x30)
        c=CPU(ram);ctx,base=0x1600000,0x1800000
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==expected[path.name]
            c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
        prefix=u32(old,0x20);bad=0;checks=0
        for i in range(u32(old,0x30)):
            pos=desc+i*16;source=u32(old,0x34)+i*16
            kind,target=u32(old,source),u32(old,source+8)
            wanted=u32(rebuilt,u32(rebuilt,0x34)+i*16+8)
            assert current[pos:pos+8]==old[source:source+8] and current[pos+12:pos+16]==old[source+12:source+16]
            if u32(current,pos+8)!=wanted:
                edits.append(dict(offset=MAP+at+pos+8,before=current[pos+8:pos+12].hex(),after=struct.pack('<I',wanted).hex()))
                struct.pack_into('<I',fixed,pos+8,wanted)
            if kind:
                assert target<u32(old,0x28)
                mapped=target+sum(v for k,v in notes['insert_counts'].items() if int(k)<=target)
                assert wanted==mapped
                oldop=u32(old,u32(old,0x2c)+target*96)
                if u32(current,u32(current,0x2c)+u32(current,pos+8)*96)!=oldop:bad+=1
                assert u32(fixed,u32(fixed,0x2c)+wanted*96)==oldop
                # Execute the game's actual descriptor-to-command calculation.
                c.mem[base:base+len(fixed)]=fixed;c.write(ctx+0x6248,base,4)
                c.r[2]=base+desc;c.r[3]=i;c.r[20]=ctx
                got=c.run(0x2b5920,stop=0x2b5944)
                assert got==prefix+mapped,(i,got,prefix+mapped)
                checks+=1
        assert edits and bad>0
        # Only descriptor words change: all dialogue, history and spawn commands survive.
        assert len(fixed)==len(current)
        report['files'].append(dict(path=str(path),before_sha256=expected[path.name],edits=edits,
            wrong_opcode_targets_before=bad,native_event_target_checks=checks,rebuild_validation=proof,
            all_other_bytes_preserved=True,live_playthrough_verified=False))
        print(path.name,'event target repair prepared:',len(edits),'words;',bad,'wrong opcode targets',flush=True)
    journal['loading_fix']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for item in report['files']:
            path=Path(item['path'])
            with path.open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],4)==a;f.seek(e['offset']);f.write(b)
                f.flush();os.fsync(f.fileno())
            inverse,target,pos=hashlib.sha256(),hashlib.sha256(),0
            with path.open('rb') as f:
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(4)==b
                    inverse.update(a);target.update(b);pos+=4
                while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
            assert inverse.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
            print(path.name,'applied',item['after_sha256'],flush=True)
        report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


def balance_master(old):
    """Dedicated ally weapons, knife upgrade tiers, allied pilot/body changes."""
    h=0x11e800;fields=list(range(0x18,0x8c,4));starts=[h+u32(old,h+k) for k in fields];end=h+u32(old,0x11e00c)
    tables={k:bytearray(old[p:(starts[i+1] if i+1<len(starts) else end)]) for i,(k,p) in enumerate(zip(fields,starts))}
    ui,pi=u16(tables[0x18],12+UNIT*2),u16(tables[0x28],12+PILOT*2)
    assert ui in (428,429) and pi==382
    body=12+ui*100;pilot=12+pi*148;keys=(0xf90,0xf91,0xf92)
    assert struct.unpack_from('<3H',tables[0x1c],body+0x24)==(0x60,0x61,0x62)
    assert all(u16(tables[0x20],12+k*2)==65535 for k in keys)
    wc=u32(tables[0x24],8);knife=52;reference=tables[0x24][12+knife*36:12+(knife+1)*36]
    assert reference[3]&63==0
    powers=[];weapons=[]
    for j,(source,key) in enumerate(zip((0x60,0x61,0x62),keys)):
        wi=u16(tables[0x20],12+source*2);original=bytes(tables[0x24][12+wi*36:12+(wi+1)*36]);r=bytearray(original)
        power=u16(r,8);assert power in (2900,3100,3900)
        struct.pack_into('<H',r,8,power+1000);r[3]=(r[3]&0xc0)|(reference[3]&63)
        if source==0x61:r[0x19]=15
        if source==0x62:r[3]=(r[3]&0xf8)|1
        assert {x for x in range(36) if r[x]!=original[x]} <= ({3,8,9,0x19} if source==0x61 else {3,8,9})
        tables[0x24].extend(r);struct.pack_into('<H',tables[0x20],12+key*2,wc+j)
        powers.append(power+1000);weapons.append(dict(source_key=source,ally_key=key,before_power=power,power=power+1000,ammo=r[0x19],upgrade_tiers=r[3]&63))
    struct.pack_into('<II',tables[0x24],4,u32(tables[0x24],4)+108,wc+3)
    # WTbl stores its own lookup size (unlike UTbl/PTbl mirror headers).
    assert u32(tables[0x20],4)==len(tables[0x20])==12+4096*2
    struct.pack_into('<3H',tables[0x1c],body+0x24,*keys)
    mobility=tables[0x1c][body+0x53];tables[0x1c][body+0x53]=120
    stats=list(tables[0x2c][pilot+0x65:pilot+0x67]);assert all(x<=245 for x in stats)
    tables[0x2c][pilot+0x65:pilot+0x67]=bytes(x+10 for x in stats)
    for off,before,after in ((0x71,21,6),(0x77,30,15),(0x7d,30,16)):
        assert tables[0x2c][pilot+off]==before;tables[0x2c][pilot+off]=after
    out=bytearray(old[:starts[0]])
    for k in fields:struct.pack_into('<I',out,h+k,len(out)-h);out.extend(tables[k])
    struct.pack_into('<I',out,0x11e00c,len(out)-h)
    assert len(out)<=len(old) and not any(old[end:len(out)]);out.extend(old[len(out):])
    # Every pre-existing master record survives, except the new allied body/pilot.
    for k,stride,allowed in [(0x1c,100,{ui}),(0x24,36,set()),(0x2c,148,{pi})]:
        a=starts[fields.index(k)];b=h+u32(out,h+k)
        for i in range(u32(old,a+8)):
            if i not in allowed:assert old[a+12+i*stride:a+12+(i+1)*stride]==out[b+12+i*stride:b+12+(i+1)*stride]
    return bytes(out),dict(weapons=weapons,mobility_before=mobility,mobility=120,
        pilot_before=stats,pilot_after=[x+10 for x in stats],knife_record=knife,original_boss_and_all_other_records_preserved=True)


def balance_fix(apply=False):
    import psutil
    from r5900_scalar_check import CPU
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['loading_fix'];assert previous['applied']
    assert not journal.get('balance_fix',{}).get('applied'),'Already applied'
    report=dict(applied=False,files=[])
    ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes()
    for item in previous['files']:
        path=Path(item['path']);edits=[];notes=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            for base in (0x5da000,0x83f000):
                old=read(f,base,0x1a5800);new,note=balance_master(old)
                c=CPU(ram);c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
                master=u32(ram,0x59d360);h=0x11e800;dest=0x1100000;c.mem[dest:dest+len(new[h:])]=new[h:]
                for i,field in enumerate(range(0x18,0x8c,4)):
                    at=dest+u32(new,h+field)
                    for off,v in [(0,at),(4,c.read(at,4)),(8,c.read(at+4,4)),(12,c.read(at+8,4)),(16,at),(20,at+12)]:c.write(master+0x28+i*24+off,v,4)
                assert c.run(0x1a7bc0,[master,UNIT])==120
                for fn,x in zip((0x1a3ef0,0x1a3e70),note['pilot_after']):assert c.run(fn,[master,PILOT])==x
                for w in note['weapons']:
                    key=w['ally_key'];source=w['source_key']
                    assert c.run(0x1a5dc0,[master,key])==w['power']
                    assert c.run(0x1a5dc0,[master,source])==w['before_power']
                    assert c.run(0x1a5720,[master,key])==0 and c.run(0x1a57b0,[master,key])==(1 if source==0x62 else 0)
                    assert c.run(0x1a4a20,[master,key])==c.run(0x1a4a20,[master,source])
                assert c.run(0x1a5b40,[master,0xf91])==15
                assert c.run(0x1a7d40,[master,UNIT])==8300
                assert [c.run(fn,[master,PILOT,5]) for fn in (0x1a3680,0x1a35c0,0x1a3500)]==[6,15,16]
                note['native_getters_verified']=True;notes.append(note)
                edits.append(dict(offset=base,before=old.hex(),after=new.hex()))
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=edits,masters=notes))
        print(path.name,'balance plan/native checks passed',flush=True)
    journal['balance_fix']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for item in report['files']:
            path=Path(item['path']);inverse,target,pos=hashlib.sha256(),hashlib.sha256(),0
            with path.open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],len(a))==a;f.seek(e['offset']);f.write(b)
                f.flush();os.fsync(f.fileno());f.seek(0)
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b
                    inverse.update(a);target.update(b);pos+=len(b)
                while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
            assert inverse.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
            print(path.name,'applied',item['after_sha256'],flush=True)
        report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


def finisher_cost(apply=False):
    """Revise the existing balance journal; final weapon cost tier 0 -> 1."""
    import psutil
    from r5900_scalar_check import CPU
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));balance=journal['balance_fix'];assert balance['applied']
    assert not balance.get('finisher_cost_tier')
    plans=[];ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes()
    for item in balance['files']:
        path=Path(item['path']);edits=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            for e in item['edits']:
                old=bytes.fromhex(e['after']);assert read(f,e['offset'],len(old))==old
                new=bytearray(old);h=0x11e800;wt,w=[h+u32(new,h+k) for k in (0x20,0x24)]
                idx=u16(new,wt+12+0xf92*2);off=w+12+idx*36+3;assert new[off]&63==0;new[off]|=1
                c=CPU(ram);c.mem[0x100000:0x582980]=read(f,0x94880,0x482980);master=u32(ram,0x59d360);dest=0x1100000
                c.mem[dest:dest+len(new[h:])]=new[h:]
                for i,field in enumerate(range(0x18,0x8c,4)):
                    at=dest+u32(new,h+field)
                    for o,v in [(0,at),(4,c.read(at,4)),(8,c.read(at+4,4)),(12,c.read(at+8,4)),(16,at),(20,at+12)]:c.write(master+0x28+i*24+o,v,4)
                for key in (0xf90,0xf91,0xf92):
                    assert c.run(0x1a5720,[master,key])==0
                    assert c.run(0x1a57b0,[master,key])==(1 if key==0xf92 else 0)
                assert c.run(0x1a5dc0,[master,0xf92])==4900
                edits.append((e['offset']+off,old[off:off+1],bytes(new[off:off+1]),e,new))
        plans.append((item,edits))
    if not apply:
        print('Both ISOs: native tier checks passed, exactly two bytes per ISO');return
    for item,edits in plans:
        path=Path(item['path']);source=item['after_sha256'];inverse,target,pos=hashlib.sha256(),hashlib.sha256(),0
        with path.open('r+b') as f:
            for off,a,b,_,_ in edits:assert read(f,off,1)==a;f.seek(off);f.write(b)
            f.flush();os.fsync(f.fileno());f.seek(0)
            for off,a,b,_,_ in edits:
                while pos<off:
                    raw=f.read(min(4<<20,off-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                assert f.read(1)==b;inverse.update(a);target.update(b);pos+=1
            while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
        assert inverse.hexdigest()==source
        for _,_,_,e,new in edits:e['after']=new.hex()
        item['after_sha256']=target.hexdigest()
        for note in item['masters']:note['weapons'][2]['upgrade_tiers']=1
        print(path.name,item['after_sha256'],flush=True)
    balance['finisher_cost_tier']=1;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


def clear_bonus(apply=False):
    """Add five native inventory grants immediately before episode 11 advances."""
    import psutil
    from validate_beowulf_prototype import validate_story_blob
    from validate_hidden_rewards import VM,ram as inventory_ram,CTX
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));balance=journal['balance_fix'];assert balance['applied']
    assert not journal.get('clear_bonus',{}).get('applied'),'Already applied'
    grants=[command(0x5f,k,0) for k in (0xdac,0xdc2,0xdba)]+[command(0x5b,k,0) for k in (21,35)]
    report=dict(applied=False,chapter=11,items=['G 임팩트 스테이크','네오 차크람 슈터','스텔스 부메랑','고성능 레이더','메가 제너레이터'],each=1,files=[])
    native_ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes()
    for item in balance['files']:
        path=Path(item['path']);s=Scripts(path);at,n=s.logos[SCRIPT];old=s.data[at:at+n];rs=s.records(SCRIPT)
        insert=len(rs)-3;assert rs[insert][1][:4]==(0x9c,0xdeaddead,7,0)
        new,notes=rebuild_beowulf_story_logo(old,[(insert,'11화 클리어 추가 보상',[('command',r) for r in grants])])
        proof=validate_story_blob(old,new,notes,native_ram,allowed_commands=tuple(tuple(r) for r in grants))
        assert u32(new,0x28)==len(rs)+5
        assert struct.unpack_from('<24I',new,u32(new,0x2c)+(insert+5)*96)==rs[insert][1]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            assert not any(read(f,MAP+at+n,len(new)-n)),'No empty growth space'
            # Execute inventory handlers on a copied save with the current master.
            vm=VM();c=vm.cpu;c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
            blob=read(f,0x5da000,0x1a5800);h=0x11e800;master=u32(inventory_ram,0x59d360);dest=0x1100000
            c.mem[dest:dest+len(blob[h:])]=blob[h:]
            for i,field in enumerate(range(0x18,0x8c,4)):
                p=dest+u32(blob,h+field)
                for o,v in [(0,p),(4,c.read(p,4)),(8,c.read(p+4,4)),(12,c.read(p+8,4)),(16,p),(20,p+12)]:c.write(master+0x28+i*24+o,v,4)
            save,glob=u32(inventory_ram,0x59d364),u32(inventory_ram,0x59d36c);allocations=[]
            for repeat in range(2):
                for r in grants:
                    before=bytes(c.mem);c.writes.clear();vm.op(r)
                    if r[0]==0x5f:
                        slots={a for a,z,pc in c.writes if pc==0x33513c and z==2 and c.read(a,2)==r[2] and before[a:a+2]!=c.mem[a:a+2]}
                        assert len(slots)==1;slot=slots.pop()
                        assert save<=slot<save+0x40000 and slot not in allocations and before[slot:slot+2]==b'\0\0'
                        assert c.read(slot+3,1)&0x20;allocations.append(slot)
                    else:
                        for off in (0x103c,0x1264):
                            p=glob+off+r[2];assert c.read(p,1)==before[p]+1
            assert len(allocations)==6
            edits=[dict(offset=MAP+at,before=read(f,MAP+at,len(new)).hex(),after=new.hex()),
                dict(offset=MAP+0x557f800+12+SCRIPT*8,before=struct.pack('<I',n).hex(),after=struct.pack('<I',len(new)).hex())]
            root=MAP+0x800+8+14*8+4;span=read(f,root,4);needed=at+len(new)-0x557e800
            if needed>u32(span,0):edits.append(dict(offset=root,before=span.hex(),after=struct.pack('<I',needed).hex()))
        edits.sort(key=lambda x:x['offset'])
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=edits,insert_before_record=insert,
            checks=proof,native_inventory_verified=True,each_reward_adds_one_existing_items_preserved=True,stage_advance_preserved=True,live_playthrough_verified=False))
        print(path.name,'five clear grants/native inventory checks passed',flush=True)
    journal['clear_bonus']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for item in report['files']:
            inverse,target,pos=hashlib.sha256(),hashlib.sha256(),0
            with Path(item['path']).open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],len(a))==a;f.seek(e['offset']);f.write(b)
                f.flush();os.fsync(f.fileno());f.seek(0)
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inverse.update(a);target.update(b);pos+=len(b)
                while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
            assert inverse.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
            print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
        report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


def valcion_master(old):
    """Independent OG1 allied Valsion Custom refurbishment, never edit the enemy."""
    h=0x11e800;fields=list(range(0x18,0x8c,4));starts=[h+u32(old,h+k) for k in fields];end=h+u32(old,0x11e00c)
    ts={k:bytearray(old[p:(starts[i+1] if i+1<len(starts) else end)]) for i,(k,p) in enumerate(zip(fields,starts))}
    assert u16(ts[0x18],12+0x4e*2)==89 and u16(ts[0x18],12+0x606*2)==65535
    uc,wc=u32(ts[0x1c],8),u32(ts[0x24],8);body=bytearray(ts[0x1c][12+89*100:12+90*100])
    assert (u32(body,0),u16(body,0x18),u16(body,0x1a),body[0x53])==(8400,250,1800,85)
    struct.pack_into('<I',body,0,9000);struct.pack_into('<H',body,0x18,300);struct.pack_into('<H',body,0x1a,2100)
    body[0x53]=120;struct.pack_into('<H',body,0x22,65535)
    oldkeys=struct.unpack_from('<4H',body,0x24);assert oldkeys==(0x119,0x11a,0x11b,0x11c)
    keys=tuple(range(0xfa0,0xfa4));assert all(u16(ts[0x20],12+k*2)==65535 for k in keys)
    for i,(key,source) in enumerate(zip(keys,oldkeys)):
        idx=u16(ts[0x20],12+source*2);r=bytearray(ts[0x24][12+idx*36:12+(idx+1)*36]);struct.pack_into('<H',r,8,u16(r,8)+700)
        ts[0x24].extend(r);struct.pack_into('<H',ts[0x20],12+key*2,wc+i)
    struct.pack_into('<II',ts[0x24],4,u32(ts[0x24],4)+144,wc+4);struct.pack_into('<4H',body,0x24,*keys)
    st=ts[0x80];count,size=u32(st,8),u32(st,4);ptrs=struct.unpack_from('<%dI'%count,st,12);name=encode('발시온 개')+b'\0'
    new=bytearray(b'Strg'+struct.pack('<II',size+4+len(name),count+1));new.extend(struct.pack('<%dI'%(count+1),*[x+4 for x in ptrs],size+4))
    new.extend(st[12+count*4:size]);new.extend(name);new.extend(bytes((-len(new))%4));ts[0x80]=new
    struct.pack_into('<H',body,12,count);ts[0x1c].extend(body);struct.pack_into('<II',ts[0x1c],4,u32(ts[0x1c],4)+100,uc+1)
    struct.pack_into('<I',ts[0x18],4,u32(ts[0x18],4)+100);struct.pack_into('<H',ts[0x18],12+0x606*2,uc)
    out=bytearray(old[:starts[0]])
    for k in fields:struct.pack_into('<I',out,h+k,len(out)-h);out.extend(ts[k])
    struct.pack_into('<I',out,0x11e00c,len(out)-h);assert len(out)<=len(old) and not any(old[end:len(out)]);out.extend(old[len(out):])
    for k,stride in ((0x1c,100),(0x24,36),(0x2c,148)):
        a=starts[fields.index(k)];b=h+u32(out,h+k);n=u32(old,a+8)*stride;assert out[b+12:b+12+n]==old[a+12:a+12+n]
    return bytes(out)


def valcion_scene():
    return [(1160,'지난 전쟁의 기체를 다시 전력으로',[
        (0x4bc,'로버트：회수해 둔 발시온 개의 개수가 끝났습니다。'),
        (0x456,'켄조：지난 전쟁에서 사용한 그 기체인가？'),
        (0x4bc,'로버트：프레임은 살리고、동력로와 구동계를 교체했습니다。'),
        (0x456,'켄조：파일럿은 어떻게 할 생각이지？'),
        (0x4bc,'로버트：공통 조종계로 바꿨습니다。 제어 계통도 다시 점검했습니다。'),
        (0x456,'켄조：그렇다면 전력으로 편입하도록。 전투 기록은 계속 수집해라。'),
        (0x4bc,'로버트：알겠습니다。 발시온 개를 본함으로 보내겠습니다。')]),
        (1190,'발시온 개 지급',[('command',command(0x5a,0x606))])]


def valcion_custom(apply=False):
    import psutil
    from r5900_scalar_check import CPU
    from validate_beowulf_prototype import validate_story_blob
    from validate_hidden_rewards import VM,ram as vr
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['mobility_fix'];assert previous['applied']
    assert not journal.get('valcion_custom',{}).get('applied'),'Already applied'
    oldcode=struct.pack('<14I',0x8e280008,0x39080600,0x2d080003,0x11000002,0,0x24070001,0x0806bc00,0x0000402d,0,0,0,0,0,0)
    code=struct.pack('<14I',0x8e280008,0x39080606,0x11000006,0,0x8e280008,0x39080600,0x2d080003,0x11000002,0,0x24070001,0x0806bc00,0x0000402d,0,0)
    codeoff=0x94880+0x114f88-0x100000;report=dict(applied=False,chapter=30,unit_key=0x606,weapon_keys=list(range(0xfa0,0xfa4)),files=[])
    for item in previous['files']:
        path=Path(item['path']);s=Scripts(path);edits=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            assert read(f,codeoff,len(oldcode))==oldcode;edits.append(dict(offset=codeoff,before=oldcode.hex(),after=code.hex()))
            for base in (0x5da000,0x83f000):
                old=read(f,base,0x1a5800);new=valcion_master(old);edits.append(dict(offset=base,before=old.hex(),after=new.hex()))
            at,n=s.logos[96];old=s.data[at:at+n];assert len(s.records(96))==1193 and s.records(96)[1190][1][:4]==(0x9c,0xdeaddead,24,0)
            new,notes=rebuild_beowulf_story_logo(old,valcion_scene(),speaker_context=True)
            proof=validate_story_blob(old,new,notes,vr,allowed_commands=(tuple(command(0x5a,0x606)),))
            dest=0x9100000;assert not any(read(f,MAP+dest,len(new)))
            edits.extend([dict(offset=MAP+dest,before=bytes(len(new)).hex(),after=new.hex()),
                dict(offset=MAP+0x557f800+8+96*8,before=read(f,MAP+0x557f800+8+96*8,8).hex(),after=struct.pack('<II',dest-0x557f800,len(new)).hex())])
            root=MAP+0x800+8+14*8+4;a=read(f,root,4);edits.append(dict(offset=root,before=a.hex(),after=struct.pack('<I',max(u32(a,0),dest+len(new)-0x557e800)).hex()))
            vm=VM();c=vm.cpu;c.mem[0x100000:0x582980]=read(f,0x94880,0x482980);c.mem[0x114f88:0x114f88+len(code)]=code
            blob=bytes.fromhex(next(e['after'] for e in edits if e['offset']==0x5da000));h=0x11e800;master=u32(vr,0x59d360);p=0x1100000;c.mem[p:p+len(blob[h:])]=blob[h:]
            for i,field in enumerate(range(0x18,0x8c,4)):
                q=p+u32(blob,h+field)
                for o,v in [(0,q),(4,c.read(q,4)),(8,c.read(q+4,4)),(12,c.read(q+8,4)),(16,q),(20,q+12)]:c.write(master+0x28+i*24+o,v,4)
            for fn,want in [(0x1a7d40,9000),(0x1a7cc0,300),(0x1a7b40,2100),(0x1a7bc0,120),(0x1a7c40,6)]:assert c.run(fn,[master,0x606])==want
            for key,power,source in zip(range(0xfa0,0xfa4),(3900,5000,2700,3100),range(0x119,0x11d)):
                assert c.run(0x1a5dc0,[master,key])==power and c.run(0x1a4a20,[master,key])==c.run(0x1a4a20,[master,source])
            save=u32(vr,0x59d364);vm.op(command(0x5a,0x606));slot=c.run(0x1abc50,[save,0x606,0,0]);assert slot>=0 and c.run(0x1a9b70,[save,slot,1])==1
            assert c.run(0x1b1300,[save,slot,0])==-1 and c.run(0x1b01d0,[save,0x34,slot,0])==65535
            vm.op(command(0x5a,0x606));assert c.run(0x1abc50,[save,0x606,0,0])==slot
            for key in (0,0x4e,0x600,0x601,0x602,0x603,0x604,0x605,0x606):
                rec=0x1900000;c.write(rec+8,key,4);c.r[17]=rec;c.r[7]=31;c.run(0x114f88,stop=0x1af000)
                assert c.r[7]==(1 if key in (0x600,0x601,0x602,0x606) else 31)
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=sorted(edits,key=lambda e:e['offset']),story=notes,validation=proof,native_grant_and_duplicate_check=True,pilot_none=True,all_original_master_records_preserved=True))
        print(path.name,'Valcion refurbishment/native grant checks passed',flush=True)
    journal['valcion_custom']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for item in report['files']:
            inv,target,pos=hashlib.sha256(),hashlib.sha256(),0
            with Path(item['path']).open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],len(a))==a;f.seek(e['offset']);f.write(b)
                f.flush();os.fsync(f.fileno());f.seek(0)
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inv.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inv.update(a);target.update(b);pos+=len(b)
                while raw:=f.read(4<<20):inv.update(raw);target.update(raw)
            assert inv.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest();print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
        report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


LEGACY_UNITS=((0x607,140,'그룬가스트 영식'),(0x608,234,'휴케바인 009'),
              (0x609,232,'휴케바인 Mk-II 트롬베'),(0x60a,12,'F-28 멧서'),(0x60b,183,'지간스쿠드'))


def legacy_master(old):
    """Append OG1 player variants; keep every existing record intact."""
    h=0x11e800;fields=list(range(0x18,0x8c,4));starts=[h+u32(old,h+k) for k in fields];end=h+u32(old,0x11e00c)
    ts={k:bytearray(old[p:(starts[i+1] if i+1<len(starts) else end)]) for i,(k,p) in enumerate(zip(fields,starts))}
    count=u32(ts[0x1c],8)
    for i,(key,source,name) in enumerate(LEGACY_UNITS):
        assert u16(ts[0x18],12+key*2)==65535
        body=bytearray(ts[0x1c][12+source*100:12+(source+1)*100]);assert len(body)==100
        # These are pilot-free reserve machines. Preserve weapons, graphics,
        # stats and upgrade types; permit normal pilot boarding.
        if key==0x607:
            struct.pack_into('<H',body,0x22,65535);ts[0x1c].extend(body);index=count
        else:
            assert u16(body,0x22)==1;index=source
        struct.pack_into('<H',ts[0x18],12+key*2,index)
    amount=100
    struct.pack_into('<II',ts[0x1c],4,u32(ts[0x1c],4)+amount,count+1)
    struct.pack_into('<I',ts[0x18],4,u32(ts[0x18],4)+amount)
    out=bytearray(old[:starts[0]])
    for k in fields:struct.pack_into('<I',out,h+k,len(out)-h);out.extend(ts[k])
    struct.pack_into('<I',out,0x11e00c,len(out)-h);assert len(out)<=len(old) and not any(old[end:len(out)]);out.extend(old[len(out):])
    for k in fields:
        if k==0x18:continue
        a=starts[fields.index(k)];b=h+u32(out,h+k)
        if k==0x1c:assert out[b+12:b+12+count*100]==old[a+12:a+12+count*100]
        else:assert out[b:b+len(ts[k])]==old[a:a+len(ts[k])]
    return bytes(out)


def legacy_scenes(s):
    """Use the real ally entry groups on both route variants, not stage clear."""
    specs=[(77,1143,0xc5,0x13,0x60a),(82,571,0xc5,0x1e,0x60a),
           (89,56,0xc5,0x14,0x608),
           (90,466,0xc5,6,0x609),(91,361,0xc5,6,0x609),
           (103,936,0x6f,0x45e,0x607),
           (82,153,0xc5,0xa,0x60b),(86,135,0xc5,2,0x60b)]
    inserts={}
    for n,i,op,arg,key in specs:
        r=s.records(n)[i][1];assert r[0]==op and r[2]==arg,(n,i,r)
        inserts.setdefault(n,{}).setdefault(i+1,[]).append(command(0x5a,key))
    # The OG2 inventory grants for repair/resupply use distinct master keys.
    for n in range(65,138):
        for i,(_,r) in enumerate(s.records(n)):
            if r[0]==0x5f and r[2] in (0xde5,0xde6) and r[3]==0:
                inserts.setdefault(n,{}).setdefault(i+1,[]).append(list(r))
    return {n:[(point,'OG1 기체 추가 및 지원장치 수량', [('command',r) for r in rows])
               for point,rows in sorted(points.items())] for n,points in inserts.items()}


def legacy_recruitment(apply=False):
    import psutil
    from validate_hidden_rewards import VM,ram as vr
    from validate_beowulf_prototype import validate_story_blob
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['valcion_custom'];assert previous['applied']
    assert not journal.get('legacy_recruitment',{}).get('applied'),'Already applied'
    oldcode=struct.pack('<14I',0x8e280008,0x39080606,0x11000006,0,0x8e280008,0x39080600,0x2d080003,0x11000002,0,0x24070001,0x0806bc00,0x0000402d,0,0)
    # Owned aliases 606..60B plus the previous 600..602. All other keys retain
    # the vanilla reserve-faction behavior, including 603..605.
    code=struct.pack('<14I',0x8e280008,0x2508f9fa,0x2d080006,0x15000005,0x8e280008,0x39080600,0x2d080003,0x11000002,0,0x24070001,0x0806bc00,0x0000402d,0,0)
    codeoff=0x94880+0x114f88-0x100000
    report=dict(applied=False,units=[dict(key=k,source_record=i,name=n) for k,i,n in LEGACY_UNITS],files=[],scope='OG2 recruitment; repair/resupply grants become two')
    for item in previous['files']:
        path=Path(item['path']);s=Scripts(path);edits=[];stories=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            assert read(f,codeoff,len(oldcode))==oldcode;edits.append(dict(offset=codeoff,before=oldcode.hex(),after=code.hex()))
            for base in (0x5da000,0x83f000):
                old=read(f,base,0x1a5800);new=legacy_master(old);edits.append(dict(offset=base,before=old.hex(),after=new.hex()))
            cursor=0x9130000
            for n,scenes in sorted(legacy_scenes(s).items()):
                at,size=s.logos[n];old=s.data[at:at+size];new,note=rebuild_beowulf_story_logo(old,scenes)
                allowed=tuple(tuple(r) for _,_,lines in scenes for _,r in lines)
                proof=validate_story_blob(old,new,note,vr,allowed_commands=allowed)
                assert not any(read(f,MAP+cursor,len(new))),(n,hex(cursor),'Occupied relocation space')
                edits.extend([dict(offset=MAP+cursor,before=bytes(len(new)).hex(),after=new.hex()),
                    dict(offset=MAP+0x557f800+8+n*8,before=read(f,MAP+0x557f800+8+n*8,8).hex(),after=struct.pack('<II',cursor-0x557f800,len(new)).hex())])
                stories.append(dict(script=n,insertions=note['insert_counts'],validation=proof));cursor=(cursor+len(new)+2047)&~2047
            assert cursor<0x9300000
            root=MAP+0x800+8+14*8+4;a=read(f,root,4);edits.append(dict(offset=root,before=a.hex(),after=struct.pack('<I',max(u32(a,0),cursor-0x557e800)).hex()))
            vm=VM();c=vm.cpu;c.mem[0x100000:0x582980]=read(f,0x94880,0x482980);c.mem[0x114f88:0x114f88+len(code)]=code
            blob=bytes.fromhex(next(e['after'] for e in edits if e['offset']==0x5da000));h=0x11e800;master=u32(vr,0x59d360);p=0x1100000;c.mem[p:p+len(blob[h:])]=blob[h:]
            for i,field in enumerate(range(0x18,0x8c,4)):
                q=p+u32(blob,h+field)
                for o,v in [(0,q),(4,c.read(q,4)),(8,c.read(q+4,4)),(12,c.read(q+8,4)),(16,q),(20,q+12)]:c.write(master+0x28+i*24+o,v,4)
            save=u32(vr,0x59d364)
            for key,source,name in LEGACY_UNITS:
                vm.op(command(0x5a,key));slot=c.run(0x1abc50,[save,key,0,0]);assert slot>=0 and c.run(0x1a9b70,[save,slot,1])==1
                assert c.run(0x1b1300,[save,slot,0])==-1 and c.run(0x1b01d0,[save,0x34,slot,0])==(65535 if key==0x607 else 1)
                vm.op(command(0x5a,key));assert c.run(0x1abc50,[save,key,0,0])==slot
                raw=blob[h+u32(blob,h+0x1c)+12+source*100:][:100]
                for fn,want in ((0x1a7d40,u32(raw,0)),(0x1a7cc0,u16(raw,0x18)),(0x1a7b40,u16(raw,0x1a)),(0x1a7bc0,raw[0x53]),(0x1a7c40,raw[0x52])):assert c.run(fn,[master,key])==want
                for weapon in struct.unpack_from('<16H',raw,0x24):
                    if weapon!=65535:assert c.run(0x1a4a20,[master,weapon])>=0
            for key in range(0x600,0x60d):
                rec=0x1900000;c.write(rec+8,key,4);c.r[17]=rec;c.r[7]=31;c.run(0x114f88,stop=0x1af000)
                assert c.r[7]==(1 if key in (0x600,0x601,0x602) or 0x606<=key<=0x60b else 31)
            for key in (0xde5,0xde6):
                allocations=[]
                for repeat in range(2):
                    before=bytes(c.mem);c.writes.clear();vm.op(command(0x5f,key,0))
                    slots={a for a,z,pc in c.writes if pc==0x33513c and z==2 and c.read(a,2)==key and before[a:a+2]!=c.mem[a:a+2]}
                    assert len(slots)==1;allocations.extend(slots)
                assert len(set(allocations))==2
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=sorted(edits,key=lambda e:e['offset']),stories=stories,native_grants_verified=True,duplicates_prevented=True,original_master_records_preserved=True))
        print(path.name,'legacy recruitment and native grant checks passed',flush=True)
    journal['legacy_recruitment']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for item in report['files']:
            inv,target,pos=hashlib.sha256(),hashlib.sha256(),0
            with Path(item['path']).open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],len(a))==a;f.seek(e['offset']);f.write(b)
                f.flush();os.fsync(f.fileno());f.seek(0)
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inv.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inv.update(a);target.update(b);pos+=len(b)
                while raw:=f.read(4<<20):inv.update(raw);target.update(raw)
            assert inv.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest();print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
        report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


def weapon_cost_rebalance(apply=False):
    """Only price curves and Rivale's price-tier bits; never growth bits."""
    import psutil
    from r5900_scalar_check import CPU
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['legacy_recruitment'];assert previous['applied']
    assert not journal.get('weapon_cost_rebalance',{}).get('applied'),'Already applied'
    offset=0x94880+0x534e30-0x100000
    expected=struct.pack('<80I',*(step*i for step in (2000,2400,4000,5200,6000) for i in range(16)))
    target=struct.pack('<80I',*(step*i for step in (1600,1600,1920,3200,3200) for i in range(16)))
    report=dict(applied=False,ten_stage_costs=[88000,88000,105600,176000,176000],
        all_attack_growth_unchanged=True,rivale_cost_tiers=[0,1,2],files=[])
    for item in previous['files']:
        path=Path(item['path']);edits=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            old=read(f,offset,320);vanilla=struct.pack('<80I',*(step*i for step in (2000,3000,5000,6500,7500) for i in range(16)));assert old in (expected,vanilla)
            edits.append(dict(offset=offset,before=old.hex(),after=target.hex()))
            for base in (0x5da000,0x83f000):
                blob=read(f,base,0x1a5800);h=0x11e800;wt=h+u32(blob,h+0x20);weap=h+u32(blob,h+0x24)
                for tier,key in enumerate(range(0xf90,0xf93)):
                    index=u16(blob,wt+12+key*2);p=weap+12+index*36+3;a=blob[p:p+1]
                    assert a[0]&7==(1 if tier==2 else 0) and (a[0]>>3)&7==0
                    b=bytes([(a[0]&~7)|tier])
                    if a!=b:edits.append(dict(offset=base+p,before=a.hex(),after=b.hex()))
            ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes();c=CPU(ram)
            c.mem[0x100000:0x582980]=read(f,0x94880,0x482980);c.mem[0x534e30:0x534f70]=target
            # Execute the same menu lookup and invested-cost loop used in-game.
            for tier in range(5):
                for level in range(1,16):
                    c.r[2]=tier;c.r[16]=(level-1)*4;c.r[17]=level-1;c.r[19]=0x1800000;c.write(0x1800000+0x53c,0,4)
                    c.run(0x443858,stop=0x443880)
                    assert c.read(0x1800000+0x53c,4)==u32(target,tier*64+level*4)
                    c.r[2]=tier;c.r[3]=level;c.r[16]=0;c.run(0x334f98,stop=0x334fd8)
                    assert c.r[16]==sum(u32(target,tier*64+i*4) for i in range(1,level+1))
            assert all(sum(u32(target,t*64+i*4) for i in range(1,11))==report['ten_stage_costs'][t] for t in range(5))
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=sorted(edits,key=lambda e:e['offset']),native_menu_and_total_checks=75))
        print(path.name,'price-only checks passed',flush=True)
    journal['weapon_cost_rebalance']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for item in report['files']:
            inv,targethash,pos=hashlib.sha256(),hashlib.sha256(),0
            try:
                with Path(item['path']).open('r+b') as f:
                    for e in item['edits']:
                        a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],len(a))==a;f.seek(e['offset']);f.write(b)
                    f.flush();os.fsync(f.fileno());f.seek(0)
                    for e in item['edits']:
                        while pos<e['offset']:
                            raw=f.read(min(4<<20,e['offset']-pos));assert raw;inv.update(raw);targethash.update(raw);pos+=len(raw)
                        a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inv.update(a);targethash.update(b);pos+=len(b)
                    while raw:=f.read(4<<20):inv.update(raw);targethash.update(raw)
                assert inv.hexdigest()==item['before_sha256'];item['after_sha256']=targethash.hexdigest()
            except Exception:
                with Path(item['path']).open('r+b') as f:
                    for e in item['edits']:f.seek(e['offset']);f.write(bytes.fromhex(e['before']))
                raise
            print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
        report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


def enemy_upgrade_plus2(apply=False):
    import psutil
    from validate_hidden_rewards import validate_enemy_strength
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['weapon_cost_rebalance'];assert previous['applied']
    assert not journal.get('enemy_upgrade_plus2',{}).get('applied'),'Already applied'
    original=json.loads((ROOT/'runtime/enemy_strength_manifest.json').read_text(encoding='utf-8'))
    offset=0x94880+original['layout']['spawn_helper']+7*4-0x100000
    before=struct.pack('<I',0x24420001);after=struct.pack('<I',0x24420002)
    proof=validate_enemy_strength([(offset,before,after)],original['layout'],upgrade_add=2,compare_vanilla=True)
    report=dict(applied=False,body_and_weapon_upgrade_add=2,pilot_stat_add=5,native_caps_retained=True,checks=proof,files=[])
    for item in previous['files']:
        path=Path(item['path'])
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            assert read(f,offset,4)==before
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=[dict(offset=offset,before=before.hex(),after=after.hex())]))
    journal['enemy_upgrade_plus2']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for item in report['files']:
            inv,target,pos=hashlib.sha256(),hashlib.sha256(),0
            with Path(item['path']).open('r+b') as f:
                assert read(f,offset,4)==before;f.seek(offset);f.write(after);f.flush();os.fsync(f.fileno());f.seek(0)
                while pos<offset:
                    raw=f.read(min(4<<20,offset-pos));assert raw;inv.update(raw);target.update(raw);pos+=len(raw)
                assert f.read(4)==after;inv.update(before);target.update(after)
                while raw:=f.read(4<<20):inv.update(raw);target.update(raw)
            assert inv.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
            print(Path(item['path']).name,'enemy upgrade +2 applied',item['after_sha256'],flush=True)
        report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False),flush=True)


def upgrade_report():
    """List actual player weapon records, keeping growth and price separate."""
    from collections import defaultdict
    path=ROOT/'build/SRWOGS_K.iso'
    with path.open('rb') as f:
        b=read(f,0x5da000,0x1a5800);h=0x11e800
        def table(k):return h+u32(b,h+k)
        st=table(0x80)
        def name(i):
            p=st+u32(b,st+12+i*4);return decode(b[p:b.index(0,p)])
        s=Scripts(path);wp=0x5071000;units=set()
        for n in range(min(144,u32(s.data,wp+4))):
            at=wp+u32(s.data,wp+8+n*8)
            for j in range(u32(s.data,at+40)):
                a=at+44+j*336;key=u32(s.data,a)
                if key<4096 and u32(s.data,a+8)==0:
                    idx=u16(b,table(0x18)+12+key*2)
                    if idx not in (0,1,65535):units.add(idx)
        for key in range(0x600,0x60c):
            idx=u16(b,table(0x18)+12+key*2)
            if idx!=65535:units.add(idx)
        weapons=defaultdict(set)
        for idx in sorted(units):
            a=table(0x1c)+12+idx*100;owner=name(u16(b,a+12))
            for key in struct.unpack_from('<16H',b,a+0x24):
                if key==65535:continue
                wi=u16(b,table(0x20)+12+key*2)
                if wi!=65535 and u16(b,table(0x24)+12+wi*36+8):weapons[wi].add(owner)
        growth=[];cost=[]
        for address,out in ((0x534bb4,growth),(0x534e30,cost)):
            data=read(f,0x94880+address-0x100000,320)
            for tier in range(5):
                values=struct.unpack_from('<16I',data,tier*64);out.append(sum(values[:10]) if address==0x534bb4 else sum(values[1:11]))
        rows=[]
        for wi,owners in weapons.items():
            a=table(0x24)+12+wi*36;ct=b[a+3]&7;gt=(b[a+3]>>3)&7
            if ct<5 and gt<5:rows.append((ct,gt,name(u16(b,a+4)),wi,owners))
        lines=['무기 개조 등급 — 현재 SRWOGS_K.iso 기준','비용과 공격력 상승량은 별도 등급입니다. 내부 등급은 0부터 시작합니다.',
            'OG1·OG2 아군 배치 및 추가 지급 기체의 고정·기본 장착 무장 기준. 개조표 범위 밖의 특수 무장은 제외.','']
        for tier in range(5):lines.append(f'공격력 상승 등급 {tier}: 10단계 +{growth[tier]} / 비용 등급 {tier}: 10단계 {cost[tier]:,}')
        for ct in sorted(set(r[0] for r in rows),reverse=True):
            lines+=['',f'=== 비용 등급 {ct} / 10단계 {cost[ct]:,} ===']
            for _,gt,n,wi,owners in sorted((r for r in rows if r[0]==ct),key=lambda r:(r[1],r[2],r[3])):
                lines.append(f'{n} | 상승등급 {gt} (+{growth[gt]}) | '+', '.join(sorted(owners))+f' | Weap[{wi}]')
        out=ROOT/'runtime/무기_개조등급_목록.txt';out.write_text('\n'.join(lines),encoding='utf-8-sig')
        print('Growth',growth,'cost',cost,'records',len(rows),flush=True)
        for ct in (4,3):print('Cost tier',ct,sorted(set(n for c,g,n,wi,owners in rows if c==ct)),flush=True)
        return out


def restoration_master(old):
    """605 is damaged; 60C is the same machine after native story conversion."""
    h=0x11e800;fields=list(range(0x18,0x8c,4))
    starts=[h+u32(old,h+k) for k in fields];end=h+u32(old,0x11e00c)
    ts={k:bytearray(old[p:(starts[i+1] if i+1<len(starts) else end)]) for i,(k,p) in enumerate(zip(fields,starts))}
    ui=u16(ts[0x18],12+UNIT*2);assert ui==429
    assert u16(ts[0x18],12+0x60c*2)==65535
    uc,wc=u32(ts[0x1c],8),u32(ts[0x24],8)
    pos=12+ui*100;full=bytearray(ts[0x1c][pos:pos+100]);weak=bytearray(full)
    assert (u32(full),u16(full,0x18),u16(full,0x1a),full[0x52],full[0x53])==(8300,500,2100,7,120)
    assert full[0x57:0x5d]==bytes((9,10,14,19,22,0))
    struct.pack_into('<I',weak,0,u32(full)*9//10)
    for off in (0x18,0x1a):struct.pack_into('<H',weak,off,u16(full,off)*9//10)
    for off in (0x52,0x53):weak[off]=full[off]*9//10
    weak[0x57:0x5d]=bytes(6)
    weapons=[]
    for i,key in enumerate((0xf90,0xf91,0xf92)):
        wi=u16(ts[0x20],12+key*2);p=12+wi*36;r=bytes(ts[0x24][p:p+36]);newkey=0xfb0+i
        assert u16(ts[0x20],12+newkey*2)==65535
        assert u16(r,8)==(3900,4100,4900)[i]
        ts[0x24].extend(r);struct.pack_into('<H',ts[0x20],12+newkey*2,wc+i)
        struct.pack_into('<H',ts[0x24],p+8,u16(r,8)-400)
        weapons.append(dict(damaged_key=key,restored_key=newkey,damaged_power=u16(r,8)-400,restored_power=u16(r,8)))
    struct.pack_into('<II',ts[0x24],4,u32(ts[0x24],4)+108,wc+3)
    struct.pack_into('<3H',full,0x24,0xfb0,0xfb1,0xfb2)
    ts[0x1c][pos:pos+100]=weak;ts[0x1c].extend(full)
    struct.pack_into('<II',ts[0x1c],4,u32(ts[0x1c],4)+100,uc+1)
    struct.pack_into('<I',ts[0x18],4,u32(ts[0x18],4)+100)
    struct.pack_into('<H',ts[0x18],12+0x60c*2,uc)
    for field in (0x80,0x84,0x88):
        if starts[0]+sum(map(len,ts.values()))<=len(old):break
        st=ts[field];strings=[]
        for i in range(u32(st,8)):
            q=u32(st,12+i*4);strings.append(bytes(st[q:st.index(0,q)+1]))
        pool=bytearray();positions={}
        for value in sorted(set(strings),key=lambda x:(-len(x),x)):
            q=pool.find(value)
            if q<0:q=len(pool);pool.extend(value)
            positions[value]=q
        prefix=12+len(strings)*4
        st=bytearray(ts[field][:4]+struct.pack('<II',prefix+len(pool),len(strings)))
        st.extend(struct.pack('<%dI'%len(strings),*[prefix+positions[v] for v in strings]));st.extend(pool);st.extend(bytes((-len(st))%4))
        for i,value in enumerate(strings):
            q=u32(st,12+i*4);assert st[q:st.index(0,q)+1]==value
        ts[field]=st
    out=bytearray(old[:starts[0]])
    for k in fields:struct.pack_into('<I',out,h+k,len(out)-h);out.extend(ts[k])
    struct.pack_into('<I',out,0x11e00c,len(out)-h)
    assert h<=end<=len(old) and len(out)<=len(old),("master allocation",len(out),len(old),end)
    out.extend(old[len(out):])
    for k,stride,allowed in [(0x1c,100,{ui}),(0x24,36,{u16(old,starts[2]+12+key*2) for key in (0xf90,0xf91,0xf92)}),(0x2c,148,set())]:
        a=starts[fields.index(k)];b=h+u32(out,h+k)
        for i in range(u32(old,a+8)):
            if i not in allowed:assert old[a+12+i*stride:a+12+(i+1)*stride]==out[b+12+i*stride:b+12+(i+1)*stride]
    return bytes(out),dict(damaged_key=UNIT,restored_key=0x60c,restored_record=uc,
        damaged_stats=[7470,450,1890,6,108],restored_stats=[8300,500,2100,7,120],
        removed_abilities=list(full[0x57:0x5d]),weapons=weapons)


def restoration_scenes(s):
    """36 clear is common to both routes, before the 37 Tesla-lab battle."""
    rs=s.records(79);at,n=s.logos[79];old=s.data[at:at+n];nc=u32(old,0x40)
    texts=s.texts(79)
    def text(r):
        i=r[2]-nc+1
        return texts[i][1] if r[0]==0x30 and 0<=i<len(texts) else ''
    point=next(i+1 for i,(_,r) in enumerate(rs) if '리바레도' in text(r) and '전력으로' in text(r))
    early=[(PILOT,'잉그램：다만、리바레는 완전한 상태가 아니다。'),
      (PILOT,'잉그램：마지막 결전의 손상에、차원이동의 충격까지 겹쳤다。'),
      (PILOT,'잉그램：출력은 저하됐고、왜곡필드와 자동수복도 정지했다。'),
      (0x4bc,'로버트：지금은 응급조치가 한계입니다。 해석이 끝나면 수복을 시도하죠。'),
      (PILOT,'잉그램：그때까지는、남아 있는 힘으로 싸우겠다。')]
    rs=s.records(102);point36=next(i for i,(_,r) in reversed(list(enumerate(rs))) if r[0]==0x9c)
    # Native background command copied from the current post-battle hangar scene.
    background=next(list(r) for _,r in reversed(s.records(79)[:point]) if r[0]==0x39)
    late=[('command',background),
      (0x4bc,'로버트：리바레의 수복 작업이 끝났습니다。')]
    late.extend([
      (0x4bc,'로버트：즈필드 크리스탈의 자기수복 기능을 재기동했습니다。'),
      (0x4bc,'로버트：지구에서 해석한 에어로게이터 기술로、동력계도 복구했죠。'),
      (PILOT,'잉그램：차원이동으로 끊어진 회로까지 정상화됐군。'),
      (0x4bc,'로버트：네。 최종전에서 입은 손상도 모두 수복했습니다。'),
      (0x4bc,'로버트：무장 출력과 왜곡필드、자동회복 기능도 원래대로입니다。'),
      (0x4ab,'류세이：그럼、이게 리바레의 원래 힘이란 말이지？'),
      (PILOT,'잉그램：그래。 이제는 전력을 다할 수 있다。'),
      ('command',command(0x6f,UNIT,0x60c,0)),
      (PILOT,'잉그램：이번에는 이 힘을、동료를 지키는 데 쓰겠다。')])
    return {79:[(point,'최종전과 차원이동의 후유증',early)],102:[(point36,'리바레 수복 완료',late)]}


def restoration_validation(path,blob):
    from validate_hidden_rewards import VM,ram as vr,CTX,REC
    vm=VM();c=vm.cpu
    with path.open('rb') as f:c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
    h=0x11e800;master=u32(vr,0x59d360);p=0x1100000;c.mem[p:p+len(blob[h:])]=blob[h:]
    for i,k in enumerate(range(0x18,0x8c,4)):
        q=p+u32(blob,h+k)
        for off,v in [(0,q),(4,c.read(q,4)),(8,c.read(q+4,4)),(12,c.read(q+8,4)),(16,q),(20,q+12)]:c.write(master+0x28+i*24+off,v,4)
    getters=(0x1a7d40,0x1a7cc0,0x1a7b40,0x1a7c40,0x1a7bc0)
    for key,stats,abilities in [(UNIT,[7470,450,1890,6,108],[0]*6),(0x60c,[8300,500,2100,7,120],[9,10,14,19,22,0])]:
        assert [c.run(fn,[master,key]) for fn in getters]==stats
        assert [c.run(0x1a6f00,[master,key,i]) for i in range(6)]==abilities
    for a,b,power in [(0xf90,0xfb0,3900),(0xf91,0xfb1,4100),(0xf92,0xfb2,4900)]:
        assert c.run(0x1a5dc0,[master,a])==power-400 and c.run(0x1a5dc0,[master,b])==power
        for fn in (0x1a4a20,0x1a5720,0x1a57b0,0x1a5b40):assert c.run(fn,[master,a])==c.run(fn,[master,b])
    save=u32(vr,0x59d364);vm.op(command(0x5a,UNIT));slot=c.run(0x1abc50,[save,UNIT,0,0]);assert slot>=0
    c.run(0x1af000,[save,2,slot,1,0]);pilot=c.run(0x1b1fd0,[save,PILOT,0]);assert pilot>=0
    c.run(0x1b13d0,[save,pilot,slot,0])
    for i,prop in enumerate(range(0xd,0x11)):c.run(0x1af000,[save,prop,slot,i+1,0])
    for i in range(3):c.write(REC,i,4);c.run(0x1af000,[save,0xc,slot,5+i,REC])
    def grades():
        body=[c.run(0x1af860,[save,x,slot,0]) for x in range(0xd,0x11)];w=[]
        for i in range(3):c.write(REC,i,4);w.append(c.run(0x1af860,[save,0xc,slot,REC]))
        return body,w
    expected=grades();assert expected==([1,2,3,4],[5,6,7]),expected
    # Use the snapshot's initialized battle root, rather than a zero actor pool.
    root=0x68c1d0;assert c.read(root+0x28,4)==0x59b240
    c.write(CTX+0x310c,root,4)
    # This scene runs after battle cleanup. Match its empty actor pool.
    for i in range(255):c.write(root+0x40e00+0x1a608+i*0x1a0,-1,4)
    assert c.read(0x867be0+0x18,4)==0xffffffff
    before=bytes(c.mem[save:save+0x3b400])
    vm.op(command(0x6f,UNIT,0x60c,0))
    restored=c.run(0x1abc50,[save,0x60c,0,0]);assert restored==slot,(restored,slot)
    assert c.run(0x1b1300,[save,restored,0])==pilot
    assert grades()==expected,(grades(),expected)
    assert c.run(0x1a9b70,[save,slot,1])==1
    after=bytes(c.mem[save:save+0x3b400]);vm.op(command(0x6f,UNIT,0x60c,0))
    assert c.mem[save:save+0x3b400]==after,'Repeated conversion modified the save'
    for i in range(512):
        p=0x6efc+i*216
        if i!=slot:assert before[p:p+216]==after[p:p+216],'Other unit changed'
    assert before[0x25cfc:0x25cfc+512*92]==after[0x25cfc:0x25cfc+512*92],'Pilot records changed'
    return dict(native_stats_and_abilities=True,native_weapon_equivalence=True,native_story_conversion=True,
        roster_slot_retained=slot,pilot_retained=True,body_upgrade_levels=expected[0],weapon_upgrade_levels=expected[1],
        repeated_conversion_idempotent=True,other_units_and_pilots_preserved=True,live_playthrough=False)


def restoration(apply=False):
    import psutil
    from validate_beowulf_prototype import validate_story_blob
    from validate_hidden_rewards import ram as vr
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['enemy_upgrade_plus2'];assert previous['applied']
    assert not journal.get('restoration',{}).get('applied'),'Already applied'
    report=dict(applied=False,chapter=36,timing='clear',files=[])
    readable=[]
    for item in previous['files']:
        path=Path(item['path'])
        if not path.exists():
            assert path.name=='SRWOGS_BEOWULF_TEST.iso'
            report.setdefault('absent_optional_test_files',[]).append(str(path));continue
        s=Scripts(path);edits=[];proofs=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            for base in (0x5da000,0x83f000):
                old=read(f,base,0x1a5800);new,note=restoration_master(old)
                native=restoration_validation(path,new)
                edits.append(dict(offset=base,before=old.hex(),after=new.hex()))
            cursor=0x8e60000
            for n,scenes in restoration_scenes(s).items():
                at,size=s.logos[n];old=s.data[at:at+size];new,notes=rebuild_beowulf_story_logo(old,scenes,speaker_context=True)
                allowed=tuple(tuple(r) for _,_,lines in scenes for who,r in lines if who=='command')
                proof=validate_story_blob(old,new,notes,vr,allowed_commands=allowed)
                assert not any(read(f,MAP+cursor,len(new))),(n,hex(cursor),'Occupied relocation space')
                edits.extend([dict(offset=MAP+cursor,before=bytes(len(new)).hex(),after=new.hex()),
                    dict(offset=MAP+0x557f800+8+n*8,before=read(f,MAP+0x557f800+8+n*8,8).hex(),after=struct.pack('<II',cursor-0x557f800,len(new)).hex())])
                proofs.append(dict(script=n,checks=proof,notes=notes));cursor=(cursor+len(new)+2047)&~2047
                if path.name=='SRWOGS_K.iso':
                    for _,title,lines in scenes:readable.extend([title]+[str(t) for who,t in lines if who!='command']+[''])
            assert cursor<0x8f00000
            off=MAP+0x800+8+14*8+4;old=read(f,off,4);new=struct.pack('<I',max(u32(old),cursor-0x557e800))
            if old!=new:edits.append(dict(offset=off,before=old.hex(),after=new.hex()))
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=sorted(edits,key=lambda e:e['offset']),master=note,checks=native,stories=proofs))
        print(path.name,'restoration plan/native validation passed',flush=True)
    journal['restoration']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'runtime/리바레_수복_대사.txt').write_text('\n'.join(readable),encoding='utf-8-sig')
    if not apply:return
    for item in report['files']:
        inv,target,pos=hashlib.sha256(),hashlib.sha256(),0
        with Path(item['path']).open('r+b') as f:
            for e in item['edits']:
                a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],len(a))==a;f.seek(e['offset']);f.write(b)
            f.flush();os.fsync(f.fileno());f.seek(0)
            for e in item['edits']:
                while pos<e['offset']:
                    raw=f.read(min(4<<20,e['offset']-pos));assert raw;inv.update(raw);target.update(raw);pos+=len(raw)
                a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inv.update(a);target.update(b);pos+=len(b)
            while raw:=f.read(4<<20):inv.update(raw);target.update(raw)
        assert inv.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest();print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
    report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')


def enemy_deployment_edits(f):
    """Apply grades to real actors, not only UNTD's permanent registration."""
    from build_beowulf_prototype import Asm
    start=0x200350;a=Asm(start)
    a.i(0x24,20,2,0x74);a.i(12,2,2,7);a.i(9,2,2,-2);a.i(11,2,2,3)
    a.branch(4,2,0,'end');a.emit(0);a.i(9,16,16,2);a.i(9,19,19,2)
    a.label('end');a.i(0x23,20,2,0);a.emit(0x03e00008);a.i(0x23,2,23,0x1034)
    code=a.data();assert start+len(code)<=0x2003c4
    changes=[(start,bytes(len(code)),code),
        (0x1e7198,struct.pack('<II',0x8e820000,0x8c571034),struct.pack('<II',3<<26|start>>2,0)),
        (0x1d5a08,struct.pack('<II',3<<26|0x200318>>2,0),struct.pack('<II',0x8fa300a8,0x28610006))]
    edits=[]
    for pc,before,after in changes:
        off=0x94880+pc-0x100000;assert read(f,off,len(before))==before,(hex(pc),'Unexpected instruction')
        edits.append(dict(offset=off,before=before.hex(),after=after.hex()))
    return sorted(edits,key=lambda e:e['offset'])


def validate_enemy_deployment(state,edits):
    """Reproduce the report using its real temporary roster and actor row."""
    from analyze_ogs_runtime_roles import load_ram
    from r5900_scalar_check import CPU
    rr,fmt=load_ram(state);save=u32(rr,0x59d364);master=u32(rr,0x59d360)
    # Find the actual enemy actor for temporary unit400, without assuming heap addresses.
    needle=struct.pack('<I',save);p=0;actors=[]
    while True:
        p=rr.find(needle,p)
        if p<0:break
        obj=p-4;p+=4
        if obj>=0 and 0x400<=u32(rr,obj+0x18)<0x414 and rr[obj+0x74]&7 in (2,3,4):actors.append(obj)
    assert len(actors)==20,('Expected reported chapter24 Gunsect group',len(actors))
    actor=actors[0];slot=u32(rr,actor+0x18);src=u32(rr,actor+0x168);assert u32(rr,src)==0x452
    for e in edits:
        pc=e['offset']-0x94880+0x100000;before=bytes.fromhex(e['before']);assert rr[pc:pc+len(before)]==before
    def machine(patched):
        c=CPU(rr)
        if patched:
            for e in edits:
                pc=e['offset']-0x94880+0x100000;b=bytes.fromhex(e['after']);c.mem[pc:pc+len(b)]=b
        return c
    def grades(c,sl=slot):
        body=[c.run(0x1af860,[save,i,sl,0]) for i in range(0xd,0x11)]
        arg=0x1800000;c.write(arg,0,4)
        return body,c.run(0x1af860,[save,0xc,sl,arg])
    c=machine(False)
    assert all(grades(c,u32(rr,o+0x18))==([0]*4,0) for o in actors)
    for patched in (False,True):
        c=machine(patched)
        for obj in actors:
            c.run(0x1e70e0,[obj,0],stop=0x1e74a0)
            assert grades(c,u32(rr,obj+0x18))==([2 if patched else 0]*4,2 if patched else 0)
    cases=0;body_checks=0;weapon_checks=0
    for diff in range(3):
        for side in range(6):
            for base in (0,5,14,15):
                results=[]
                for patched in (False,True):
                    c=machine(patched);global_=u32(rr,0x59d36c)
                    c.write(global_+0xf60,0,4);c.write(global_+0xf68,diff,4)
                    c.write(actor+0x74,(rr[actor+0x74]&~7)|side,1)
                    for off in (0x38,0x3c,0x40,0x44,0x48,0x4c):c.write(src+off,base,4)
                    c.run(0x1e70e0,[actor,0],stop=0x1e74a0);results.append(grades(c))
                add=2 if side in (2,3,4) else 0
                for x,y in zip(results[0][0],results[1][0]):assert y==min(x+add,15),(diff,side,base,results);body_checks+=1
                assert results[1][1]==min(results[0][1]+add,15),(diff,side,base,results);weapon_checks+=1;cases+=1
    # The old registration helper must no longer run (prevents double addition).
    c=machine(True);ctx=0x1600000;source=0x1700000
    c.write(ctx+0x28,0x59b240,4);c.write(ctx+0x346d4,source,4);c.mem[source:source+336]=rr[src:src+336]
    c.run(0x1d5970,[ctx,0]);assert c.visits[0x200318]==0
    # PADDUB is used by a native lookup within the actor weapon loop.
    c=CPU(bytes(0x200));c.pc=0;c.write(0,28<<26|1<<21|2<<16|3<<11|24<<6|0x28,4)
    xs=bytes((0,1,254,255)*4);ys=bytes((0,255,2,1)*4)
    c.r[1]=int.from_bytes(xs,'little');c.r[2]=int.from_bytes(ys,'little');c.step()
    assert c.r[3].to_bytes(16,'little')==bytes(min(x+y,255) for x,y in zip(xs,ys))
    return dict(state=str(state),state_sha256=hashlib.sha256(state.read_bytes()).hexdigest(),
        reported_enemy_count=20,reported_before_body=[0]*4,reported_before_weapon=0,reported_after_body=[2]*4,reported_after_weapon=2,
        real_actor_initializer_through_all_unit_and_weapon_grade_stores=True,stopped_before_pilot_and_render_tail=True,
        difficulty_side_cap_cases=cases,body_assertions=body_checks,weapon_assertions=weapon_checks,
        allies_and_neutrals_unchanged=True,old_registration_hook_removed=True,paddub_lane_check=True,live_playthrough=False)


def enemy_deployment_fix(apply=False):
    import psutil
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    folder=Path(r'C:\Users\OXP2\Desktop\슈퍼로봇대전 2차, 3파 알파 hd버전\pcsx2-v1.7.4005-windows-64bit-AVX2-Qt\sstates')
    state=folder/'SLPS-25733 (442C24CB).01.p2s';assert state.exists()
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['restoration'];assert previous['applied']
    assert not journal.get('enemy_deployment_fix',{}).get('applied'),'Already applied'
    report=dict(applied=False,files=[])
    for item in previous['files']:
        path=Path(item['path'])
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            edits=enemy_deployment_edits(f)
        proof=validate_enemy_deployment(state,edits)
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=edits,checks=proof))
        print(path.name,'actual chapter24 Gunsect regression passed',flush=True)
    journal['enemy_deployment_fix']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if not apply:return
    for item in report['files']:
        inv,target,pos=hashlib.sha256(),hashlib.sha256(),0
        with Path(item['path']).open('r+b') as f:
            for e in item['edits']:
                a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert read(f,e['offset'],len(a))==a;f.seek(e['offset']);f.write(b)
            f.flush();os.fsync(f.fileno());f.seek(0)
            for e in item['edits']:
                while pos<e['offset']:
                    raw=f.read(min(4<<20,e['offset']-pos));assert raw;inv.update(raw);target.update(raw);pos+=len(raw)
                a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inv.update(a);target.update(b);pos+=len(b)
            while raw:=f.read(4<<20):inv.update(raw);target.update(raw)
        assert inv.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest();print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
    report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')



def refurbishment_master(old):
    """Independent damaged bodies; no enemy or shared weapon edits."""
    h=0x11e800;fields=list(range(0x18,0x8c,4));starts=[h+u32(old,h+k) for k in fields];end=h+u32(old,0x11e00c)
    ts={k:bytearray(old[p:(starts[i+1] if i+1<len(starts) else end)]) for i,(k,p) in enumerate(zip(fields,starts))}
    notes=[]
    for key,fullkey,newweapons,ratio,penalty in [(0x600,0x60d,range(0xfc0,0xfc4),90,400),(0x606,0x60e,range(0xfc4,0xfc8),95,200)]:
        idx=u16(ts[0x18],12+key*2);count=u32(ts[0x1c],8);wc=u32(ts[0x24],8)
        assert u16(ts[0x18],12+fullkey*2)==65535
        pos=12+idx*100;full=bytes(ts[0x1c][pos:pos+100]);weak=bytearray(full)
        expected=(6300,190,1900,7,125) if key==0x600 else (9000,300,2100,6,120)
        assert (u32(full),u16(full,0x18),u16(full,0x1a),full[0x52],full[0x53])==expected
        struct.pack_into('<I',weak,0,u32(full)*ratio//100)
        for off in (0x18,0x1a):struct.pack_into('<H',weak,off,u16(full,off)*ratio//100)
        # Retain movement for the mildly weakened Valsion; Mumyou follows Rivale.
        for off in ((0x52,0x53) if key==0x600 else (0x53,)):weak[off]=full[off]*ratio//100
        if key==0x600:weak[0x57:0x5d]=bytes(6)
        weapons=[]
        for i,newkey in enumerate(newweapons):
            original=u16(full,0x24+i*2);wi=u16(ts[0x20],12+original*2);r=bytearray(ts[0x24][12+wi*36:12+(wi+1)*36])
            assert original!=65535 and len(r)==36 and u16(ts[0x20],12+newkey*2)==65535
            power=u16(r,8);struct.pack_into('<H',r,8,power-penalty)
            ts[0x24].extend(r);struct.pack_into('<H',ts[0x20],12+newkey*2,wc+i);struct.pack_into('<H',weak,0x24+i*2,newkey)
            weapons.append(dict(damaged_key=newkey,restored_key=original,damaged_power=power-penalty,restored_power=power))
        struct.pack_into('<II',ts[0x24],4,u32(ts[0x24],4)+144,wc+4)
        ts[0x1c][pos:pos+100]=weak;ts[0x1c].extend(full)
        struct.pack_into('<II',ts[0x1c],4,u32(ts[0x1c],4)+100,count+1);struct.pack_into('<I',ts[0x18],4,u32(ts[0x18],4)+100)
        struct.pack_into('<H',ts[0x18],12+fullkey*2,count)
        notes.append(dict(key=key,full_key=fullkey,weak_record=idx,full_record=count,clear_threshold=36 if key==0x600 else 38,
            weak_stats=[u32(weak),u16(weak,0x18),u16(weak,0x1a),weak[0x52],weak[0x53]],full_stats=list(expected),
            weak_abilities=list(weak[0x57:0x5d]),full_abilities=list(full[0x57:0x5d]),weapons=weapons))
    # Pool suffixes without changing a single logical string, including codec controls.
    for field in (0x80,0x84,0x88):
        if starts[0]+sum(map(len,ts.values()))<=len(old):break
        st=ts[field];n=u32(st,8);strings=[]
        for i in range(n):
            q=u32(st,12+4*i);assert 12+4*n<=q<len(st)
            strings.append(bytes(st[q:st.index(0,q)+1]))
        pool=bytearray();positions={}
        for value in sorted(set(strings),key=lambda x:(-len(x),x)):
            q=pool.find(value)
            if q<0:q=len(pool);pool.extend(value)
            positions[value]=q
        prefix=12+4*n;out=bytearray(st[:4]+struct.pack('<II',prefix+len(pool),n))
        out.extend(struct.pack('<%dI'%n,*[prefix+positions[v] for v in strings]));out.extend(pool);out.extend(bytes((-len(out))%4))
        assert len(out)<=len(st)
        for i,v in enumerate(strings):
            q=u32(out,12+4*i);assert out[q:out.index(0,q)+1]==v
        ts[field]=out
    out=bytearray(old[:starts[0]])
    for k in fields:struct.pack_into('<I',out,h+k,len(out)-h);out.extend(ts[k])
    struct.pack_into('<I',out,0x11e00c,len(out)-h);assert h<=end<=len(old) and len(out)<=len(old),("master allocation",len(out),len(old),end)
    out.extend(old[len(out):])
    for k,stride in ((0x1c,100),(0x24,36),(0x2c,148)):
        a=starts[fields.index(k)];b=h+u32(out,h+k)
        for i in range(u32(old,a+8)):
            if k==0x1c and i in {n['weak_record'] for n in notes}:continue
            assert old[a+12+i*stride:a+12+(i+1)*stride]==out[b+12+i*stride:b+12+(i+1)*stride]
    return bytes(out),notes


def refurbishment_hook(f,notes,rivale_pair=(429,432,36)):
    """Pure table selection: saves, slots, pilots and upgrades are not rewritten."""
    from build_beowulf_prototype import Asm
    pairs=[(n['weak_record'],n['full_record'],n['clear_threshold']) for n in notes]+[rivale_pair]
    pc=0x49b0a0;a=Asm(pc)
    for i,(weak,full,threshold) in enumerate(pairs):
        for idx in (weak,full):
            a.i(9,0,2,idx);a.branch(4,5,2,'pair%d'%i);a.emit(0)
    a.branch(4,0,0,'original');a.emit(0)
    for i,(weak,full,threshold) in enumerate(pairs):
        a.label('pair%d'%i);a.i(15,0,2,0x5a);a.i(0x23,2,2,-0x2c94)
        a.branch(4,2,0,'original');a.emit(0);a.i(0x23,2,3,0xf5c);a.i(9,0,1,1)
        a.branch(5,3,1,'original');a.emit(0);a.i(0x23,2,3,0xf74);a.i(10,3,3,threshold)
        a.branch(4,3,0,'full%d'%i);a.i(9,0,5,weak)
        a.branch(4,0,0,'original');a.emit(0);a.label('full%d'%i);a.i(9,0,5,full)
        a.branch(4,0,0,'original');a.emit(0)
    a.label('original');a.i(9,29,29,-0x30);a.i(0x3f,29,31,0x10);a.jump(0x1a8d28);a.emit(0)
    code=a.data();assert pc+len(code)<0x49cbe8
    edits=[]
    for addr,before,after in [(pc,bytes(len(code)),code),(0x1a8d20,struct.pack('<II',0x27bdffd0,0xffbf0010),struct.pack('<II',2<<26|pc>>2,0))]:
        off=0x94880+addr-0x100000;assert read(f,off,len(before))==before
        edits.append(dict(offset=off,before=before.hex(),after=after.hex()))
    return edits


def refurbishment_scenes(s):
    background=next(list(r) for _,r in reversed(s.records(79)) if r[0]==0x39)
    end=lambda n:next(i for i,(_,r) in reversed(list(enumerate(s.records(n)))) if r[0]==0x9c)
    assert s.records(74)[end(74)-1][1][0:3:2]==(0x5a,0x600)
    early=[('command',background),
      (0x4bc,'로버트：무라타가 버리고 간 기체를 회수했습니다。'),
      (0x446,'쿄스케：가리온 커스텀……무명인가。'),
      (0x4bc,'로버트：동력계와 무장이 손상됐습니다。 지금은 제한 출력으로만 운용할 수 있습니다。'),
      (0x446,'쿄스케：쓸 수 있는 전력이라면 확보해 두는 편이 좋겠군。'),
      (0x4bc,'로버트：응급조치부터 하겠습니다。 제대로 된 개수는 시간이 필요합니다。')]
    late=[(0x4bc,'로버트：무명의 개수도 끝났습니다。 손상된 동력계와 구동계를 교체했습니다。'),
      (0x446,'쿄스케：회수했을 때의 출력 제한도 해제된 건가？'),
      (0x4bc,'로버트：네。 무장 출력과 방어 기능도 정상입니다。 이제 본래 성능으로 싸울 수 있습니다。'),
      (0x446,'쿄스케：좋아。 다음 전투부터 투입할 수 있도록 준비해 줘。')]
    valearly=[('command',background),
      (0x4bc,'로버트：지난 전쟁에서 사용했던 발시온 개를 인수했습니다。'),
      (0x456,'켄조：수리가 끝나지 않았다고 들었는데。'),
      (0x4bc,'로버트：네。 응급수리는 마쳤지만、동력계와 무장은 아직 제한 출력입니다。'),
      (0x456,'켄조：조종 계통은 안전한가？'),
      (0x4bc,'로버트：공통 조종계로 교체하고 점검했습니다。 지금 상태로도 운용은 가능합니다。'),
      (0x456,'켄조：그렇다면 편입하지。 남은 개수도 계속 진행해 주게。'),
      ('command',command(0x5a,0x606))]
    vallate=[('command',background),
      (0x4bc,'로버트：발시온 개의 개수 작업이 완료됐습니다。'),
      (0x456,'켄조：이제 지난 전쟁의 손상도 모두 복구됐다는 건가？'),
      (0x4bc,'로버트：네。 동력계와 구동계를 정비하고、무장 출력 제한도 해제했습니다。'),
      (0x456,'켄조：잘됐군。 앞으로의 전투에서도 힘을 보태 줄 걸세。')]
    return {74:[(end(74)-1,'버려진 무명 회수',early)],87:[(end(87),'미수리 발시온 개 인수',valearly)],
            102:[(end(102),'무명 개수 완료',late)],104:[(end(104),'발시온 개 개수 완료',vallate)]}


def refurbishment_validation(path,blob,edits,notes):
    from validate_hidden_rewards import VM,ram as vr,REC
    vm=VM();c=vm.cpu
    with path.open('rb') as f:c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
    for e in edits:
        pc=e['offset']-0x94880+0x100000;b=bytes.fromhex(e['after']);c.mem[pc:pc+len(b)]=b
    master=u32(vr,0x59d360);save=u32(vr,0x59d364);glob=u32(vr,0x59d36c);p=0x1100000;h=0x11e800
    c.mem[p:p+len(blob[h:])]=blob[h:]
    for i,k in enumerate(range(0x18,0x8c,4)):
        q=p+u32(blob,h+k)
        for off,v in [(0,q),(4,c.read(q,4)),(8,c.read(q+4,4)),(12,c.read(q+8,4)),(16,q),(20,q+12)]:c.write(master+0x28+i*24+off,v,4)
    ut=h+u32(blob,h+0x18)
    records=notes+[dict(key=0x605,full_key=0x60c,weak_record=u16(blob,ut+12+0x605*2),full_record=u16(blob,ut+12+0x60c*2),clear_threshold=36,
      weak_stats=[7470,450,1890,6,108],full_stats=[8300,500,2100,7,120],weak_abilities=[0]*6,full_abilities=[9,10,14,19,22,0],
      weapons=[dict(damaged_key=0xf90+i,restored_key=0xfb0+i,damaged_power=x-400,restored_power=x) for i,x in enumerate((3900,4100,4900))])]
    fns=(0x1a7d40,0x1a7cc0,0x1a7b40,0x1a7c40,0x1a7bc0);checks=0
    c.write(glob+0xf5c,1,4)
    for n in records:
        for key in (n['key'],n['full_key']):
            vm.op(command(0x5a,key));slot=c.run(0x1abc50,[save,key,0,0]);assert slot>=0
            for i,prop in enumerate(range(0xd,0x11)):c.run(0x1af000,[save,prop,slot,i+1,0])
            for i in range(len(n['weapons'])):c.write(REC,i+8,4);c.run(0x1af000,[save,0xc,slot,i+3,REC])
            snapshot=bytes(c.mem[save:save+0x3b400])
            for cleared in (0,23,n['clear_threshold']-1,n['clear_threshold'],40,50):
                c.write(glob+0xf74,cleared,4);full=cleared>=n['clear_threshold'];prefix='full' if full else 'weak'
                assert [c.run(fn,[master,key]) for fn in fns]==n[prefix+'_stats'],(hex(key),cleared,'stats')
                assert [c.run(0x1a6f00,[master,key,i]) for i in range(6)]==n[prefix+'_abilities']
                for i,w in enumerate(n['weapons']):
                    c.write(REC,i,4);wk=c.run(0x1b01d0,[save,0x49,slot,REC]);expected=w['restored_key'] if full else w['damaged_key']
                    assert wk==expected,(hex(key),cleared,i,hex(wk),hex(expected))
                    assert c.run(0x1a5dc0,[master,wk])==w['restored_power' if full else 'damaged_power']
                    c.write(REC,i+8,4);assert c.run(0x1af860,[save,0xc,slot,REC])==i+3
                assert [c.run(0x1af860,[save,x,slot,0]) for x in range(0xd,0x11)]==[1,2,3,4]
                assert bytes(c.mem[save:save+0x3b400])==snapshot,'Read-only phase selection changed save'
                checks+=1
        for w in n['weapons']:
            for fn in (0x1a4a20,0x1a5720,0x1a57b0,0x1a5b40):assert c.run(fn,[master,w['damaged_key']])==c.run(fn,[master,w['restored_key']])
    # Every unrelated Unit index is byte-identical to the native accessor result.
    table=master+0x28+24;count=u32(blob,h+u32(blob,h+0x1c)+8);data=c.read(table+20,4)
    excluded={i for n in records for i in (n['weak_record'],n['full_record'])}
    for idx in range(count):
        if idx not in excluded:assert c.run(0x1a8d20,[table,idx])==data+100*idx
    for part in (0,2):
        c.write(glob+0xf5c,part,4)
        for n in records:
            for idx in (n['weak_record'],n['full_record']):assert c.run(0x1a8d20,[table,idx])==data+100*idx
    return dict(native_phase_cases=checks,unrelated_unit_indices_verified=count-len(excluded),
        existing_raw_keys_and_upgrades_preserved=True,save_reads_are_nonmutating=True,non_og2_bypass=True,
        native_fixed_weapon_selection=True,weapon_motion_cost_growth_ammo_preserved=True,live_playthrough=False)


def refurbishment(apply=False):
    import psutil
    from validate_beowulf_prototype import validate_story_blob
    from validate_hidden_rewards import ram as vr
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));previous=journal['enemy_deployment_fix'];assert previous['applied']
    assert not journal.get('refurbishment',{}).get('applied'),'Already applied'
    report=dict(applied=False,mumyou_acquire_clear=6,mumyou_restore_clear=36,valsion_acquire_clear=21,valsion_restore_clear=38,files=[])
    readable=[]
    for item in previous['files']:
        path=Path(item['path']);s=Scripts(path);edits=[];proofs=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            for base in (0x5da000,0x83f000):
                old=read(f,base,0x1a5800);new,notes=refurbishment_master(old);edits.append(dict(offset=base,before=old.hex(),after=new.hex()))
            hooks=refurbishment_hook(f,notes);edits.extend(hooks);native=refurbishment_validation(path,new,hooks,notes)
            cursor=0x9300000
            for n,scenes in refurbishment_scenes(s).items():
                at,size=s.logos[n];old=s.data[at:at+size];new,info=rebuild_beowulf_story_logo(old,scenes,speaker_context=True)
                allowed=tuple(tuple(r) for _,_,lines in scenes for who,r in lines if who=='command')
                proof=validate_story_blob(old,new,info,vr,allowed_commands=allowed)
                assert not any(read(f,MAP+cursor,len(new))),('Occupied story space',n,hex(cursor))
                edits.extend([dict(offset=MAP+cursor,before=bytes(len(new)).hex(),after=new.hex()),
                    dict(offset=MAP+0x557f800+8+n*8,before=read(f,MAP+0x557f800+8+n*8,8).hex(),after=struct.pack('<II',cursor-0x557f800,len(new)).hex())])
                proofs.append(dict(script=n,validation=proof,notes=info));cursor=(cursor+len(new)+2047)&~2047
                for _,title,lines in scenes:readable.extend(['【'+title+'】']+[str(t) for who,t in lines if who!='command']+[''])
            assert cursor<0x9400000
            # Remove only our superseded chapter30 addition. Its source LOGO is untouched.
            prior=next(x for x in journal['valcion_custom']['files'] if x['path']==str(path))
            directory=MAP+0x557f800+8+96*8;entry=next(e for e in prior['edits'] if e['offset']==directory)
            at,size=s.logos[96];assert any(bytes.fromhex(e['after'])==s.data[at:at+size] for e in prior['edits'])
            edits.append(dict(offset=directory,before=read(f,directory,8).hex(),after=entry['before']))
            original_at,original_size=struct.unpack('<II',bytes.fromhex(entry['before']));assert s.data[0x557f800+original_at:0x557f800+original_at+4]==b'LOGO'
            off=MAP+0x800+8+14*8+4;old=read(f,off,4);new=struct.pack('<I',max(u32(old),cursor-0x557e800))
            if old!=new:edits.append(dict(offset=off,before=old.hex(),after=new.hex()))
        edits.sort(key=lambda e:e['offset'])
        for a,b in zip(edits,edits[1:]):assert a['offset']+len(bytes.fromhex(a['after']))<=b['offset'],'Overlapping writes'
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=edits,masters=notes,checks=native,stories=proofs,
            phase_source='OG2 global +F74 completed chapter count, selected at Unit accessor; no roster mutation',old_30_event_removed=True))
        print(path.name,'refurbishment master/story/native phase checks passed',native,flush=True)
    journal['refurbishment']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'runtime/무명_발시온개_개수_대사.txt').write_text('\n'.join(readable),encoding='utf-8-sig')
    if not apply:return
    for item in report['files']:
        inv,target,pos=hashlib.sha256(),hashlib.sha256(),0;written=[]
        try:
            with Path(item['path']).open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert len(a)==len(b) and read(f,e['offset'],len(a))==a
                    f.seek(e['offset']);f.write(b);written.append(e)
                f.flush();os.fsync(f.fileno());f.seek(0)
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inv.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inv.update(a);target.update(b);pos+=len(b)
                while raw:=f.read(4<<20):inv.update(raw);target.update(raw)
            assert inv.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
        except Exception:
            with Path(item['path']).open('r+b') as f:
                for e in reversed(written):f.seek(e['offset']);f.write(bytes.fromhex(e['before']))
            raise
        print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
    report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')



def granzon_dialogue(old,replacements):
    """Replace strings by the native combined string index, keeping records intact."""
    out=bytearray(old);notes=[];pool=u32(old,0x4c);table=u32(old,0x44);co=u32(old,0x2c)
    for index,(guard,text) in sorted(replacements.items()):
        r=struct.unpack_from('<24I',old,co+index*96);assert r[0]==0x30
        q=pool+u32(old,table+r[2]*4);before=decode(old[q:old.index(0,q)])
        assert guard in before,(index,guard,before)
        text=text.replace('@',' ').replace(' ','　');parts=[]
        while len(text)>20:
            cut=text.rfind('　',6,21)
            if cut<0:cut=20
            parts.append(text[:cut]);text=text[cut:].lstrip('　')
        text='@'.join(parts+[text]);assert len(text.split('@'))<=3
        raw=encode(text);assert decode(raw)==text
        struct.pack_into('<I',out,table+r[2]*4,len(out)-pool);out.extend(raw+b'\0')
        notes.append(dict(record=index,string_index=r[2],speaker=r[4],before=before,after=text,encoded=raw.hex()))
    out.extend(bytes((-len(out))%4));struct.pack_into('<I',out,4,len(out));struct.pack_into('<I',out,0x6c,len(out))
    assert out[co:co+u32(old,0x28)*96]==old[co:co+u32(old,0x28)*96]
    return bytes(out),notes


def granzon_join_validation(path,blob,row,stories):
    from validate_hidden_rewards import VM,ram as vr,CTX,REC
    from r5900_scalar_check import CPU
    vm=VM();c=vm.cpu
    with path.open('rb') as f:c.mem[0x100000:0x582980]=read(f,0x94880,0x482980)
    h=0x11e800;master=u32(vr,0x59d360);save=u32(vr,0x59d364);p=0x1100000
    c.mem[p:p+len(blob[h:])]=blob[h:]
    for i,k in enumerate(range(0x18,0x8c,4)):
        q=p+u32(blob,h+k)
        for off,v in ((0,q),(4,c.read(q,4)),(8,c.read(q+4,4)),(12,c.read(q+8,4)),(16,q),(20,q+12)):c.write(master+0x28+i*24+off,v,4)
    before=bytes(c.mem[save:save+0x3b400]);assert c.run(0x1abc50,[save,0x456,0,0])==-1
    ctx=0x1700000;bundle=0x1780000;data=0x1790000;c.write(ctx+40,bundle,4)
    for off,g in ((0x2120,0x59d360),(0x2124,0x59d364),(0x212c,0x59d36c)):c.write(bundle+off,c.read(g,4),4)
    c.write(ctx+0x346d4,data,4);c.write(ctx+0x346d0,1,4);c.mem[data:data+336]=row;c.write(CTX+0x310c,ctx-0x40e00,4)
    vm.op(command(0x5e,0x27));slot=c.run(0x1abc50,[save,0x456,0,0]);pilot=c.run(0x1ab6f0,[save,0x45d,1])
    assert slot>=0 and pilot>=0 and c.run(0x1a9b70,[save,slot,1])==1 and c.run(0x1b1300,[save,slot,0])==pilot
    assert [c.run(fn,[master,0x456]) for fn in (0x1a7d40,0x1a7cc0,0x1a7b40,0x1a7c40,0x1a7bc0)]==[6500,280,2000,5,75]
    assert [c.run(0x1aca50,[save,p,slot]) for p in (0x37,0x38,0x39)]==[0,0,0]
    assert [c.run(0x1ac800,[save,p,pilot]) for p in (0xe7,0xe8,0xe9)]==[0,0,0],[c.run(0x1ac800,[save,p,pilot]) for p in (0xe7,0xe8,0xe9)]
    after=bytes(c.mem[save:save+0x3b400])
    for i in range(512):
        if i!=slot:assert before[0x6efc+i*216:0x6efc+(i+1)*216]==after[0x6efc+i*216:0x6efc+(i+1)*216]
        if i!=pilot:assert before[0x25cfc+i*92:0x25cfc+(i+1)*92]==after[0x25cfc+i*92:0x25cfc+(i+1)*92]
    vm.op(command(0x5e,0x27));assert c.run(0x1abc50,[save,0x456,0,0])==slot and c.run(0x1ab6f0,[save,0x45d,1])==pilot
    native_messages=0
    for b,notes in stories:
        cpu=CPU(vr);base=0x1800000;context=0x1600000;cpu.mem[base:base+len(b)]=b;cpu.run(0x2b5c90,[context,base])
        for note in notes:
            cpu.run(0x2baf90,[context,0,note['string_index']]);raw=bytes.fromhex(note['encoded'])
            assert cpu.mem[context+0x85a0:context+0x85a0+len(raw)]==raw;native_messages+=1
    return dict(native_roster_grant=True,permanent_unit_slot=slot,permanent_pilot_slot=pilot,pilot_boarded=True,
        duplicate_unit_and_pilot_prevented=True,other_units_and_pilots_unchanged=True,original_master_stats_preserved=True,
        native_dialogue_lookups=native_messages,live_playthrough=False)


def granzon_join(apply=False):
    import psutil
    from validate_beowulf_prototype import validate_story_blob
    from validate_hidden_rewards import ram as vr
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));prior=journal['refurbishment'];assert prior['applied']
    assert not journal.get('granzon_join',{}).get('applied'),'Already applied'
    report=dict(applied=False,part='OG2',chapter=40,unit_key=0x456,pilot_key=0x45d,files=[]);readable=[]
    replacements={
      1783:('실례','슈우：그럼、이번 싸움이 끝날 때까지 제 그랑존도 힘을 보태겠습니다。'),
      1784:('어딜','마사키：뭐！？ 네가 우리와 함께 싸우겠다고？'),
      1785:('대답','슈우：인스펙터와 섀도우미러、아인스트를 방치할 수는 없으니까요。'),
      1786:('꾸미고','마사키：그래서 갑자기 도와주겠다는 거냐？'),
      1787:('이해','슈우：목적이 같은 동안은 협력하는 편이 합리적이지 않겠습니까。'),
      1788:('인스펙터랑','슈우：그랑존의 힘은、지금 이 전쟁을 끝내는 데 쓰겠습니다。'),
      1789:('구경','마사키：수상한 짓을 하면 가만두지 않을 거야。'),
      1790:('별고','슈우：후후。 그때까지는 당신들 곁에서 싸우지요。'),
      1794:('도망','마사키：좋아。 똑똑히 지켜보겠어！'),
      1795:('안돼요','레피나：협력에 감사드립니다、시라카와 박사。'),
      1796:('！','마사키：……흥。'),
      1797:('필요','레피나：지금은 힘을 모아 이 사태를 끝내야 합니다。'),
      1798:('마사키','류네：마사키、지금은 함께 싸우자。 네가 지켜보면 되잖아？'),
      1799:('……','마사키：……알았어。'),
      1800:('그래','마사키：지금만은 믿어 주지。')}
    for item in prior['files']:
        path=Path(item['path']);s=Scripts(path);edits=[];proofs=[];stories=[]
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            wp=0x5071000;dp=wp+8+110*8;at=wp+u32(s.data,dp);size=u32(s.data,dp+4);old=s.data[at:at+size]
            count=u32(old,40);assert len(old)==44+count*336 and old[24:32].startswith(b'01046')
            assert all(u32(old,44+i*336+4)!=0x27 for i in range(count))
            sp=wp+8+124*8;source=wp+u32(s.data,sp);row=bytearray(s.data[source+44+78*336:source+44+79*336])
            assert (u32(row),u32(row,32))==(0x456,0x45d)
            for off,v in ((4,0x27),(8,0),(16,0),(20,0),(24,0),(28,1)):struct.pack_into('<I',row,off,v)
            new=bytearray(old+row);struct.pack_into('<I',new,40,count+1);dest=0x93b0000;unt_end=dest+len(new)
            assert not any(read(f,MAP+dest,len(new)))
            edits.extend([dict(offset=MAP+dest,before=bytes(len(new)).hex(),after=new.hex()),
                dict(offset=MAP+dp,before=read(f,MAP+dp,8).hex(),after=struct.pack('<II',dest-wp,len(new)).hex())])
            cursor=0x9400000
            for n,reps in ((106,replacements),(115,None)):
                at,size=s.logos[n];old=s.data[at:at+size]
                if reps is None:
                    co=u32(old,0x2c);table=u32(old,0x44);pool=u32(old,0x4c);hits=[]
                    for i,(_,r) in enumerate(s.records(n)):
                        if r[0]!=0x30:continue
                        p=pool+u32(old,table+r[2]*4);text=decode(old[p:old.index(0,p)])
                        if '슈우' in text and '움직임' in text:hits.append(i)
                    assert len(hits)==1;reps={hits[0]:('슈우','마사키：그래。 이번 사건도 끝났고……슈우 녀석도 마지막까지 힘을 빌려줬어。')}
                modified,changes=granzon_dialogue(old,reps);readable.extend([f'【OG2 {40 if n==106 else 49}화】']+[x['after'] for x in changes]+[''])
                if n==106:
                    point=next(i for i,(_,r) in reversed(list(enumerate(s.records(n)))) if r[0]==0x9c)
                    new,notes=rebuild_beowulf_story_logo(modified,[(point,'슈우와 그랑존 정식 합류',[('command',command(0x5e,0x27))])])
                    proof=validate_story_blob(modified,new,notes,vr,allowed_commands=(tuple(command(0x5e,0x27)),))
                else:new=modified;proof=dict(original_commands_preserved=u32(old,0x28),only_dialogue_pointer_and_append_changed=True)
                assert not any(read(f,MAP+cursor,len(new)))
                edits.extend([dict(offset=MAP+cursor,before=bytes(len(new)).hex(),after=new.hex()),
                    dict(offset=MAP+0x557f800+8+n*8,before=read(f,MAP+0x557f800+8+n*8,8).hex(),after=struct.pack('<II',cursor-0x557f800,len(new)).hex())])
                stories.append((new,changes));proofs.append(dict(script=n,checks=proof,replacements=changes));cursor=(cursor+len(new)+2047)&~2047
            assert cursor<0x9600000
            for slot,needed in ((13,unt_end-0x5070000),(14,cursor-0x557e800)):
                off=MAP+0x800+8+slot*8+4;before=read(f,off,4);after=struct.pack('<I',max(u32(before),needed))
                if before!=after:edits.append(dict(offset=off,before=before.hex(),after=after.hex()))
            blob=read(f,0x5da000,0x1a5800);native=granzon_join_validation(path,blob,row,stories)
        edits.sort(key=lambda x:x['offset'])
        for a,b in zip(edits,edits[1:]):assert a['offset']+len(bytes.fromhex(a['after']))<=b['offset']
        report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=edits,checks=native,stories=proofs))
        print(path.name,'Granzon permanent native recruitment and dialogue checks passed',native,flush=True)
    journal['granzon_join']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'runtime/슈우_그랑존_정식합류_대사.txt').write_text('\n'.join(readable),encoding='utf-8-sig')
    if not apply:return
    for item in report['files']:
        inverse,target,pos=hashlib.sha256(),hashlib.sha256(),0;written=[]
        try:
            with Path(item['path']).open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert len(a)==len(b) and read(f,e['offset'],len(a))==a
                    f.seek(e['offset']);f.write(b);written.append(e)
                f.flush();os.fsync(f.fileno());f.seek(0)
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inverse.update(a);target.update(b);pos+=len(b)
                while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
            assert inverse.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
        except Exception:
            with Path(item['path']).open('r+b') as f:
                for e in reversed(written):f.seek(e['offset']);f.write(bytes.fromhex(e['before']))
            raise
        print(Path(item['path']).name,'applied',item['after_sha256'],flush=True)
    report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')



def granzon_dialogue_followup(apply=False):
    import psutil
    from r5900_scalar_check import CPU
    from validate_hidden_rewards import ram as vr
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2'
    journal=json.loads(JOURNAL.read_text(encoding='utf-8'));prior=journal['granzon_join'];assert prior['applied']
    assert not journal.get('granzon_dialogue_followup',{}).get('applied'),'Already applied'
    specs={110:{119:('슈우','마사키：아아。 슈우가 손을 쓴 모양이야。'),
                121:('위해서','마사키：녀석도 우리와 싸우기로 했으니까。 방식은 여전히 마음에 안 들지만……。')},
           113:{739:('본인','웬드로：글쎄……난 당사자가 아니니까。 함께 다니는 시라카와에게 물어보게。'),
                740:('칫','마사키：칫……！ 이 싸움이 끝나면 확실히 물어봐야겠군。')}}
    report=dict(applied=False,files=[]);readable=[]
    for item in prior['files']:
        path=Path(item['path']);scripts=Scripts(path);edits=[];proof=[];cursor=0x94c0000
        with path.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==item['after_sha256']
            for n,replacements in specs.items():
                at,size=scripts.logos[n];old=scripts.data[at:at+size];new,notes=granzon_dialogue(old,replacements)
                assert not any(read(f,MAP+cursor,len(new)))
                # Execute the actual native string fetcher, including game-codec controls.
                c=CPU(vr);base,ctx=0x1800000,0x1600000;c.mem[base:base+len(new)]=new;c.run(0x2b5c90,[ctx,base])
                for msg in notes:
                    c.run(0x2baf90,[ctx,0,msg['string_index']]);raw=bytes.fromhex(msg['encoded'])
                    assert c.mem[ctx+0x85a0:ctx+0x85a0+len(raw)]==raw
                edits.extend([dict(offset=MAP+cursor,before=bytes(len(new)).hex(),after=new.hex()),
                    dict(offset=MAP+0x557f800+8+n*8,before=read(f,MAP+0x557f800+8+n*8,8).hex(),after=struct.pack('<II',cursor-0x557f800,len(new)).hex())])
                proof.append(dict(script=n,replacements=notes,native_text_lookup=True,all_original_commands_preserved=True));cursor=(cursor+len(new)+2047)&~2047
                readable.extend([f'【추가 교정 LOGO {n}】']+[m['after'] for m in notes]+[''])
            assert cursor<0x9600000
            off=MAP+0x800+8+14*8+4;before=read(f,off,4);after=struct.pack('<I',max(u32(before),cursor-0x557e800))
            if before!=after:edits.append(dict(offset=off,before=before.hex(),after=after.hex()))
        edits.sort(key=lambda e:e['offset']);report['files'].append(dict(path=str(path),before_sha256=item['after_sha256'],edits=edits,stories=proof))
    journal['granzon_dialogue_followup']=report;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    if not apply:return
    for item in report['files']:
        inverse,target,pos=hashlib.sha256(),hashlib.sha256(),0;written=[]
        try:
            with Path(item['path']).open('r+b') as f:
                for e in item['edits']:
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert len(a)==len(b) and read(f,e['offset'],len(a))==a
                    f.seek(e['offset']);f.write(b);written.append(e)
                f.flush();os.fsync(f.fileno());f.seek(0)
                for e in item['edits']:
                    while pos<e['offset']:
                        raw=f.read(min(4<<20,e['offset']-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                    a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);assert f.read(len(b))==b;inverse.update(a);target.update(b);pos+=len(b)
                while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
            assert inverse.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
        except Exception:
            with Path(item['path']).open('r+b') as f:
                for e in reversed(written):f.seek(e['offset']);f.write(bytes.fromhex(e['before']))
            raise
        print('Applied Granzon later dialogue:',item['after_sha256'],flush=True)
    report['applied']=True;JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'runtime/슈우_그랑존_정식합류_대사.txt').open('a',encoding='utf-8') as f:f.write('\n'+'\n'.join(readable))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--repair-loading',action='store_true');ap.add_argument('--balance',action='store_true');ap.add_argument('--finisher-cost',action='store_true');ap.add_argument('--clear-bonus',action='store_true');ap.add_argument('--valcion-custom',action='store_true');ap.add_argument('--legacy-recruitment',action='store_true');ap.add_argument('--weapon-cost-rebalance',action='store_true');ap.add_argument('--enemy-upgrade-plus2',action='store_true');ap.add_argument('--upgrade-report',action='store_true');ap.add_argument('--restoration',action='store_true');ap.add_argument('--enemy-deployment-fix',action='store_true');ap.add_argument('--refurbishment',action='store_true');ap.add_argument('--granzon-join',action='store_true');ap.add_argument('--granzon-dialogue',action='store_true');args=ap.parse_args()
    if args.granzon_dialogue:return granzon_dialogue_followup(args.apply)
    if args.granzon_join:return granzon_join(args.apply)
    if args.refurbishment:return refurbishment(args.apply)
    if args.enemy_deployment_fix:return enemy_deployment_fix(args.apply)
    if args.restoration:return restoration(args.apply)
    if args.enemy_upgrade_plus2:return enemy_upgrade_plus2(args.apply)
    if args.weapon_cost_rebalance:return weapon_cost_rebalance(args.apply)
    if args.upgrade_report:return upgrade_report()
    if args.legacy_recruitment:return legacy_recruitment(args.apply)
    if args.valcion_custom:return valcion_custom(args.apply)
    if args.clear_bonus:return clear_bonus(args.apply)
    if args.finisher_cost:return finisher_cost(args.apply)
    if args.balance:return balance_fix(args.apply)
    if args.repair_loading:return repair_loading(args.apply)
    if args.apply:
        import psutil
        assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2 before applying'
    result=dict(applied=False,unit_key=UNIT,pilot_key=PILOT,chapter=11,files=[])
    for name,digest in EXPECTED.items():
        path=ROOT/'build'/name
        with path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest
        edits,note,row=make_plan(path);note['spawn_validation']=validate_spawn(path,edits,row)
        result['files'].append(dict(path=str(path),before_sha256=digest,details=note,
            edits=[dict(offset=o,before=a.hex(),after=b.hex()) for o,a,b in edits]))
        print(name,'plan and native checks passed',flush=True)
    JOURNAL.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.apply:
        for item in result['files']:
            path=Path(item['path']);es=item['edits']
            try:
                with path.open('r+b') as f:
                    for e in es:
                        a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);f.seek(e['offset']);assert f.read(len(a))==a;f.seek(e['offset']);f.write(b)
                    f.flush();os.fsync(f.fileno())
                inverse=hashlib.sha256();target=hashlib.sha256();pos=0
                with path.open('rb') as f:
                    for e in es:
                        a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                        while pos<e['offset']:
                            raw=f.read(min(4<<20,e['offset']-pos));assert raw;inverse.update(raw);target.update(raw);pos+=len(raw)
                        assert f.read(len(b))==b;inverse.update(a);target.update(b);pos+=len(b)
                    while raw:=f.read(4<<20):inverse.update(raw);target.update(raw)
                assert inverse.hexdigest()==item['before_sha256'];item['after_sha256']=target.hexdigest()
            except Exception:
                with path.open('r+b') as f:
                    for e in es:f.seek(e['offset']);f.write(bytes.fromhex(e['before']))
                raise
        result['applied']=True;JOURNAL.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    text=['잉그램·R-GUN 리바레 합류 시나리오','OG2 11화 / HP8300 · 장갑2100 · 원본 무장 유지','']
    for p,title,lines in story_scenes():
        text+=['【'+title+'】','']
        for who,t in lines:
            if who=='command':text+=['[차원 균열에서 R-GUN 리바레 등장]','']
            else:text+=[t.replace('@','\n'),'']
    (ROOT/'runtime/잉그램_합류_시나리오.txt').write_text('\n'.join(text),encoding='utf-8-sig')
    print(json.dumps(dict(applied=result['applied'],files=[dict(path=x['path'],validation=x['details']['spawn_validation']) for x in result['files']]),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
