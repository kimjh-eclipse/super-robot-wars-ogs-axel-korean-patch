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


if __name__ == "__main__":
    main()
