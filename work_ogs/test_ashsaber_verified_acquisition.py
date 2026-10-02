"""Offline execution tests using actual game functions and copied EE memory.

No process memory, ISO, memory card, or .p2s file is edited by these tests.
"""
import json
from audit_ashsaber_keys import STATE, ROOT, load_ram, u16, u32
from build_ashsaber_verified_acquisition import patches, iso_at, SOUL, ASH
from r5900_scalar_check import CPU

def owned(c,save):
    return [i for i in range(512) if c.read(save+0x3B2FC+i//32*4,4)&(1<<(i%32))]
def records(c,save):
    return {i:bytes(c.mem[save+0x6EFC+i*0xD8:save+0x6EFC+(i+1)*0xD8]) for i in owned(c,save)}
def search(c,s,key):return c.run(0x1ABC50,[s,key,1,0])
def menu(c,s):
    c.r[17]=s;c.r[19]=0x5C8610
    return c.run(0x431778,[0x5C8610+0x2C260],stop=0x431780)
def clear_owned(c,s,i):
    at=s+0x3B2FC+i//32*4;c.write(at,c.read(at,4)&~(1<<(i%32)),4)

def main():
    ram=bytearray(load_ram(STATE));s=u32(ram,0x59D364)
    unit=ram.find(b'Unit',0xB00000)+12
    assert u16(ram,unit+0x3B*100+0x22) in (0x201,0xFFFF)
    ram[unit+0x3B*100+0x22:unit+0x3B*100+0x24]=b'\xff\xff'
    for label,off,old,new in patches():
        if off<0x500000:
            va=off-iso_at(0);ram[va:va+len(new)]=new
    results=[]
    c=CPU(ram)
    assert search(c,s,SOUL)>=0 and search(c,s,ASH)==-1
    before=records(c,s)
    menu(c,s);ash=search(c,s,ASH)
    assert ash>=0
    assert c.run(0x1A9B70,[s,ash,1])==1,'allocated but excluded by affiliation gate'
    assert c.run(0x1AF860,[s,2,ash,0])==1
    after=records(c,s)
    assert set(after)-set(before)=={ash}
    assert all(after[k]==v for k,v in before.items()),'existing unit changed'
    assert c.run(0x1B01D0,[s,0x34,ash])==0xFFFF
    gates={hex(p):c.run(0x1ACA50,[s,p,ash]) for p in (0x37,0x38,0x39,0x59)}
    assert gates=={'0x37':0,'0x38':0,'0x39':0,'0x59':65535}
    pilotmask=c.run(0x1AC800,[s,0xF2,0xA])
    assert pilotmask==0x0201 and pilotmask&0xFFFF
    menu(c,s)
    assert records(c,s)==after,'duplicate creation or unit mutation on re-entry'
    results.append({'test':'post35 menu backfill and repeat','ash_slot':ash,'result':'PASS','original_units_unchanged':len(before),'ownership_and_affiliation_gate':1,'candidate_gates':gates,'axel_pilot_mask':pilotmask})

    c=CPU(ram);clear_owned(c,s,search(c,s,SOUL));before=records(c,s)
    menu(c,s)
    assert search(c,s,ASH)==-1 and records(c,s)==before
    results.append({'test':'no returned Soulgain means no grant','result':'PASS'})

    c=CPU(ram);clear_owned(c,s,search(c,s,SOUL));before=records(c,s)
    soul=c.run(0x1B2070,[s,SOUL,0]);ash=search(c,s,ASH)
    assert soul>=0 and ash>=0 and soul!=ash
    assert c.run(0x1A9B70,[s,ash,1])==1
    assert search(c,s,SOUL)==soul,'nested allocator corrupted return value'
    after=records(c,s)
    assert set(after)-set(before)=={soul,ash}
    assert all(after[k]==v for k,v in before.items())
    results.append({'test':'return event creates both; original return address/value preserved','soul_slot':soul,'ash_slot':ash,'result':'PASS'})

    c=CPU(ram);before=records(c,s)
    ash=c.run(0x1B2070,[s,ASH,0])
    assert set(records(c,s))-set(before)=={ash}
    assert c.run(0x1A9B70,[s,ash,1])==0
    menu(c,s)
    assert c.run(0x1A9B70,[s,ash,1])==1
    assert set(records(c,s))-set(before)=={ash}
    results.append({'test':'already-owned Ashsaber suppresses companion duplicate','result':'PASS'})

    c=CPU(ram)
    for i in range(4):c.write(s+0x3B2FC+i*4,0xFFFFFFFF,4)
    before=records(c,s);menu(c,s)
    assert search(c,s,ASH)==-1 and records(c,s)==before
    results.append({'test':'full allied roster fails without deleting units','result':'PASS'})
    report={'state':str(STATE),'save_base':hex(s),'method':'scalar R5900 execution of real game functions; no stubs','results':results,'live_verified':False}
    (ROOT/'runtime/ashsaber_offline_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
