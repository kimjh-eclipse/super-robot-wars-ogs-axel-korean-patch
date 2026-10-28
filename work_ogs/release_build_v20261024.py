# -*- coding: utf-8 -*-
"""v20261026 릴리즈 산출물 일괄 생성 (build/SRWOGS_K.iso 기준).

xdelta → 전체 구간 팩 → 업그레이드 팩(v20260831, v20260904, v20261002 적용본 → 신판)
→ 패처 E2E(기준본/구판 및 옵션ON 적용본/복원) → release_v20261026 폴더·SHA256SUMS·ZIP.
임시 ISO는 한 번에 하나만 만들고 즉시 지운다. 모든 단계 해시 가드.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import json
import struct
import importlib.util
import urllib.request
import urllib.parse
import re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

V = "v20261026"
W = Path(__file__).resolve().parent
ROOT = W.parent
XD = ROOT / "xdelta.exe"
ISO = W / "build" / "SRWOGS_K.iso"
BASE = W / "baseline" / "srwogs-v1.4.3s1.iso"
DIST = W / "dist"
QP = W / "iso_quickpatch"
REL = W / f"release_{V}"
BASE_SHA = "9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C"
EXPECT = ""  # derived from the guarded current ISO by removing only the option
HIDDEN_EXPECT = ""  # derived after reverting the selected bundle
OUKA_EXPECT = ""  # bundled Ouka + Daizengar, without hidden rewards
BOTH_EXPECT = "C3A1525F4754EC88DD5812CB52E3C563A30558EE50E6B43A212B881E94924753"
OLD = [  # (라벨, xdelta, 복원 해시)
    ("v20260831", DIST / "old_v20260831" / "SRWOGS_AxelRoleSwap_kr_v20260831.xdelta",
     "08615F303D301AC9935A7C71379D8AE4BD5B2F9E0C2B328397D103FD0352B930"),
    ("v20260904", DIST / "SRWOGS_AxelRoleSwap_kr_v20260904.xdelta",
     "831A646BCDE363B92A1E8CD2C5CACE786102A61833A5757BB155B527CF35B9CC"),
    ("v20261002", DIST / "SRWOGS_AxelRoleSwap_kr_v20261002.xdelta",
     "747832E0310F6CD4B23A702FC1FC928C19F6D44B8B51879184FCC2459BEF6915"),
]
OLD += [
    ("v20261024", DIST/"SRWOGS_AxelRoleSwap_kr_v20261024.xdelta",
     "5432A2F5066DB50E54511AB2C3A0744A56911FA4510A519AB65FB803CE7114A8"),
    ("v20261024_hidden", DIST/"SRWOGS_AxelRoleSwap_kr_v20261024.xdelta",
     "687397FA1E1B57CB6FD547B3D6A23701B7AE529C500B491360B6B69566EB1735")]
OLD += [
    ('v20261025',DIST/'SRWOGS_AxelRoleSwap_kr_v20261025.xdelta',
     '637324DD8326CBC2D7035E6F0536759D0FAAA910830633E0E5B5182DE08F5F7D'),
    ('v20261025_hidden',DIST/'SRWOGS_AxelRoleSwap_kr_v20261025.xdelta',
     '8499BE55449D6026831DF7697185BA12E5009492ED584B21B645D3DAFE7AD3FB')]
OLD += [
    ('v20261025_1_ouka',DIST/'SRWOGS_AxelRoleSwap_kr_v20261025.1.xdelta',
     '3739CBBB32BBB1DF1F744E67F5277E5B2A7E97B83AC96781BE5F3C8C7CA48AD0'),
    ('v20261025_1_both',DIST/'SRWOGS_AxelRoleSwap_kr_v20261025.1.xdelta',
     '5BC30BB635EA895A04A3E2C1F713F91C54F78CF802D1D48A33F53BD77AEBA1F1')]
XDELTA_OUT = DIST / f"SRWOGS_AxelRoleSwap_kr_{V}.xdelta"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest().upper()


def md5(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest().upper()


def run(*args):
    print("  $", " ".join(str(a) for a in args))
    subprocess.run([str(a) for a in args], check=True)


def need(cond, msg):
    if not cond:
        raise SystemExit("중단: " + msg)

def remove_build_tree(path):
    resolved = path.resolve()
    need(resolved.is_relative_to(W.resolve()) and resolved != W.resolve(), "정리 경로 범위 오류")
    if resolved.exists(): shutil.rmtree(resolved)

def restore_old(label, xd, expected, target):
    run(XD,'-d','-f','-s',BASE,xd,target)
    def apply_option(pack):
        with pack.open('rb') as p:
            need(p.read(8)==b'OGSHID01','Old option pack magic')
            need(struct.unpack('<Q',p.read(8))[0]==target.stat().st_size,'Old option size')
            source,destination=p.read(32).hex().upper(),p.read(32).hex().upper()
            need(sha(target)==source,'Old variant source mismatch')
            with target.open('r+b') as f:
                for _ in range(struct.unpack('<I',p.read(4))[0]):
                    off,length=struct.unpack('<QI',p.read(12));old,new=p.read(length),p.read(length)
                    need(len(new)==length,'Old option payload truncated')
                    f.seek(off);need(f.read(length)==old,'Old option byte guard')
                    f.seek(off);f.write(new)
            need(not p.read(1),'Old option trailing bytes')
        need(sha(target)==destination,'Old option result mismatch')
    if label=='v20261025_hidden':
        apply_option(W/'release_v20261025/patcher/OGS_hidden_rewards.bin')
    elif label=='v20261025_1_ouka':
        apply_option(W/'release_v20261025.1/patcher/OGS_ouka_survival.bin')
    elif label=='v20261025_1_both':
        apply_option(W/'release_v20261025.1/patcher/OGS_hidden_rewards.bin')
        apply_option(W/'release_v20261025.1/patcher/OGS_ouka_survival_hidden.bin')
    elif label.endswith('_hidden'):
        m=json.loads((W/'runtime/hidden_rewards_manifest.json').read_text(encoding='utf-8'))
        need(sha(target)==m['source_sha256'].upper(),'Old option source mismatch')
        with target.open('r+b') as f:
            for e in m['edits']:
                old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                f.seek(e['offset']);need(f.read(len(old))==old,'Old option guard')
                f.seek(e['offset']);f.write(new)
    need(sha(target)==expected,'Old release reconstruction mismatch: '+label)


def prepare_default():
    global EXPECT,HIDDEN_EXPECT,OUKA_EXPECT
    default=DIST/'DEFAULT_BUILD.iso';hidden=DIST/'HIDDEN_BUILD.iso';bundle=DIST/'OUKA_BUILD.iso'
    # Keep the user's ISO unchanged. Build the bundle-off variant by reverting
    # Ouka, Daizengar combat data and its appended animation routes only.
    shutil.copyfile(ISO,hidden)
    ouka=json.loads((W/'runtime/ouka_survival_manifest.json').read_text(encoding='utf-8'))
    animations=json.loads((W/'runtime/daizengar_animation_links_manifest.json').read_text(encoding='utf-8'))
    need(ouka['applied'] and animations['applied'],'Bundle inputs not applied')
    with BASE.open('rb') as base,hidden.open('r+b') as f:
        for e in ouka['edits']+animations['edits']:
            old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
            f.seek(e['offset']);need(f.read(len(new))==new,'Bundle reverse byte guard')
            f.seek(e['offset']);f.write(old)
        for start in (0x5DA000,0x83F000):
            for idx in (0xD0,0xD1,0x176):
                at=start+0x11F8A4+idx*100;base.seek(at);original=bytearray(base.read(100))
                f.seek(at+0x22);boarding=f.read(2)
                # Keep the common Sanger/Sladegelmir boarding compatibility.
                original[0x22:0x24]=boarding;f.seek(at);f.write(original)
            for idx in list(range(0x30C,0x314))+list(range(0x575,0x57A)):
                at=start+0x12BF88+idx*36;base.seek(at);original=base.read(36)
                f.seek(at);f.write(original)
            at=start+0x11E898+0x49A*2;base.seek(at);original=base.read(2)
            need(original==bytes.fromhex('d100'),'Original basic unit alias mismatch')
            f.seek(at);f.write(original)
    HIDDEN_EXPECT=sha(hidden)
    repair=json.loads((W/'runtime/release_preflight_manifest.json').read_text(encoding='utf-8'))
    rewards=json.loads((W/'runtime/hidden_rewards_manifest.json').read_text(encoding='utf-8'))
    from build_hidden_rewards import Scripts,MAP
    scripts=Scripts();at,size=scripts.logos[88]
    def remove_hidden(source,target):
        shutil.copyfile(source,target)
        with target.open('r+b') as f:
            for e in repair['edits']:
                if MAP+at<=e['offset']<MAP+at+size:
                    old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                    f.seek(e['offset']);need(f.read(len(new))==new,'Option lookup reverse guard')
                    f.seek(e['offset']);f.write(old)
            for e in rewards['edits']:
                old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                f.seek(e['offset']);need(f.read(len(new))==new,'Option reverse guard')
                f.seek(e['offset']);f.write(old)
    remove_hidden(hidden,default);remove_hidden(ISO,bundle)
    EXPECT=sha(default);OUKA_EXPECT=sha(bundle)
    metadata=dict(version=V,default_sha256=EXPECT,hidden_sha256=HIDDEN_EXPECT,
                  ouka_sha256=OUKA_EXPECT,bundle_sha256=OUKA_EXPECT,both_sha256=BOTH_EXPECT,
                  default_md5=md5(default),hidden_default=False,bundle_default=False,
                  bundle_scope='Ouka survival + all Daizengar combat changes',
                  sanger_sladegelmir_boarding_compatibility_preserved=True)
    (W/'runtime/release_build_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    from validate_hidden_rewards import validate_release_variants
    validation=validate_release_variants(default,hidden,bundle,ISO)
    (W/'runtime/release_variants_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Four native option profiles verified',flush=True)
    return default


def hidden_pack():
    spec=importlib.util.spec_from_file_location('ranges',QP/'build_range_pack.py')
    ranges=importlib.util.module_from_spec(spec);spec.loader.exec_module(ranges)
    def option(source,target,name):
        entries=ranges.find_ranges(source,target)
        with (QP/name).open('wb') as f, source.open('rb') as a, target.open('rb') as b:
            f.write(b'OGSHID01');f.write(struct.pack('<Q',ISO.stat().st_size))
            f.write(bytes.fromhex(sha(source)));f.write(bytes.fromhex(sha(target)))
            f.write(struct.pack('<I',len(entries)))
            for off,size in entries:
                a.seek(off);b.seek(off);f.write(struct.pack('<QI',off,size));f.write(a.read(size));f.write(b.read(size))
    option(DIST/'DEFAULT_BUILD.iso',DIST/'HIDDEN_BUILD.iso','OGS_hidden_rewards.bin')
    option(DIST/'DEFAULT_BUILD.iso',DIST/'OUKA_BUILD.iso','OGS_ouka_zengar.bin')
    option(DIST/'HIDDEN_BUILD.iso',ISO,'OGS_ouka_zengar_hidden.bin')


def test_options():
    exe=QP/'OGS_AxelSwap_QuickPatch.exe';t=QP/'TEST.iso';bak=Path(str(t)+'.ogsbak')
    variants=[('기본',DIST/'DEFAULT_BUILD.iso',EXPECT,()),
              ('숨김',DIST/'HIDDEN_BUILD.iso',HIDDEN_EXPECT,('--hidden',)),
              ('오우카·젠가',DIST/'OUKA_BUILD.iso',OUKA_EXPECT,('--bundle',)),
              ('두 옵션',ISO,BOTH_EXPECT,('--hidden','--bundle'))]
    results=[]
    def action(label, expected, *flags):
        run(exe,t,*flags);need(sha(t)==expected,label+' 결과 해시 실패');results.append(label)
        print('PASS',label,flush=True)
    try:
        for name,path,expected,flags in variants:
            bak.unlink(missing_ok=True);shutil.copyfile(BASE,t)
            action('기준본 → '+name,expected,'--cli',*flags)
            before_bak=sha(bak)
            action(name+' 재적용 무변경',expected,'--cli',*flags)
            need(sha(bak)==before_bak,'무변경 재적용이 백업을 변경함')
            action(name+' 기준본 백업 복원',BASE_SHA,'--restore')
        for source,source_path,source_hash,_ in variants:
            for destination,_,expected,flags in variants:
                if source==destination:continue
                bak.unlink(missing_ok=True);shutil.copyfile(source_path,t)
                action(source+' → '+destination,expected,'--cli',*flags)
                action(source+' → '+destination+' 복원',source_hash,'--restore')
        for label,xd,expected in OLD:
            bak.unlink(missing_ok=True);restore_old(label,xd,expected,t)
            action(label+' → 두 옵션',BOTH_EXPECT,'--cli','--hidden','--bundle')
            action(label+' 업그레이드 백업 복원',expected,'--restore')
            action(label+' → 기본 옵션',EXPECT,'--cli')
        report=dict(version=V,passed=True,paths=results,base_iso_sha256=EXPECT,
                    hidden_iso_sha256=HIDDEN_EXPECT,ouka_iso_sha256=OUKA_EXPECT,both_iso_sha256=BOTH_EXPECT)
        (W/'runtime/hidden_rewards_patcher_e2e.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        t.unlink(missing_ok=True);bak.unlink(missing_ok=True)


def main() -> None:
    out = subprocess.run(["tasklist"], capture_output=True, text=True, errors="ignore").stdout.lower()
    need("pcsx2" not in out and "srwz" not in out, "PCSX2 실행 중")
    package_only = "--package-only" in sys.argv
    print("[0] 해시 가드")
    need(sha(BASE) == BASE_SHA, "기준 ISO 해시 불일치")
    need(sha(ISO) == BOTH_EXPECT, "SRWOGS_K.iso 해시 불일치")
    global EXPECT,HIDDEN_EXPECT,OUKA_EXPECT
    if any(x in sys.argv for x in ('--publish','--test-options','--package-only')):
        meta=json.loads((W/'runtime/release_build_metadata.json').read_text(encoding='utf-8'))
        need(meta['version']==V and meta['both_sha256']==BOTH_EXPECT,'Build metadata mismatch')
        EXPECT=meta['default_sha256'];HIDDEN_EXPECT=meta['hidden_sha256'];OUKA_EXPECT=meta['bundle_sha256']
    if '--publish' in sys.argv:
        publish();return
    if '--test-options' in sys.argv:
        test_options();return

    if package_only:
        exe = QP / "OGS_AxelSwap_QuickPatch.exe"
        need(XDELTA_OUT.exists(), "xdelta 없음")
        return package(exe)
    default_iso=prepare_default()
    hidden_pack()
    print('[compile] QuickPatch',flush=True)
    run(Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'),
        '/nologo','/target:winexe','/platform:anycpu','/optimize+',
        '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll',
        '/out:'+str(QP/'OGS_AxelSwap_QuickPatch.exe'),QP/'OgsAxelQuickPatch.cs')
    print("[1] xdelta")
    run(XD, "-e", "-9", "-f", "-B", "536870912", "-s", BASE, default_iso, XDELTA_OUT)
    tmp = DIST / "VERIFY.iso"
    run(XD, "-d", "-f", "-s", BASE, XDELTA_OUT, tmp)
    ok = sha(tmp) == EXPECT
    tmp.unlink()
    need(ok, "xdelta 복호 불일치")

    print("[2] 전체 구간 팩")
    spec=importlib.util.spec_from_file_location('ranges',QP/'build_range_pack.py')
    ranges=importlib.util.module_from_spec(spec);spec.loader.exec_module(ranges)
    ranges.TARGET=default_iso;ranges.main()

    print("[3] 업그레이드 팩")
    old_dir = QP / "old_packs"
    old_dir.mkdir(exist_ok=True)
    for p in QP.glob("OGS_ISO_ranges_upgrade*.bin"):
        shutil.move(str(p), old_dir / ("superseded_" + p.name))
    for label, xd, exp in OLD:
        tmp = DIST / f"OLD_{label}.iso"
        restore_old(label,xd,exp,tmp)
        run(sys.executable, QP / "build_upgrade_pack_from_iso.py", tmp, default_iso,
            QP / f"OGS_ISO_ranges_upgrade_{label}.bin",
            f"슈퍼로봇대전 OGs 액셀 역할 교체 패치 ({label} 적용본→{V} 업그레이드)")
        tmp.unlink()

    print("[4] 패처 E2E — base/old variants, options and restore")
    test_options()
    for name in ('DEFAULT_BUILD.iso','HIDDEN_BUILD.iso','OUKA_BUILD.iso'):(DIST/name).unlink()
    package(QP / "OGS_AxelSwap_QuickPatch.exe")


def package(exe: Path) -> None:
    print("[5] 패키지")
    result=json.loads((W/'runtime/hidden_rewards_patcher_e2e.json').read_text(encoding='utf-8'))
    need(result.get('passed') and result.get('version')==V and result.get('both_iso_sha256')==BOTH_EXPECT,'패처 E2E 검증 미완료')
    if REL.exists():
        keep = {p.name: p.read_bytes() for p in REL.glob("*.txt")}
        remove_build_tree(REL)
    else:
        keep = {}
    (REL / "patcher").mkdir(parents=True)
    (REL / "xdelta").mkdir()
    for p in [exe, QP / "OGS_ISO_ranges.bin", QP/'OGS_hidden_rewards.bin', QP/'OGS_ouka_zengar.bin', QP/'OGS_ouka_zengar_hidden.bin', *sorted(QP.glob("OGS_ISO_ranges_upgrade_*.bin"))]:
        shutil.copy2(p, REL / "patcher")
    for p in (XDELTA_OUT, XD, W / "release_v20260904" / "xdelta" / "xdeltaUI.exe"):
        shutil.copy2(p, REL / "xdelta")
    readme = REL / "읽어주세요.txt"
    readme.write_bytes((W / "release_readme_v20261024.template.txt").read_bytes())
    if readme.exists():
        s = readme.read_text(encoding="utf-8")
        repl = {
            "__EXE_SHA__": sha(REL / "patcher" / exe.name),
            "__BIN_SHA__": sha(REL / "patcher" / "OGS_ISO_ranges.bin"),
            "__UP0831_SHA__": sha(REL / "patcher" / "OGS_ISO_ranges_upgrade_v20260831.bin"),
            "__UP0904_SHA__": sha(REL / "patcher" / "OGS_ISO_ranges_upgrade_v20260904.bin"),
            "__UP1002_SHA__": sha(REL / "patcher" / "OGS_ISO_ranges_upgrade_v20261002.bin"),
            "__ISO_SHA__": EXPECT,
            "__ISO_MD5__": json.loads((W/"runtime/release_build_metadata.json").read_text())["default_md5"],
            "__HIDDEN_SHA__": HIDDEN_EXPECT,
            "__OUKA_SHA__": OUKA_EXPECT,
            "__BOTH_SHA__": BOTH_EXPECT,
        }
        for k, v in repl.items():
            s = s.replace(k, v)
        need("__" not in s, "읽어주세요.txt 자리표시자 남음")
        readme.write_text(s, encoding="utf-8")
    else:
        print("  ! 읽어주세요.txt 없음 — 작성 후 [5]만 재실행 필요")
    lines = [f"슈퍼로봇대전 OGs 액셀 역할 교체 패치 {V} — SHA-256", ""]
    for p in sorted(REL.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS.txt":
            lines.append(f"{sha(p)}  {p.relative_to(REL).as_posix()}")
    lines += ["", "기준 ISO (배포물에 미포함)", f"{BASE_SHA}  srwogs-v1.4.3s1.iso (4,518,150,144B)",
              "", "기본 옵션 결과 ISO", f"{EXPECT}  (4,518,150,144B)",
              "", "숨겨진 요소 자동 습득 선택 결과 ISO", f"{HIDDEN_EXPECT}  (4,518,150,144B)", "", "오우카 생존·젠가 밸런스 묶음 선택 결과 ISO", f"{OUKA_EXPECT}  (4,518,150,144B)", "", "두 옵션 선택 결과 ISO", f"{BOTH_EXPECT}  (4,518,150,144B)"]
    (REL / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    stage = DIST / f"stage_{V}"
    remove_build_tree(stage)
    shutil.copytree(REL, stage / f"SRWOGS_AxelRoleSwap_kr_{V}")
    zpath = DIST / f"SRWOGS_AxelRoleSwap_kr_{V}"
    shutil.make_archive(str(zpath), "zip", stage)
    remove_build_tree(stage)
    z = Path(str(zpath) + ".zip")
    print("\n결과")
    print("  ZIP     ", sha(z), z.stat().st_size)
    print("  xdelta  ", sha(XDELTA_OUT), md5(XDELTA_OUT), XDELTA_OUT.stat().st_size)
    print("  ISO MD5 ", md5(ISO))
    for p in sorted((REL / "patcher").iterdir()):
        print("  ", p.name, sha(p), p.stat().st_size)
    print("DONE")


def publish():
    """Create a new versioned release; preserve all previously published assets."""
    repo=ROOT/'ogs-repo';z=DIST/f'SRWOGS_AxelRoleSwap_kr_{V}.zip'
    need(z.exists(),'Release ZIP missing')
    report=json.loads((W/'runtime/hidden_rewards_patcher_e2e.json').read_text(encoding='utf-8'))
    need(report['passed'] and report.get('version')==V and report.get('both_iso_sha256')==BOTH_EXPECT,'E2E incomplete')
    token=next((line.split('=',1)[1].strip().strip('"').strip("'")
                for line in (ROOT/'.env').read_text(encoding='utf-8').splitlines()
                if line.startswith('GITHUB_TOKEN=')),None)
    need(bool(token),'Release authentication unavailable')
    api_root='https://api.github.com/repos/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch'
    def api(method,url,data=None,ctype='application/json'):
        req=urllib.request.Request(url,method=method,data=data,headers={
            'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
            'Content-Type':ctype,'User-Agent':'ogs-release-patcher'})
        with urllib.request.urlopen(req,timeout=120) as response:
            return json.loads(response.read() or b'{}')
    need(not subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip(),'Commit release files before publishing')
    run('git','-C',repo,'push','origin','main')
    head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    body=(W/'runtime/release_notes.md').read_text(encoding='utf-8')
    body+='\n\nZIP SHA-256: `'+sha(z)+'`\n'
    rel=api('POST',api_root+'/releases',json.dumps(dict(tag_name=V,target_commitish=head,
        name='OGs 액셀 역할 교체 패치 '+V+' — 오우카 생존·젠가 밸런스 선택 옵션',
        body=body,draft=True,prerelease=False),ensure_ascii=False).encode())
    for file,ctype in ((z,'application/zip'),(XDELTA_OUT,'application/octet-stream')):
        uploaded=api('POST',rel['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(file.name),file.read_bytes(),ctype)
        need(uploaded['size']==file.stat().st_size,'Upload size mismatch')
        if uploaded.get('digest'):need(uploaded['digest'].lower()=='sha256:'+sha(file).lower(),'Upload digest mismatch')
    rel=api('PATCH',rel['url'],json.dumps(dict(draft=False,make_latest='true')).encode())
    verified=[]
    for asset in rel['assets']:
        with urllib.request.urlopen(asset['browser_download_url'],timeout=120) as response:
            h=hashlib.sha256()
            while b:=response.read(4<<20):h.update(b)
        local=z if asset['name']==z.name else XDELTA_OUT
        need(h.hexdigest().upper()==sha(local),'Published download hash mismatch')
        verified.append(asset['browser_download_url'])
    result=dict(release=rel['html_url'],assets=verified,zip_sha256=sha(z),commit=head,download_verified=True)
    (W/'runtime/hidden_rewards_publish.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)



def build_common_xdelta():
    version='v20261029.1';repo=ROOT/'ogs-repo'
    profiles=json.loads((W/'runtime/common_fix_profiles.json').read_text(encoding='utf-8'))
    cache=W/'runtime/story_xdelta_validation.json'
    delta=DIST/f'SRWOGS_AxelRoleSwap_kr_{version}.xdelta'
    if cache.exists() and delta.exists():
        m=json.loads(cache.read_text(encoding='utf-8'))
        need(m['default_sha256']==profiles['hashes'][0] and m['delta_sha256']==sha(delta),'Cached xdelta changed')
        return delta,m['default_md5']
    # Reconstruct the old all-OFF profile, add the guarded common fix, then
    # encode and fully decode the new default xdelta before distribution.
    delta=DIST/f'SRWOGS_AxelRoleSwap_kr_{version}.xdelta'
    test=DIST/'VERIFY_OPTIONS_RELEASE.iso'
    need(not test.exists(),'Inspect existing release test ISO first')
    try:
        run(XD,'-d','-f','-s',BASE,repo/'patch/SRWOGS_AxelRoleSwap_kr_v20261026.xdelta',test)
        need(sha(test)==profiles['previous_hashes'][0],'Previous default decode mismatch')
        fix=dict(edits=json.loads((W/'runtime/story_common_edits.json').read_text(encoding='utf-8'))['0'])
        with test.open('r+b') as f:
            for e in fix['edits']:
                at=e['offset'];old=bytes.fromhex(e['before']);new=bytes.fromhex(e['after'])
                f.seek(at);need(f.read(len(old))==old,'Default shared-fix byte guard');f.seek(at);f.write(new)
        need(sha(test)==profiles['hashes'][0],'New default SHA mismatch')
        default_md5=md5(test)
        run(XD,'-e','-9','-f','-B','536870912','-s',BASE,test,delta)
        run(XD,'-d','-f','-s',BASE,delta,test)
        need(sha(test)==profiles['hashes'][0],'Default xdelta decode mismatch')
    finally:test.unlink(missing_ok=True)
    cache.write_text(json.dumps(dict(default_sha256=profiles['hashes'][0],default_md5=default_md5,
        delta_sha256=sha(delta),decode_verified=True),indent=2),encoding='utf-8')
    return delta,default_md5


def prepare_options_release():
    """Package the five-option release without changing the gameplay ISO."""
    import zipfile
    version='v20261029.1';repo=ROOT/'ogs-repo';rel=W/('release_'+version)
    profiles=json.loads((W/'runtime/common_fix_profiles.json').read_text(encoding='utf-8'))
    e2e=json.loads((W/'runtime/optional_features_patcher_e2e.json').read_text(encoding='utf-8'))
    need(e2e['passed'] and len(e2e['real_iso_transitions'])==32 and e2e['current_gameplay_iso_unchanged']==profiles['iso_unchanged_sha256'] and e2e['production_composition_selftest']==5120,'Five-option E2E incomplete')
    need(sha(ISO)==profiles['hashes'][31],'Gameplay ISO changed')
    need(sha(BASE)==BASE_SHA,'Baseline changed')
    # Ensure staged data still matches the exact files tested/packaged locally.
    sums=(QP/'SHA256SUMS.txt').read_text(encoding='utf-8-sig')
    for line in sums.splitlines():
        h,name=line.split('  ',1);need(sha(QP/name)==h,'Patcher file changed: '+name)
    need(e2e['patcher_sha256']==sha(QP/'OGS_AxelSwap_QuickPatch.exe') and e2e['common_pack_sha256']==sha(QP/'OGS_common_fix.bin'),'Patcher changed after completed E2E')
    if rel.exists():remove_build_tree(rel)
    (rel/'patcher').mkdir(parents=True)
    for line in sums.splitlines():
        _,name=line.split('  ',1);shutil.copyfile(QP/name,rel/'patcher'/name)
    delta,default_md5=build_common_xdelta()
    shutil.copyfile(delta,rel/delta.name)
    # The installer README is for this public package rather than the earlier
    # standalone local patcher bundle.
    small=(rel/'patcher/읽어주세요.txt').read_text(encoding='utf-8-sig')
    small=small.replace('공개 GitHub 릴리즈는 별도로 갱신하지 않았습니다.','')
    (rel/'patcher/읽어주세요.txt').write_text(small,encoding='utf-8-sig')
    cafe=(W/'CAFE_POST_붙여넣기용.txt').read_text(encoding='utf-8-sig')
    lines=[line for line in cafe.splitlines() if not line.startswith('※ 공개 게시 전 확인용')]
    text='\n'.join(lines).strip()+'\n'
    ends=[text.index(x) for x in ('■ 제작·검증 정보','■ xdelta 적용','■ 배포 파일','■ 검증 및 다운로드') if x in text]
    text=text[:min(ends)] if ends else text
    download=f'https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/download/{version}/SRWOGS_AxelRoleSwap_kr_{version}.zip'
    text+='■ xdelta 적용\n\n기준 한글패치 v1.4.3s1 적용본에만 사용합니다. 다섯 선택 옵션이 모두 꺼진 결과를 만듭니다. 옵션을 사용하려면 빠른 패처를 이용해 주세요.\n\nxdelta.exe -d -s "srwogs-v1.4.3s1.iso" "SRWOGS_AxelRoleSwap_kr_v20261029.1.xdelta" "출력.iso"\n\n워단 생존·삼식 추가 지급·무명 6화 지급은 모든 옵션 조합과 xdelta에 기본 적용됩니다. 이전 버전과 결과 ISO가 다릅니다.\n\n■ 검증 및 다운로드\n\n32개 조합의 전체 ISO 해시, 패처 내부 5,120개 전환, 실제 ISO의 32개 조합 적용 및 대표 조합 백업 복원을 확인했습니다. 모든 시나리오와 전투 연출의 실플레이를 새로 완료한 것은 아닙니다.\n\n'
    text+=download+'\n\n게임 ISO는 배포하지 않습니다.\n'
    (rel/'읽어주세요.txt').write_text(text,encoding='utf-8-sig')
    def markdown(t):
        out=[]
        for line in t.splitlines():
            if line.startswith('제목: '):out.append('# '+line[4:])
            elif line.startswith('■ '):out.append('## '+line[2:])
            elif line.startswith('· '):out.append('- '+line[2:])
            else:out.append(line)
        return '\n'.join(out)+'\n'
    notes=markdown(text)
    (W/'runtime/release_notes.md').write_text(notes,encoding='utf-8')
    (rel/'CHANGELOG.md').write_text(notes,encoding='utf-8')
    (rel/'옵션별_ISO_SHA256.json').write_text(json.dumps(profiles,ensure_ascii=False,indent=2),encoding='utf-8')
    checksum=''.join(sha(f)+'  '+f.relative_to(rel).as_posix()+'\n' for f in sorted(rel.rglob('*')) if f.is_file())
    (rel/'SHA256SUMS.txt').write_text(checksum,encoding='utf-8-sig')
    z=DIST/f'SRWOGS_AxelRoleSwap_kr_{version}.zip';tmp=z.with_suffix('.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for f in sorted(rel.rglob('*')):
            if f.is_file():archive.write(f,'SRWOGS_AxelRoleSwap_kr_'+version+'/'+f.relative_to(rel).as_posix())
    tmp.replace(z)
    with zipfile.ZipFile(z) as archive:
        need(archive.testzip() is None,'Release ZIP CRC failure')
        for f in rel.rglob('*'):
            if f.is_file():need(hashlib.sha256(archive.read('SRWOGS_AxelRoleSwap_kr_'+version+'/'+f.relative_to(rel).as_posix())).hexdigest().upper()==sha(f),'ZIP entry mismatch')
    # Public docs include the cumulative change list requested by the user.
    long_notes=notes[notes.index('## 이번 업데이트'):]
    old_changelog=(repo/'CHANGELOG.md').read_text(encoding='utf-8')
    need('## '+version+' ' not in old_changelog,'Release notes already staged; inspect before rerun')
    (repo/'CHANGELOG.md').write_text('# 변경 내역\n\n## '+version+' (2026-10-29)\n\n'+long_notes+'\n'+old_changelog.removeprefix('# 변경 내역').lstrip(),encoding='utf-8')
    overview='# Super Robot Wars OGs — 액셀 알마 역할 교체 패치\n\nPS2 『슈퍼로봇대전 OG ORIGINAL GENERATIONS』의 라미아 아군 루트를 액셀로 플레이하는 패치입니다. **OGs 한글패치 v1.4.3s1 적용본**을 대상으로 합니다.\n\n현재 버전: **v20261029.1**\n\n[패처 ZIP 다운로드](DOWNLOAD) · [릴리즈](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/releases/tag/v20261029.1) · [전체 변경내역](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/blob/main/CHANGELOG.md)\n\n## 적용 방법\n\n1. ZIP을 폴더째 풉니다.\n2. `patcher/OGS_AxelSwap_QuickPatch.exe`에서 ISO를 선택합니다.\n3. 원하는 옵션을 체크하고 [패치 적용]을 누릅니다. **다섯 옵션의 기본값은 모두 꺼짐**입니다.\n4. 에뮬레이터를 완전히 다시 실행하고 **게임 내 메모리카드 세이브**로 불러옵니다. 이전 세이브 스테이트는 사용하지 마세요.\n\n| 독립 선택 옵션 | 내용 |\n|---|---|\n| 숨겨진 요소 자동 습득 (OG2) | 원래 획득 시점의 조건 해제 |\n| 오우카 생존 + 젠가 밸런스 | 44화 양쪽 루트 오우카 합류·45화 후속 대사, 다이젠가 강화·8무장 통합 |\n| 자금 +20% · PP 2배 | 적 격추 보상 증가 |\n| 적 강화 | 적 파일럿 6개 능력치 +5, 기체·무기 기본 개조 +1단, 기본 HP 20,000 미만 적 HP +10% |\n| 액셀·제오라 정신기 변경 | 액셀 철벽·혼·각성 SP 조정, 제오라 번뜩임·가속 |\n\n같은 ISO에서 체크를 바꾸고 재적용할 수 있습니다. 해제한 옵션의 패치 데이터는 원래대로 복원합니다. 이미 세이브에 쌓인 자금·PP·보유품·합류 기록은 회수하지 않습니다. 패처 옆 `.bin` 파일은 모두 함께 두세요. `.ogsbak`으로 마지막 작업 직전 상태를 복원할 수 있습니다.\n\n기준 한글판 및 v20260831·v20260904·v20261002·v20261024·v20261025·v20261025.1·v20261026·v20261027·v20261027.1·v20261028·v20261029 공개 적용본을 지원합니다. v20261026의 네 조합과 새 32개 조합 사이에서도 전환할 수 있습니다.\n\n## 기본 적용 사항\n\n- **아군 슬레이드겔미르** HP8300·장갑2100·6무장 공격력+200. 성체의태도 P/사거리1~2/배리어 관통. 적 원형은 유지합니다.\n- **44화 마지막 결전 후 워단(W15)이 생환하여 슬레이드겔미르에 합류**합니다. 기존 기체와 개조값을 재사용하며 다른 탑승 파일럿 기록은 유지합니다. 오우카 생존 옵션과 별개로 기본 적용됩니다.\n- **37화 클리어 후 그룬거스트 삼식**(젠가의 참식참함도 장착형)을 기체만 추가 지급합니다. 기존 다른 삼식은 유지하고 젠가 갈아타기를 지원합니다.\n- OG2 **6화 종료 후 가리온 커스텀 무명**을 미보유한 경우 기체만 지급합니다. 5화 지급은 제거했습니다.\n- OG2 6화 클리어 후 **부스트 해머·시시오 블레이드·G 임팩트 스테이크·강철의 혼·용자의 증표·고성능 전자두뇌** 각각 1개 추가.\n- OG2 37화 클리어 후 **슬레이드겔미르** 기체만 지급. 젠가 갈아타기 지원.\n- 기존 소울게인·바이사가·아슈세이버 획득 및 갈아타기 조정 유지.\n- 소울게인·바이사가 무장별 대사·음성 연결 수정, 시나리오 대사·호칭·문자 깨짐 교정, 적 라미아·안쥬르그 조정 유지.\n- 아우센자이터 무장 공격력 +200 및 배리어 관통, 알트아이젠 리제 배리어 관통, 공용 시시오 블레이드·암검살·스태그 비틀 크래셔 사거리 조정 등 유지.\n\n전체 수치와 획득 시점은 아래 누적 릴리즈 노트에 정리했습니다. **지나간 화의 보상은 소급 지급하지 않습니다.** 오우카 생존은 44화 결말 이전부터 진행해야 합니다. 적 기본 개조는 적이 생성될 때 적용됩니다.\n\n## xdelta\n\n`SRWOGS_AxelRoleSwap_kr_v20261029.1.xdelta`는 기준 한글판 전용이며 다섯 옵션이 모두 꺼진 결과를 만듭니다. 워단 생존·삼식 추가 지급·무명 6화 지급은 모든 옵션 조합에 기본 적용됩니다.\n\n```text\nxdelta.exe -d -s "srwogs-v1.4.3s1.iso" "SRWOGS_AxelRoleSwap_kr_v20261029.1.xdelta" "출력.iso"\n```\n\n## 검증\n\n32개 결과 ISO 전체 해시, 5,120개 옵션 전환, 실제 ISO의 32개 조합 적용과 대표 백업 복원을 검증했습니다. 전체 시나리오의 실플레이 검증을 새로 완료한 것은 아닙니다.\n\n모든 조합의 ISO 크기는 4,518,150,144바이트입니다. 각 결과 해시는 ZIP의 `옵션별_ISO_SHA256.json`에 있습니다.\n\n게임 ISO와 세이브는 배포하지 않습니다.\n\n'
    overview=overview.replace('DOWNLOAD',download)
    (repo/'README.md').write_text(overview.rstrip()+'\n',encoding='utf-8')
    (repo/'docs/home.md').write_text(overview.rstrip()+'\n',encoding='utf-8')
    (repo/'docs/patch-notes.md').write_text(notes,encoding='utf-8')
    sidebar=(repo/'docs/_sidebar.md').read_text(encoding='utf-8').replace('v20261029.zip','v20261029.1.zip')
    (repo/'docs/_sidebar.md').write_text(sidebar,encoding='utf-8')
    shutil.copyfile(delta,repo/'patch'/delta.name)
    info=json.loads((repo/'patch/PATCH_INFO.json').read_text(encoding='utf-8'))
    info.update(version=version,built='2026-10-29',status='RELEASED')

    info['previous']='v20261029'
    info['changes']=['아군 슬레이드겔미르 HP8300·장갑2100·6무장 공격력+200, 성체의태도 P/사거리1~2/배리어 관통; 적 원형 유지','5화 무명 지급 삽입 제거, 6화 종료 무명 지급으로 통일', '아군 무명 HP6300, 시시오 블레이드4600, 무명2도인기참5600; 적 무라타 유지', '무기 개조비용 최저등급 유지, 나머지20% 인하', '오우카 생존 옵션: 다른44화 루트 합류와45화 후속대사 수정', '적 강화 옵션: 기본HP20000미만 적HP10% 추가', '베어울프 테스트 제외', '자금+20%·PP2배 / 적 강화 / 액셀·제오라 정신기 변경을 독립 선택 옵션으로 추가',
        '기존 숨겨진 요소·오우카 생존+젠가 밸런스 옵션 유지; 모두 기본 OFF',
        '32개 옵션 조합 및 5120개 전환 검증',
        '무명·슬레이드겔미르 획득, 6화 추가 보상 및 기존 무장·대사 조정을 누적 릴리즈 노트에 정리']

    info['result_iso'].update(sha256=profiles['hashes'][0],md5=default_md5)
    info['patch'].update(file=delta.name,size=delta.stat().st_size,sha256=sha(delta),md5=md5(delta))
    info['quickpatch']['exe_sha256']=sha(QP/'OGS_AxelSwap_QuickPatch.exe')
    info['quickpatch']['verified']='32 full ISO profiles, 5120 composition transitions, real ISO patch/restore checks passed'
    info['quickpatch']['core_pack_default_sha256']=profiles['previous_hashes'][0]
    info['quickpatch']['optional_hidden_rewards']['result_iso_sha256']=profiles['hashes'][1]
    info['quickpatch']['optional_ouka_zengar']['result_iso_sha256']=profiles['hashes'][2]
    info['quickpatch']['optional_ouka_zengar']['both_options_result_iso_sha256']=profiles['hashes'][3]
    info['quickpatch']['common_fix']=dict(file='OGS_common_fix.bin',sha256=sha(QP/'OGS_common_fix.bin'),always_enabled=True)
    info['quickpatch']['optional_features']=dict(file='OGS_optional_features.bin',sha256=sha(QP/'OGS_optional_features.bin'),defaults_off=True,profiles=profiles)
    info['release_zip']=dict(file=z.name,size=z.stat().st_size,sha256=sha(z))
    (repo/'patch/PATCH_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    cafe=text+'\n■ 배포 파일\n\n'+z.name+'\n크기: '+format(z.stat().st_size,',')+' 바이트\nSHA256: '+sha(z)+'\n'
    (W/'CAFE_POST_붙여넣기용.txt').write_text(cafe.rstrip()+'\n',encoding='utf-8-sig')
    release=dict(version=version,zip=str(z),zip_sha256=sha(z),zip_size=z.stat().st_size,
        delta=str(delta),delta_sha256=sha(delta),default_iso_sha256=profiles['hashes'][0],all_options_iso_sha256=profiles['hashes'][31],xdelta_decode_verified=True)
    (W/'runtime/optional_features_release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copyfile(W/'runtime/optional_features_release.json',repo/'work_ogs/validation/optional_features_release.json')
    shutil.copyfile(Path(__file__),repo/'work_ogs'/Path(__file__).name)
    print(json.dumps(release,ensure_ascii=False,indent=2),flush=True)


def publish_options_release():
    """Publish the guarded v20261027 assets; retain older releases."""
    version='v20261029.1';repo=ROOT/'ogs-repo'
    metadata=json.loads((W/'runtime/optional_features_release.json').read_text(encoding='utf-8'))
    files=[Path(metadata['zip']),Path(metadata['delta'])]
    need(sha(files[0])==metadata['zip_sha256'] and sha(files[1])==metadata['delta_sha256'],'Release assets changed')
    need(not subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip(),'Commit source/doc updates before publish')
    token=next((line.split('=',1)[1].strip().strip('"').strip("'") for line in (ROOT/'.env').read_text(encoding='utf-8').splitlines() if line.startswith('GITHUB_TOKEN=')),None)
    need(bool(token),'Release authentication unavailable')
    api_root='https://api.github.com/repos/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch'
    def api(method,url,data=None,ctype='application/json'):
        req=urllib.request.Request(url,method=method,data=data,headers={'Authorization':'Bearer '+token,
            'Accept':'application/vnd.github+json','Content-Type':ctype,'User-Agent':'ogs-release-patcher'})
        with urllib.request.urlopen(req,timeout=120) as response:return json.loads(response.read() or b'{}')
    run('git','-C',repo,'push','origin','main')
    head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    body=(W/'runtime/release_notes.md').read_text(encoding='utf-8')
    body+='\n\nZIP SHA256: `'+metadata['zip_sha256']+'`\n'
    # A published version must never be silently replaced by rerunning a build.
    try:
        existing=api('GET',api_root+'/releases/tags/'+version)
        need(existing['draft'],'This version is already public; inspect before changing it')
        rel=existing
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        rel=api('POST',api_root+'/releases',json.dumps(dict(tag_name=version,target_commitish=head,
            name='OGs 액셀 역할 교체 패치 '+version+' — 아군 슬레이드겔미르 조정',
            body=body,draft=True,prerelease=False),ensure_ascii=False).encode())
    for file in files:
        matches=[a for a in rel.get('assets',[]) if a['name']==file.name]
        if matches:
            need(matches[0].get('digest','').lower()=='sha256:'+sha(file).lower(),'Existing draft asset differs')
            continue
        uploaded=api('POST',rel['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(file.name),file.read_bytes(),
            'application/zip' if file.suffix=='.zip' else 'application/octet-stream')
        need(uploaded['size']==file.stat().st_size,'Upload size mismatch')
        need(uploaded.get('digest','').lower()=='sha256:'+sha(file).lower(),'Uploaded digest mismatch')
    rel=api('PATCH',rel['url'],json.dumps(dict(body=body,target_commitish=head,draft=False,make_latest='true'),ensure_ascii=False).encode())
    verified=[]
    for file in files:
        asset=next(a for a in rel['assets'] if a['name']==file.name)
        with urllib.request.urlopen(asset['browser_download_url'],timeout=120) as response:
            h=hashlib.sha256()
            while chunk:=response.read(4<<20):h.update(chunk)
        need(h.hexdigest().upper()==sha(file),'Public download hash mismatch')
        verified.append(asset['browser_download_url'])
    latest=api('GET',api_root+'/releases/latest');need(latest['tag_name']==version,'Latest release mismatch')
    result=dict(release=rel['html_url'],tag=version,commit=head,assets=verified,zip_sha256=metadata['zip_sha256'],download_verified=True)
    (W/'runtime/optional_features_publish.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__ == "__main__":
    if "--common-xdelta" in sys.argv:build_common_xdelta()
    elif "--release-options" in sys.argv:prepare_options_release()
    elif "--publish-options" in sys.argv:publish_options_release()
    else:main()
