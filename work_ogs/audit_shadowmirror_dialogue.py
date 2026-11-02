"""Read-only current LOGO speaker/name/context audit. Never scans stale relocated pools.

Follows executed opcode30 string IDs and records both caption and speaker key.
Native Korean baseline is evidence; intentionally rewritten dialogue is NOT
automatically restored by the name-count heuristics.
"""
from pathlib import Path
import collections,json,re,struct
from build_hidden_rewards import Scripts,MAP,u32
from build_beowulf_prototype import Archive,read,u16,decode,ROOT,SOURCE,OUT

BASE=ROOT.parent/'슈퍼 로봇 대전 OG (K).iso'
TARGETS=('액셀','라미아','레몬')

def body(t):
    return re.split('[：:（(]',t,maxsplit=1)[-1]

def sp(t):
    return re.split('[：:（(]',t,maxsplit=1)[0]

def references(s,n):
    at,size=s.logos[n];nc=u32(s.data,at+0x40);ts=s.texts(n);refs=collections.defaultdict(list)
    for countfield,offsetfield,kind in ((0x20,0x24,'prefix'),(0x28,0x2c,'main')):
        count=u32(s.data,at+countfield);off=u32(s.data,at+offsetfield)
        for i in range(count):
            r=struct.unpack_from('<24I',s.data,at+off+i*96)
            if r[0]!=0x30:continue
            k=r[2]-nc
            if 0<=k<len(ts):refs[k].append(dict(kind=kind,record=i,speaker=r[4],expression=r[5],history=r[1]))
    return ts,refs

def pilot_names(path):
    with path.open('rb') as f:b=read(f,0x5da000,0x1a5800)
    h=0x11e800;pt=h+u32(b,h+0x28);plot=h+u32(b,h+0x2c)+12;s=h+u32(b,h+0x80);out={}
    for key in range(2048):
        idx=u16(b,pt+12+key*2)
        if idx==65535:continue
        sid=u16(b,plot+idx*148+4)
        if sid>=u32(b,s+8):continue
        p=s+u32(b,s+12+sid*4)
        try:out[key]=decode(b[p:b.index(0,p)])
        except Exception:pass
    return out

def analyse():
    old=Scripts(BASE);cur=Scripts(OUT);prod=Scripts(SOURCE);names=pilot_names(OUT)
    candidates=[];related=[];mismatches=[];dialogues=0;allstrings=0
    for n in range(len(cur.logos)):
        ot,orefs=references(old,n);ts,refs=references(cur,n);pt,prefs=references(prod,n);allstrings+=len(ts)
        for k,rr in sorted(refs.items()):
            dialogues+=len(rr);at,t=ts[k];before=ot[k][1] if k<len(ot) else None
            if not any(z in t or (before and z in before) for z in TARGETS):continue
            entry=dict(script=n,text_index=k,current_map_offset=at,baseline=before,current=t,
                production=pt[k][1] if k<len(pt) else None,references=rr)
            related.append(entry)
            reasons=[]
            if before:
                expected=body(before).replace('액셀','TEMPAXEL').replace('라미아','액셀').replace('TEMPAXEL','라미아')
                for who in TARGETS:
                    if expected.count(who)!=body(t).count(who):reasons.append(f'{who} 본문 지칭 변화')
                if body(before).count('레몬')==0 and '레몬' in body(t) and ('액셀' in body(before) or '라미아' in body(before)):
                    reasons.append('원본 역할 대상이 레몬으로 바뀜: 문맥 우선 확인')
            for r in rr:
                expected=names.get(r['speaker'])
                if expected in TARGETS and sp(t) in TARGETS and expected!=sp(t):
                    mismatches.append(dict(**entry,expected_speaker=expected,caption=sp(t)))
            if reasons:candidates.append(dict(**entry,reasons=reasons))
    # Complete scene, not only strings matching the screenshots.
    scene=[]
    for n in range(len(cur.logos)):
        ts,refs=references(cur,n);ot,_=references(old,n);pt,_=references(prod,n)
        hits=[i for i,(at,t) in enumerate(ts) if '명령보다' in t and '판단' in t]
        for hit in hits:
            for k in range(max(0,hit-41),min(len(ts),hit+24)):
                if k not in refs:continue
                scene.append(dict(script=n,text_index=k,baseline=ot[k][1] if k<len(ot) else None,
                    current=ts[k][1],production=pt[k][1] if k<len(pt) else None,references=refs[k]))
    data=dict(read_only=True,baseline=str(BASE),production=str(SOURCE),test=str(OUT),
        scripts=len(cur.logos),decoded_string_table_entries=allstrings,executed_dialogue_references=dialogues,
        related_dialogues=len(related),candidate_count=len(candidates),speaker_caption_mismatch_count=len(mismatches),
        candidates=candidates,speaker_caption_mismatches=mismatches,episode47_scene=scene,
        all_related_dialogue=related,heuristics_are_not_automatic_corrections=True)
    report=ROOT/'runtime/shadowmirror_dialogue_audit.json';report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# シャドウミラー 대사 문맥 검토','',
        f'실행 중인 LOGO {data["scripts"]}개, 대사 참조 {dialogues}개를 추적했습니다. 재배치 전의 폐기된 문자열은 제외했습니다.',
        f'관련 대사 {len(related)}개, 지칭 변화 후보 {len(candidates)}개, 화자 표기 불일치 {len(mismatches)}개.',
        '후보는 자동 오류 판정이 아닙니다. 기존 의도적인 대사 교정은 보존하고 문맥으로 판단합니다.','',
        '## 47화 W16 장면 전체','']
    for e in scene:
        lines.extend([f'### LOGO {e["script"]} / 문자열 {e["text_index"]}',
            '- 원본: '+str(e['baseline']).replace('@',' / '),'- 현재: '+e['current'].replace('@',' / '),
            '- 화자 키: '+', '.join(hex(r['speaker']) for r in e['references']),''])
    lines.extend(['## 전 화 지칭 변화 검토 후보',''])
    for e in candidates:
        lines.extend([f'### LOGO {e["script"]} / 문자열 {e["text_index"]}',
            '- 사유: '+', '.join(e['reasons']),'- 원본: '+str(e['baseline']).replace('@',' / '),
            '- 현재: '+e['current'].replace('@',' / '),''])
    (ROOT/'SHADOWMIRROR_DIALOGUE_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in data.items() if k not in ('candidates','speaker_caption_mismatches','episode47_scene','all_related_dialogue')},ensure_ascii=False,indent=2))

# Explicit scene corrections. Speaker keys, commands, pointers and allocations
# remain untouched; these are not global name substitutions.
CORRECTIONS={
 (112,200):'라미아：드디어……@결전의　때가　왔군。',
 (112,202):'에키드나：뭐？@레몬님께　지령을　받았다。@내　역할은　너를　지키는……',
 (112,203):'라미아：아니、화이트스타의@방위에　전념해라。@여기서　밀리면　모든　게　끝난다。',
 (112,205):'라미아：나는　지지　않는다。@하지만　만일의　사태에도@대비해야　한다。……이해해라。',
 (112,207):'쿄스케：라미아、@여기서　결착을　내겠다……！',
 (112,208):'라미아：쓰러질　건　네놈이다。@이번에도　누군가　구해　줄　거라@생각하지　마라！',
 (112,218):'라미아：큭！@내가　밀리다니！',
 (112,219):'쿄스케：그　틈을@놓치지　않는다！',
 (112,220):'라미아：쿄스케……！',
 (112,221):'쿄스케：승부는　났다、@라미아！',
 (112,222):'에키드나：라미아！',
 (112,225):'류네：저녀석、@라미아를　감쌌어！',
 (112,228):'에키드나：내　역할은……@너를……생환시키는……@것이다、라미아…',
 (112,229):'라미아：그건　레몬님의　지령이다！@나는　새로운　지령을　전했을　텐데！',
 (112,232):'에키드나：레몬님이……@슬퍼하신다……',
 (112,239):'에키드나：라미아……@어서……철수해라。@작전을　성공시키기　위해서도……',
 (112,242):'에키드나：정말……미안하다……',
 (112,243):'라미아：……철수하겠다。@네가　말한　대로。',
 (112,244):'에키드나：……아아、라미아……@고맙다……',
 (112,262):'라미아：자기　의지로@나를　지킨　건가……',
 (113,170):'액셀：Ｗ１６도　스스로@라미아를　지켰다……！',
 (113,183):'액셀（Ｗ１６은　스스로　라미아를　지켰다。@　Ｗ１７도　마지막엔　선택했다。@　둘　다　인형은　아니었어……）',
}

def correct_scene(apply=False):
    import hashlib
    from ogs_korean_codec import encode
    evidence=json.loads((ROOT/'runtime/shadowmirror_dialogue_audit.json').read_text(encoding='utf-8'))
    guards={(e['script'],e['text_index']):e for e in evidence['all_related_dialogue']+evidence['episode47_scene']}
    plans=[]
    for path,column in ((OUT,'current'),(SOURCE,'production')):
        s=Scripts(path);edits=[]
        for (n,k),new in CORRECTIONS.items():
            ts,refs=references(s,n);at,old=ts[k]
            assert k in refs,(n,k,'unreferenced')
            if old==new:continue
            assert old==guards[n,k][column],(path,n,k,'unexpected text',old)
            raw=encode(old);encoded=encode(new)
            # Consume only explicitly zero-filled padding, never the next slot.
            end=at+len(raw)
            stop=end
            while s.data[stop]==0:stop+=1
            pointers=[p for p,t in ts if p>at]
            limit=min([stop-1]+pointers)
            capacity=limit-at
            assert len(encoded)<=capacity,(n,k,len(encoded),capacity)
            width=max(len(raw),len(encoded))+1
            before=bytes(s.data[at:at+width]);after=encoded+b'\0'*(width-len(encoded))
            assert decode(encoded)==new,(n,k,'codec round trip')
            edits.append(dict(script=n,text_index=k,offset=MAP+at,before=before.hex(),after=after.hex(),old=old,new=new))
        plans.append(dict(path=str(path),edits=edits))
    # Plan both ISOs completely before either is written.
    report=ROOT/'runtime/shadowmirror_dialogue_correction.json'
    if not apply:
        print(json.dumps([dict(path=p['path'],changes=len(p['edits'])) for p in plans],ensure_ascii=False));return
    import subprocess
    running=subprocess.run(['powershell','-NoProfile','-Command','@(Get-Process pcsx2* -ErrorAction SilentlyContinue).Count'],capture_output=True,text=True,check=True)
    assert running.stdout.strip()=='0','PCSX2 must be closed before applying'
    def digest(path,restore=()):
        h=hashlib.sha256()
        with path.open('rb') as f:
            off=0
            while b:=f.read(8*1024*1024):
                b=bytearray(b)
                for e in restore:
                    p=e['offset'];raw=bytes.fromhex(e['before']);lo=max(off,p);hi=min(off+len(b),p+len(raw))
                    if lo<hi:b[lo-off:hi-off]=raw[lo-p:hi-p]
                h.update(b);off+=len(b)
        return h.hexdigest()
    for plan in plans:
        path=Path(plan['path']);plan['sha256_before']=digest(path)
    report.write_text(json.dumps(dict(status='prepared',plans=plans),ensure_ascii=False,indent=2),encoding='utf-8')
    for plan in plans:
        path=Path(plan['path'])
        with path.open('r+b') as f:
            for e in plan['edits']:
                f.seek(e['offset']);assert f.read(len(bytes.fromhex(e['before'])))==bytes.fromhex(e['before'])
            for e in plan['edits']:
                f.seek(e['offset']);f.write(bytes.fromhex(e['after']))
            f.flush()
        check=Scripts(path)
        for key,new in CORRECTIONS.items():assert check.texts(key[0])[key[1]][1]==new
        assert digest(path,plan['edits'])==plan['sha256_before'],'Unexpected unrelated ISO changes'
        plan['sha256_after']=digest(path)
        plan['verified_only_planned_bytes_changed']=True
    report.write_text(json.dumps(dict(status='applied_and_verified',plans=plans),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([dict(path=p['path'],changes=len(p['edits']),sha256=p['sha256_after']) for p in plans],ensure_ascii=False,indent=2))

HANGAR_SOULGAIN={
 503:'류세이：아、그거！@나도　신경쓰이더라、@그　콧수염　달린　로봇！',
 507:'류세이：저　늠름한　콧수염！@주먹으로　밀어붙이는　것도@정말　멋지더라！',
 508:'라투니（콧수염……@　그런　게　취향인　건가……）',
 509:'류세이：Ｒ－３에도　저런　수염을@달면、좀　더　위엄이　생길　텐데……',
 510:'아야：어～라、위엄이　없어서@정말　미안하네요。',
 512:'비렛타：……그　수염에@무슨　특별한　기능이라도　있나？',
 513:'쿄스케：그건　모르겠습니다만、@이스루기　중공의　시작기입니다。@기체명은　소울게인입니다。',
 514:'로버트：이스루기의？@저런　무투파　기체도　만들었나……',
 517:'엑셀렌：기체의　콧수염과는　달리、@파일럿은　수염　없는　미남이에용。',
}


def correct_soulgain_hangar(apply=False):
    import hashlib,os,psutil
    from ogs_korean_codec import encode
    from r5900_scalar_check import CPU
    expected={'SRWOGS_K.iso':'22788c87e3c1933a9aa621657c181b644d3f877efe5a9d1c4abc68c2c9e68e2b',
      'SRWOGS_BEOWULF_TEST.iso':'9f17e5372d3fc6b3d233708b6e5b98893010cb64a702c1c080769c7e2e98827d'}
    if apply:assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close PCSX2 before applying'
    plans=[];ram=(ROOT/'runtime/beowulf/current_user_ram.bin').read_bytes()
    for name,digest in expected.items():
        path=ROOT/'build'/name
        with path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest
        s=Scripts(path);at,size=s.logos[79];old=bytes(s.data[at:at+size]);b=bytearray(old);ts,refs=references(s,79);changes=[]
        assert '예쁜' in ts[503][1] and '날개' in ts[507][1] and '스커트' in ts[508][1]
        assert '발시오네' in ts[512][1] and '소울게인' in ts[513][1]
        for key,text in HANGAR_SOULGAIN.items():
            assert key in refs and sp(text)==sp(ts[key][1])
            assert len(text.split('@'))<=3 and all(len(x)<=20 for x in text.split('@')),(key,text)
            enc=encode(text);assert decode(enc)==text
            struct.pack_into('<I',b,u32(b,0x54)+key*4,len(b)-u32(b,0x4c));b.extend(enc+b'\0')
            changes.append(dict(text_index=key,before=ts[key][1],after=text))
        b.extend(bytes((-len(b))%4));struct.pack_into('<I',b,4,len(b));struct.pack_into('<I',b,0x6c,len(b))
        # No command, branch, event descriptor, history or Japanese pointer moves.
        normalized=bytearray(b[:len(old)]);normalized[4:8]=old[4:8];normalized[0x6c:0x70]=old[0x6c:0x70]
        for key in HANGAR_SOULGAIN:
            p=u32(old,0x54)+key*4;normalized[p:p+4]=old[p:p+4]
        assert normalized==old
        assert not any(s.data[at+size:at+len(b)]),'No verified space to grow LOGO'
        c=CPU(ram);ctx,base=0x1600000,0x1800000
        c.mem[base:base+len(b)]=b;c.run(0x2b5c90,[ctx,base]);nc=u32(b,0x40)
        for key,text in HANGAR_SOULGAIN.items():
            c.run(0x2baf90,[ctx,0,nc+key]);enc=encode(text)
            assert bytes(c.mem[ctx+0x85a0:ctx+0x85a0+len(enc)])==enc
        edits=[]
        with path.open('rb') as f:
            edits.append(dict(offset=MAP+at,before=read(f,MAP+at,len(b)).hex(),after=b.hex()))
            off=MAP+0x557f800+12+79*8;edits.append(dict(offset=off,before=read(f,off,4).hex(),after=struct.pack('<I',len(b)).hex()))
            off=MAP+0x800+8+14*8+4;before=read(f,off,4);span=max(u32(before,0),at+len(b)-0x557e800)
            if span!=u32(before,0):edits.append(dict(offset=off,before=before.hex(),after=struct.pack('<I',span).hex()))
        edits.sort(key=lambda e:e['offset'])
        plans.append(dict(path=str(path),before_sha256=digest,changes=changes,edits=edits,native_text_checks=9,
            command_and_event_bytes_unchanged=True,ingram_join_preserved=True))
    report=dict(applied=False,chapter=11,script=79,plans=plans)
    journal=ROOT/'runtime/soulgain_hangar_dialogue.json';journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        for plan in plans:
            path=Path(plan['path'])
            try:
                with path.open('r+b') as f:
                    for e in plan['edits']:
                        a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after']);f.seek(e['offset']);assert f.read(len(a))==a;f.seek(e['offset']);f.write(b)
                    f.flush();os.fsync(f.fileno())
                inverse=hashlib.sha256();actual=hashlib.sha256();pos=0
                with path.open('rb') as f:
                    for e in plan['edits']:
                        a,b=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                        while pos<e['offset']:
                            raw=f.read(min(4<<20,e['offset']-pos));assert raw;inverse.update(raw);actual.update(raw);pos+=len(raw)
                        assert f.read(len(b))==b;inverse.update(a);actual.update(b);pos+=len(b)
                    while raw:=f.read(4<<20):inverse.update(raw);actual.update(raw)
                assert inverse.hexdigest()==plan['before_sha256'];plan['after_sha256']=actual.hexdigest()
                check=Scripts(path)
                for key,text in HANGAR_SOULGAIN.items():assert check.texts(79)[key][1]==text
            except Exception:
                with path.open('r+b') as f:
                    for e in plan['edits']:f.seek(e['offset']);f.write(bytes.fromhex(e['before']))
                raise
        report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    text=['11화 격납고 대화 — 소울게인에 맞춘 교정','']
    for e in plans[0]['changes']:text+=['기존: '+e['before'].replace('　',' ').replace('@',' / '),'수정: '+e['after'].replace('　',' ').replace('@',' / '),'']
    (ROOT/'runtime/11화_소울게인_격납고_대사수정.txt').write_text('\n'.join(text),encoding='utf-8-sig')
    print(json.dumps(dict(applied=report['applied'],files=[dict(path=x['path'],changes=len(x['changes']),sha256=x.get('after_sha256')) for x in plans]),ensure_ascii=False,indent=2))


if __name__=='__main__':
    import sys
    if '--soulgain-hangar' in sys.argv:correct_soulgain_hangar('--apply' in sys.argv)
    elif '--apply-scene' in sys.argv:correct_scene(True)
    elif '--plan-scene' in sys.argv:correct_scene(False)
    else:analyse()
