"""Local guarded fix for duplicated Ouka, Wodan speech and overwritten conversion trampoline."""
from pathlib import Path
import struct,json,hashlib,os
from build_hidden_rewards import ISO,ROOT,MAP,Scripts,command,u32
from build_beowulf_prototype import Asm,Archive,Plan,read,u16
from build_ingram_rivale import trombe_coexist_code
from validate_hidden_rewards import load_ram,VM,CTX,REC
from r5900_scalar_check import CPU
ART=ROOT/'runtime/mobile_bug_20261121'
STATE=ART/'sstates/SLPS-25733 (0F622503).00.p2s'
def pack(words):return struct.pack('<%dI'%len(words),*words)
def J(pc,link=False):return (3 if link else 2)<<26|pc>>2
def initializer(start,end,base,second=False):
 a=Asm(start);a.i(15,0,8,0x54);a.i(9,8,8,base-0x540000);a.i(9,0,9,15)
 a.label('loop');a.i(0x39,8,2,0);a.i(0x39,8,1,4);a.i(0x39,8,0,8);a.i(9,8,8,16);a.i(9,9,9,-1);a.branch(7,9,0,'loop');a.emit(0)
 a.i(0x39,8,2,0);a.i(0x39,8,1,4)
 for r in ((8,9,10,2,3) if second else (8,9,10)):a.i(15,0,r,0x54)
 a.jump(end);a.emit(0);return a.data()
def relocated_trombe(target):
 old=trombe_coexist_code(target);locations={}
 for pc,data in old:
  for i in range(0,len(data),4):
   if pc==0x49c800:new=0x200558+i if i<280 else 0x20098c+i-280
   else:new={0x49ca60:0x2009f4,0x49cb00:0x200a60,0x49cbc0:0x200678}[pc]+i
   locations[pc+i]=new
 out={0x200514:bytearray(initializer(0x200514,0x20068c,0x538df4)),0x200940:bytearray(initializer(0x200940,0x200abc,0x539044,True))}
 assert len(out[0x200514])==68 and len(out[0x200940])==76
 words={}
 for pc,data in old:
  for i,w in enumerate(struct.unpack('<%dI'%(len(data)//4),data)):
   op=w>>26;at=pc+i*4;new=locations[at]
   if op in (2,3):
    dest=(at+4)&0xf0000000|(w&0x3ffffff)<<2
    if dest in locations:w=(w&0xfc000000)|(locations[dest]>>2)
   elif op in (1,4,5,6,7,20,21,22,23):
    imm=w&65535;dest=at+4+((imm-65536 if imm&32768 else imm)*4)
    assert dest in locations
    delta=(locations[dest]-new-4)//4;assert -32768<=delta<32768;w=(w&0xffff0000)|(delta&65535)
   words[new]=w
 words[0x200670]=J(0x20098c);words[0x200674]=0
 for start,end in ((0x200514,0x20068c),(0x200940,0x200abc)):
  result=bytearray(end-start);result[:len(out[start])]=out[start]
  for at,w in words.items():
   if start<=at<end:struct.pack_into('<I',result,at-start,w)
  out[start]=bytes(result)
 return out

def allocation_code():
 # Keep the existing startup initializer and extend only its reserved wrappers.
 start=0x20042c;a=Asm(start)
 a.i(9,0,2,0x601);a.branch(4,5,2,'match');a.emit(0);a.i(9,0,2,0x4e4);a.branch(5,5,2,'original');a.emit(0)
 a.label('match');a.i(9,29,29,-0x20);a.i(0x3f,29,31,0x10);a.i(0x3f,29,4,0);a.i(0x3f,29,5,0x18)
 a.jump(0x1abc50,True);a.move(7,0);a.branch(1,2,0,'allocate');a.i(0x37,29,4,0)
 a.i(0x3f,29,2,8);a.move(5,2);a.jump(0x1b1370,True);a.move(6,0);a.i(0x37,29,2,8);a.branch(4,0,0,'return');a.emit(0)
 a.label('allocate');a.i(0x37,29,5,0x18);a.jump(0x1b2070,True);a.move(6,0)
 a.label('return');a.i(0x37,29,31,0x10);a.emit(0x03e00008);a.i(9,29,29,0x20)
 a.label('original');a.jump(0x1b2070);a.emit(0)
 unit=a.data();pilotpc=start+len(unit);a=Asm(pilotpc)
 a.i(9,0,2,0x602);a.branch(4,5,2,'match');a.emit(0);a.i(9,0,2,0x43a);a.branch(5,5,2,'original');a.emit(0)
 a.label('match');a.i(9,29,29,-0x20);a.i(0x3f,29,31,0x10);a.i(0x3f,29,4,0);a.i(0x3f,29,5,8)
 a.jump(0x1ab6f0,True);a.i(9,0,6,1);a.branch(1,2,1,'return');a.i(0x37,29,4,0)
 a.i(0x37,29,5,8);a.jump(0x1b1fd0,True);a.move(6,0)
 a.label('return');a.i(0x37,29,31,0x10);a.emit(0x03e00008);a.i(9,29,29,0x20)
 a.label('original');a.jump(0x1b1fd0);a.emit(0)
 data=unit+a.data();assert start+len(data)<=0x200514,(len(data),hex(start+len(data)))
 return start,pilotpc,data.ljust(0x200514-start,b'\0')

def cleanup_block():
 start,end=0x1feea0,0x1ff294;a=Asm(start)
 a.i(15,0,8,0x54);a.i(9,8,8,-0x7f38);a.i(0x39,8,1,0);a.i(0x39,8,0,4);a.i(9,8,8,12);a.i(9,0,9,41)
 a.label('loop');a.i(0x39,8,2,0);a.i(0x39,8,1,4);a.i(0x39,8,0,8);a.i(9,8,8,16);a.i(9,9,9,-1);a.branch(7,9,0,'loop');a.emit(0)
 a.i(0x39,8,2,0);a.i(0x39,8,1,4)
 for r in (8,9,10):a.i(15,0,r,0x54)
 a.jump(end);a.emit(0);init=a.data();assert len(init)==80
 cleanup=start+len(init);a=Asm(cleanup);a.i(9,29,29,-0x70)
 for i,r in enumerate(range(16,22)):a.i(0x1f,29,r,i*16)
 a.i(0x3f,29,31,0x60);a.i(15,0,2,0x5a);a.i(0x23,2,3,-0x2c94);a.i(0x23,3,3,0xf5c);a.i(9,0,2,1);a.branch(5,3,2,'exit');a.emit(0)
 a.i(15,0,2,0x5a);a.i(0x23,2,16,-0x2c9c)
 a.move(4,16);a.i(9,0,5,0x4e4);a.move(6,0);a.jump(0x1abc50,True);a.move(7,0);a.branch(1,2,0,'pilots');a.move(17,2)
 a.move(4,16);a.i(9,0,5,0x4e4);a.move(6,0);a.jump(0x1abc50,True);a.i(9,17,7,1);a.branch(1,2,0,'pilots');a.move(18,2)
 a.move(4,16);a.move(5,18);a.jump(0x1a9b70,True);a.i(9,0,6,1);a.branch(4,2,0,'pilots');a.emit(0)
 a.move(21,0);a.label('partcheck');a.i(0x2b,29,21,0x68);a.move(4,16);a.i(9,0,5,6);a.move(6,18);a.jump(0x1af860,True);a.i(9,29,7,0x68);a.branch(5,2,0,'pilots');a.emit(0);a.i(9,21,21,1);a.i(10,21,2,4);a.branch(5,2,0,'partcheck');a.emit(0)
 def ptr(rd,idx):
  a.emit(idx<<16|2<<11|3<<6);a.emit(2<<21|idx<<16|3<<11|0x21);a.emit(3<<16|2<<11|2<<6);a.emit(2<<21|3<<16|2<<11|0x23);a.emit(2<<16|2<<11|3<<6);a.emit(2<<21|16<<16|rd<<11|0x21);a.i(9,rd,rd,0x6efc)
 ptr(19,17);ptr(20,18);a.move(21,0)
 a.label('compare');a.i(9,0,2,2);a.branch(4,21,2,'next');a.emit(0);a.i(9,0,2,110);a.branch(4,21,2,'next');a.emit(0)
 a.i(0x25,19,2,0);a.i(0x25,20,3,0);a.branch(5,2,3,'pilots');a.emit(0)
 a.label('next');a.i(9,19,19,2);a.i(9,20,20,2);a.i(9,21,21,2);a.i(10,21,2,216);a.branch(5,2,0,'compare');a.emit(0)
 a.move(4,16);a.move(5,18);a.jump(0x1b1370,True);a.move(6,0)
 a.jump(0x1d0a00,True);a.i(9,20,4,-216)
 a.emit(18<<16|2<<11|5<<6|2);a.emit(2<<16|2<<11|2<<6);a.i(15,0,3,4);a.emit(3<<21|16<<16|3<<11|0x21);a.emit(3<<21|2<<16|3<<11|0x21);a.i(0x23,3,2,-0x4d04)
 a.i(12,18,4,31);a.i(9,0,5,1);a.emit(4<<21|5<<16|5<<11|4);a.emit(5<<21|5<<11|0x27);a.emit(2<<21|5<<16|2<<11|0x24);a.i(0x2b,3,2,-0x4d04)
 a.label('pilots')
 a.move(4,16);a.i(9,0,5,0x43a);a.jump(0x1ab6f0,True);a.i(9,0,6,1);a.branch(1,2,0,'exit');a.i(9,2,18,1)
 a.emit(18<<16|2<<11|1<<6);a.emit(2<<21|18<<16|2<<11|0x21);a.emit(2<<16|2<<11|3<<6);a.emit(2<<21|18<<16|2<<11|0x23);a.emit(2<<16|2<<11|2<<6);a.emit(2<<21|16<<16|19<<11|0x21);a.i(15,0,3,2);a.i(13,3,3,0x5cfc);a.emit(19<<21|3<<16|19<<11|0x21)
 a.label('pilotloop');a.i(10,18,2,192);a.branch(4,2,0,'exit');a.emit(0)
 a.i(0x25,19,2,0);a.i(9,0,3,0x43a);a.branch(5,2,3,'pilotnext');a.emit(0)
 a.i(0x25,19,2,6);a.branch(5,2,0,'pilotnext');a.emit(0)
 a.move(4,16);a.jump(0x1b12a0,True);a.move(5,18);a.branch(1,2,1,'pilotnext');a.emit(0)
 a.jump(0x1d37d0,True);a.move(4,19)
 a.emit(18<<16|2<<11|5<<6|2);a.emit(2<<16|2<<11|2<<6);a.i(15,0,3,4);a.emit(3<<21|16<<16|3<<11|0x21);a.emit(3<<21|2<<16|3<<11|0x21);a.i(0x23,3,2,-0x4cc4)
 a.i(12,18,4,31);a.i(9,0,5,1);a.emit(4<<21|5<<16|5<<11|4);a.emit(5<<21|5<<11|0x27);a.emit(2<<21|5<<16|2<<11|0x24);a.i(0x2b,3,2,-0x4cc4)
 a.label('pilotnext');a.i(9,18,18,1);a.branch(4,0,0,'pilotloop');a.i(9,19,19,92)
 a.label('exit')
 for i,r in enumerate(range(16,22)):a.i(0x1e,29,r,i*16)
 a.i(0x37,29,31,0x60);a.emit(0x03e00008);a.i(9,29,29,0x70);code=a.data()
 wrapper=cleanup+len(code);a=Asm(wrapper);a.i(9,29,29,-0x50)
 for i,r in enumerate(range(4,8)):a.i(0x1f,29,r,i*16)
 a.i(0x3f,29,31,0x40);a.jump(cleanup,True);a.emit(0)
 for i,r in enumerate(range(4,8)):a.i(0x1e,29,r,i*16)
 a.i(0x37,29,31,0x40);a.i(9,29,29,0x50);a.jump(0x49b800);a.emit(0)
 result=init+code+a.data();assert len(result)<=end-start
 return start,result.ljust(end-start,b'\0'),cleanup,wrapper

def build(path):
 with path.open('rb') as f:
  p=Plan(f);elf=read(f,0x94880,0x482980);target=0x49b800
  a=u32(elf,0x431778-0x100000);assert (a&0x3ffffff)<<2==0x49cb00
  oldmeta=json.loads((ROOT/'runtime/trombe_coexist_20261119.json').read_text(encoding='utf-8'))
  olditem=next(x for x in oldmeta['files'] if Path(x['path']).name==path.name)
  # Return runtime data slots to their pre-patch bytes in the ISO only.
  for e in olditem['edits']:
   at=e['offset']-0x94880+0x100000
   assert read(f,e['offset'],len(bytes.fromhex(e['after'])))==bytes.fromhex(e['after'])
   if 0x49c800<=at<=0x49cbc0:p.add(e['offset'],bytes.fromhex(e['before']),'Restore volatile game data, never execute code here')
  extra_start,extra_code,cleanup,chain=cleanup_block()
  p.add(0x94880+extra_start-0x100000,extra_code,'Preserved startup + safe intermission duplicate cleanup')
  relocated=relocated_trombe(target)
  block=bytearray(relocated[0x200940]);assert u32(block,len(block)-8)==J(target);struct.pack_into('<I',block,len(block)-8,J(chain));relocated[0x200940]=bytes(block)
  for pc,data in relocated.items():p.add(0x94880+pc-0x100000,data,'Preserved initialization + executable conversion hooks')
  p.add(0x94880+0x2da480-0x100000,pack([J(0x2009f4),0]),'Safe conversion handler')
  p.add(0x94880+0x431778-0x100000,pack([J(0x200a60),0x902d]),'Safe Trombe recovery entry')
  unit,pilot,data=allocation_code();p.add(0x94880+unit-0x100000,data,'Reuse existing Ouka/Wodan unit and pilot slots')
  p.add(0x94880+0x1d5a3c-0x100000,pack([J(unit,True)]),'Unit allocation wrapper')
  p.add(0x94880+0x1d5d98-0x100000,pack([J(pilot,True)]),'Pilot allocation wrapper')
  voice=Archive(f,0x8574e800);assert voice.mapping[0x602]==65535
  raw=voice.get(f,0x42d);clone=bytearray(raw);h=struct.unpack_from('<16H',raw);count=0
  for off in range(h[12],h[13],2):
   tag=u16(raw,off)
   if tag&0x7ff==0x42d:struct.pack_into('<H',clone,off,(tag&0xf800)|0x602);count+=1
  assert count>0
  p.cursor=max(o+n for base in (0x25120800,0x27d66800,0x2970d000,0x8574e800) for o,n in Archive(f,base).entries)
  span=p.archive(voice,[(0x602,bytes(clone),'Allied Wodan speech: original lines/voice IDs, separate pilot key')]);p.add(0x25120000+8+5*8+4,pack([span]),'Speech archive span')
  es=sorted(p.edits)
  for x,y in zip(es,es[1:]):assert x[0]+len(x[1])<=y[0],(x[3],y[3])
 return es,elf,dict(wodan_retagged_rows=count,unit_hook=unit,pilot_hook=pilot)


def patched_cpu(ram,edits):
 c=CPU(ram)
 for at,old,new,label in edits:
  pc=at-0x94880+0x100000
  if 0x100000<=pc<0x582980 and not 0x49c800<=pc<0x49cbe8:c.mem[pc:pc+len(new)]=new
 return c

def slots(c,key,pilot=False):
 save=c.read(0x59d364,4);base,stride,bitmap=(0x25cfc,92,0x3b33c) if pilot else (0x6efc,216,0x3b2fc)
 return [i for i in range(512) if c.read(save+bitmap+(i//32)*4,4)&(1<<(i%32)) and c.read(save+base+i*stride,2)==key]

def repair_ouka(ram):
 c=CPU(ram);save=c.read(0x59d364,4);us,ps=slots(c,0x4e4),slots(c,0x43a,True)
 assert us==[81,83] and ps==[45,46],(us,ps)
 keepu,dropu=us;keepp,dropp=ps
 assert c.run(0x1b1300,[save,keepu,0])==keepp
 former=c.run(0x1b1300,[save,dropu,0]);former_record=bytes(c.mem[save+0x25cfc+former*92:save+0x25cfc+(former+1)*92])
 # The duplicate has no equipped parts or upgrades. The retained pilot is the
 # trained level-38 one; the duplicate is an unused zero-level initializer.
 x=bytes(c.mem[save+0x6efc+keepu*216:save+0x6efc+(keepu+1)*216]);y=bytes(c.mem[save+0x6efc+dropu*216:save+0x6efc+(dropu+1)*216])
 assert [i for i,(a,b) in enumerate(zip(x,y)) if a!=b]==[2,110]
 pp=bytes(c.mem[save+0x25cfc+keepp*92:save+0x25cfc+(keepp+1)*92])
 c.run(0x1b1370,[save,dropu,0])
 assert bytes(c.mem[save+0x25cfc+former*92:save+0x25cfc+(former+1)*92])==former_record
 c.run(0x1d0a00,[save+0x6efc+dropu*216]);c.run(0x1d37d0,[save+0x25cfc+dropp*92])
 for index,bitmap in ((dropu,0x3b2fc),(dropp,0x3b33c)):
  at=save+bitmap+(index//32)*4;c.write(at,c.read(at,4)&~(1<<(index%32)),4)
 assert slots(c,0x4e4)==[keepu] and slots(c,0x43a,True)==[keepp]
 assert bytes(c.mem[save+0x6efc+keepu*216:save+0x6efc+(keepu+1)*216])==x
 assert bytes(c.mem[save+0x25cfc+keepp*92:save+0x25cfc+(keepp+1)*92])==pp
 # Export only native save writes, not the offline CPU's scratch stack.
 out=bytearray(ram);out[save+0x25cfc+dropp*92:save+0x25cfc+(dropp+1)*92]=c.mem[save+0x25cfc+dropp*92:save+0x25cfc+(dropp+1)*92]
 bit=save+0x3b33c+(dropp//32)*4;out[bit:bit+4]=c.mem[bit:bit+4]
 return bytes(out),dict(kept_unit=keepu,kept_pilot=keepp,deferred_unit_cleanup_in_intermission=dropu,removed_unused_pilot=dropp)

def validate(es,elf):
 original=load_ram(STATE);fixed,cleanup=repair_ouka(original);checks=[]
 for start,end in ((0x200514,0x20068c),(0x200940,0x200abc),(0x1feea0,0x1ff294)):
  a=CPU(original);b=patched_cpu(original,es)
  for cpu in (a,b):
   for i in range(1,32):cpu.r[i]=i*0x123456789
   for i in (8,9,10):cpu.r[i]=0x540000
   cpu.fpr[:]=[0x3f000000+i*123 for i in range(32)]
   cpu.run(start,stop=end)
  assert a.r==b.r and a.fpr==b.fpr
  assert a.mem[0x530000:0x540000]==b.mem[0x530000:0x540000]
 checks.append('startup_initializers_identical_registers_float_values_and_data_writes')
 # No original branch may enter the middle of a reclaimed straight-line block.
 for offset in range(0,0x39a6f0,4):
  w=u32(elf,offset);op=w>>26;pc=0x100000+offset;target=None
  if op in (2,3):target=(w&0x3ffffff)<<2
  elif op in (1,4,5,6,7,20,21,22,23):
   imm=w&65535;target=pc+4+(imm-65536 if imm&32768 else imm)*4
  if target is not None:
   assert not (0x200514<target<0x20068c or 0x200940<target<0x200abc or 0x1feea0<target<0x1ff294),('incoming branch',hex(pc),hex(target))
 checks.append('new_code_in_executable_startup_blocks_without_interior_entry_references')
 save=u32(fixed,0x59d364)
 # Group initialization now reuses the already-owned unit AND pilot.
 source=Scripts();wp=0x5071000;at=wp+u32(source.data,wp+8+110*8);n=u32(source.data,at+40)
 rows=[source.data[at+44+i*336:at+44+(i+1)*336] for i in range(n) if u32(source.data,at+44+i*336+4) in (0x24,0x25)]
 for row in rows:
  c=patched_cpu(fixed,es);ctx,bundle,data=0x1700000,0x1780000,0x1790000;c.write(ctx+40,bundle,4)
  for off,g in ((0x2120,0x59d360),(0x2124,0x59d364),(0x212c,0x59d36c)):c.write(bundle+off,c.read(g,4),4)
  c.write(ctx+0x346d4,data,4);c.write(ctx+0x346d0,1,4);c.mem[data:data+336]=row;c.write(CTX+0x310c,ctx-0x40e00,4)
  key,pkey=u32(row,0),u32(row,32);before=(slots(c,key),slots(c,pkey,True))
  for j,v in enumerate(command(0x5e,u32(row,4))):c.write(REC+j*4,v,4)
  for repeat in range(2):
   assert c.run(0x2dae50,[CTX,REC],limit=5000000)==10
   assert (slots(c,key),slots(c,pkey,True))==before,(hex(key),before,slots(c,key),slots(c,pkey,True))
 checks.append('repeated_actual_Ouka_and_Wodan_grant_handlers_do_not_duplicate_units_or_pilots')
 c=patched_cpu(fixed,es);cleanup_pc=cleanup_block()[2];save=c.read(0x59d364,4)
 retained=bytes(c.mem[save+0x6efc+81*216:save+0x6efc+82*216]);pilots_before=bytes(c.mem[save+0x25cfc:save+0x314fc])
 c.run(cleanup_pc);assert slots(c,0x4e4)==[81] and slots(c,0x43a,True)==[45]
 assert bytes(c.mem[save+0x6efc+81*216:save+0x6efc+82*216])==retained and bytes(c.mem[save+0x25cfc:save+0x314fc])==pilots_before
 stable=bytes(c.mem[save:save+0x3b440]);c.run(cleanup_pc);assert c.mem[save:save+0x3b440]==stable
 # A differently upgraded or equipped second unit is never discarded.
 c=patched_cpu(fixed,es);c.run(0x1af000,[save,0xd,83,1,0]);before=bytes(c.mem[save:save+0x3b440]);c.run(cleanup_pc);assert c.mem[save:save+0x3b440]==before
 checks.append('intermission_duplicate_unit_cleanup_preserves_pilots_parts_and_upgrades_and_is_idempotent')
 c=patched_cpu(original,es);c.run(cleanup_pc);assert slots(c,0x4e4)==[81] and slots(c,0x43a,True)==[45]
 checks.append('old_save_duplicate_pilot_is_removed_only_if_untrained_and_unassigned')
 # The real saved map contains corrupted runtime data where the old jump
 # lived. The relocated wrapper must reach the original prologue regardless.
 results=[]
 for modified in (False,True):
  c=patched_cpu(original,es) if modified else CPU(original)
  if not modified:c.mem[0x2da480:0x2da488]=pack([0x27bdff60,0x24060003])
  for j,v in enumerate(command(0x6f,0x4e3,0x4e2,0)):c.write(REC+j*4,v,4)
  c.run(0x2da480,[CTX,REC],stop=0x2da488)
  results.append([c.r[i] for i in (4,5,6,*range(16,32))])
 assert results[0]==results[1]
 checks.append('real_saved_map_conversion_reaches_original_prologue_with_identical_arguments_stack_and_saved_registers')
 # Re-execute future Trombe granting through the relocated helper.
 c=patched_cpu(fixed,es);c.write(u32(fixed,0x59d36c)+0xf5c,1,4)
 present=slots(c,0x4ba);other=slots(c,0x4b9)
 if present and not other:
  src=present[0];before=bytes(c.mem[save+0x6efc+src*216:save+0x6efc+(src+1)*216])
  c.run(0x200558,[0x4ba,0x4b9]);assert len(slots(c,0x4b9))==1
  assert bytes(c.mem[save+0x6efc+src*216:save+0x6efc+(src+1)*216])==before
 elif other and not present:
  c.run(0x200558,[0x4b9,0x4ba]);assert len(slots(c,0x4ba))==1
 else:assert len(present)==len(other)==1,(present,other)
 stable=bytes(c.mem[save:save+0x3b440]);c.run(0x200558,[0x4ba,0x4b9]);assert c.mem[save:save+0x3b440]==stable
 checks.append('relocated_Trombe_helper_preserves_existing_units_and_is_idempotent')
 # Exercise the split helper's entire allocation/grade-copy path.
 c=patched_cpu(fixed,es);source=slots(c,0x4ba)[0];removed=slots(c,0x4b9)[0]
 c.run(0x1b1370,[save,removed,0]);c.run(0x1d0a00,[save+0x6efc+removed*216]);bit=save+0x3b2fc+(removed//32)*4;c.write(bit,c.read(bit,4)&~(1<<(removed%32)),4)
 for j,prop in enumerate(range(0xd,0x11)):c.run(0x1af000,[save,prop,source,j+3,0])
 for j in range(16):c.write(REC,j,4);c.run(0x1af000,[save,0xc,source,(j+2)%11,REC])
 keep=bytes(c.mem[save+0x6efc+source*216:save+0x6efc+(source+1)*216])
 c.run(0x200558,[0x4ba,0x4b9]);extra=slots(c,0x4b9);assert len(extra)==1
 assert bytes(c.mem[save+0x6efc+source*216:save+0x6efc+(source+1)*216])==keep
 for j,prop in enumerate(range(0xd,0x11)):assert c.run(0x1af860,[save,prop,extra[0],0])==j+3
 for j in range(16):c.write(REC,j,4);assert c.run(0x1af860,[save,0xc,extra[0],REC])==c.run(0x1af860,[save,0xc,source,REC])
 checks.append('relocated_split_helper_executes_full_body_and_weapon_upgrade_copy')
 # Original Wodan selector/text/voice data remain identical except self tags.
 class SelectorCPU(CPU):
  def step(self):
   if self.pc==0x12fc58:self.put(2,0);self.pc=self.r[31]&0xffffffff;self.pending=None;self.count+=1
   else:super().step()
 with ISO.open('rb') as f:
  archive=Archive(f,0x8574e800);raw=archive.get(f,0x42d)
 clone=next(new for at,old,new,label in es if label.startswith('Allied Wodan speech'))
 h=struct.unpack_from('<16H',clone);assert raw[:h[12]]==clone[:h[12]] and raw[h[13]:]==clone[h[13]:]
 for data in (raw,clone):
  c=SelectorCPU(fixed);obj,loc,choice=0x1600000,0x1700000,0x1800000;c.mem[obj:obj+0x100]=bytes(0x100);c.mem[loc:loc+len(data)]=data;c.write(obj,1,4);c.write(obj+4,loc,4);c.run(0x3593c0,[obj])
  for motion in (1,2,3):
   for phase in (0,1):
    idx=c.run(0x359060,[obj,0,103,motion,phase,0x4a5,0,choice]);assert idx>=0,(motion,phase,idx)
 checks.append('all_six_original_Wodan_weapon_cues_resolve_through_native_speech_selector')
 return checks,cleanup


def zip_read(path,z,info):
 try:return z.read(info)
 except NotImplementedError:
  import zstandard
  assert info.compress_type in (20,93)
  with path.open('rb') as f:
   f.seek(info.header_offset);hd=f.read(30);n,e=struct.unpack_from('<HH',hd,26);f.seek(n+e,1)
   return zstandard.ZstdDecompressor().decompress(f.read(info.compress_size),max_output_size=info.file_size)

def make_state(edits):
 import zipfile,functools,operator
 original=load_ram(STATE);fixed,cleanup=repair_ouka(original);out=bytearray(patched_cpu(fixed,edits).mem)
 # Remove still-intact injected instructions from the old data-area cave,
 # while retaining every word that the running game has already written there.
 oldplan=json.loads((ROOT/'runtime/trombe_coexist_20261119.json').read_text(encoding='utf-8'))['files'][0]['edits'];cleared=0
 for item in oldplan:
  pc=item['offset']-0x94880+0x100000
  if not 0x49c800<=pc<=0x49cbc0:continue
  before,after=bytes.fromhex(item['before']),bytes.fromhex(item['after'])
  for i in range(0,len(after),4):
   if out[pc+i:pc+i+4]==after[i:i+4] and after[i:i+4]!=before[i:i+4]:out[pc+i:pc+i+4]=before[i:i+4];cleared+=1
 assert out[0x49cac0:0x49cad0]==original[0x49cac0:0x49cad0] and out[0x49cbc0:0x49cbe8]==original[0x49cbc0:0x49cbe8]
 cleanup['stale_injected_code_words_cleared']=cleared
 # Update the already-loaded native speech archive descriptors as well as ISO.
 # The next independent archive starts at 0x9D6B80, leaving room for one entry.
 with ISO.open('rb') as f:
  f.seek(0x94800);head=f.read(52);length=u32(head,32)+u16(head,46)*u16(head,48);f.seek(0x94800);elf=f.read(length)
 newcrc=functools.reduce(operator.xor,struct.unpack('<%dI'%(len(elf)//4),elf),0)
 for at,old,new,label in edits:
  if at==0x8574e804:dst=0x9d51c4
  elif at==0x8574e810:dst=0x9d51d0
  elif at==0x8574f800:
   dst=0x9d61c0;assert dst+len(new)<=0x9d6b80
  else:continue
  # The appended directory entry occupies prior unused alignment padding.
  compare=min(len(old),len(new)-8) if label.startswith('Wpbb') else len(old)
  assert original[dst:dst+compare]==old[:compare],(label,hex(dst))
  out[dst:dst+len(new)]=new
 assert u16(out,0x9d51d0+0x602*2)!=65535
 assert slots(CPU(out),0x43a,True)==[45] and slots(CPU(out),0x4e4)==[81,83]
 destination=ART/('SLPS-25733 (%08X).'%newcrc+STATE.name.split(').',1)[1])
 entries=[]
 with zipfile.ZipFile(STATE) as z:
  with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as target:
   for info in z.infolist():
    raw=zip_read(STATE,z,info);before=hashlib.sha256(raw).hexdigest()
    if info.filename=='eeMemory.bin':raw=bytes(out)
    elif info.filename=='PCSX2 Internal Structures.dat':
     assert raw.count(pack([0x0f622503]))==1 and raw[0x1244:0x1248]==pack([0x0f622503]);raw=raw[:0x1244]+pack([newcrc])+raw[0x1248:]
    target.writestr(info.filename,raw);entries.append(dict(name=info.filename,before_sha256=before,after_sha256=hashlib.sha256(raw).hexdigest()))
 with zipfile.ZipFile(destination) as z:assert z.testzip() is None
 assert load_ram(destination)==bytes(out)
 assert all(e['before_sha256']==e['after_sha256'] for e in entries if e['name'] not in ('eeMemory.bin','PCSX2 Internal Structures.dat'))
 return dict(path=str(destination),elf_crc='%08X'%newcrc,original_preserved=True,cleanup=cleanup,entries=entries,sha256=hashlib.sha256(destination.read_bytes()).hexdigest())

def apply_all():
 import psutil
 assert not any('pcsx2' in p.name().lower() for p in psutil.process_iter()),'Close local PCSX2'
 report=dict(applied=False,live_playthrough_verified=False,files=[]);journal=ART/'fix_manifest.json';plans=[]
 for name in ('SRWOGS_K.iso','SRWOGS_BEOWULF_CUTIN_TEST.iso'):
  path=ROOT/'build'/name;es,elf,info=build(path);checks,cleanup=validate(es,elf)
  with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
  item=dict(path=str(path),before_sha256=digest,checks=checks,details=info,edits=[dict(offset=at,before=old.hex(),after=new.hex(),label=label) for at,old,new,label in es]);report['files'].append(item);plans.append((path,es,item))
  print(name,'native validations passed',flush=True)
 journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 for path,es,item in plans:
  with path.open('r+b') as f:
   assert hashlib.file_digest(f,'sha256').hexdigest()==item['before_sha256']
   try:
    for at,old,new,label in es:assert read(f,at,len(old))==old;f.seek(at);f.write(new)
    f.flush();os.fsync(f.fileno());f.seek(0);pos=0;current=hashlib.sha256();inverse=hashlib.sha256()
    for at,old,new,label in es:
     while pos<at:
      raw=f.read(min(4<<20,at-pos));assert raw;current.update(raw);inverse.update(raw);pos+=len(raw)
     raw=f.read(len(new));assert raw==new;current.update(raw);inverse.update(old);pos+=len(raw)
    while raw:=f.read(4<<20):current.update(raw);inverse.update(raw)
    assert inverse.hexdigest()==item['before_sha256'];item['after_sha256']=current.hexdigest()
   except Exception:
    for at,old,new,label in es:f.seek(at);f.write(old)
    f.flush();os.fsync(f.fileno());raise
  print(path.name,'ISO applied and whole-file inverse hash verified',flush=True)
 report['applied']=True;journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 report['state']=make_state(plans[0][1]);journal.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(applied=True,state=report['state']['path'],crc=report['state']['elf_crc']),ensure_ascii=False),flush=True)

if __name__=='__main__':
 import sys
 if '--apply' in sys.argv:apply_all()
 else:
  es,elf,info=build(ISO);print(info,flush=True);print(validate(es,elf),flush=True)
