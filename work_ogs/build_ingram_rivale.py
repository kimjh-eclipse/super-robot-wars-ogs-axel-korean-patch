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


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--repair-loading',action='store_true');ap.add_argument('--balance',action='store_true');ap.add_argument('--finisher-cost',action='store_true');ap.add_argument('--clear-bonus',action='store_true');ap.add_argument('--valcion-custom',action='store_true');args=ap.parse_args()
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
