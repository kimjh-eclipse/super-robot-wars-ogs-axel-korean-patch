# -*- coding: utf-8 -*-
"""v20261025 릴리즈 산출물 일괄 생성 (build/SRWOGS_K.iso 기준).

xdelta → 전체 구간 팩 → 업그레이드 팩(v20260831, v20260904, v20261002 적용본 → 신판)
→ 패처 E2E(기준본/구판 및 옵션ON 적용본/복원) → release_v20261025 폴더·SHA256SUMS·ZIP.
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

V = "v20261025"
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
HIDDEN_EXPECT = "8499BE55449D6026831DF7697185BA12E5009492ED584B21B645D3DAFE7AD3FB"
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
    if label.endswith('_hidden'):
        m=json.loads((W/'runtime/hidden_rewards_manifest.json').read_text(encoding='utf-8'))
        need(sha(target)==m['source_sha256'].upper(),'Old option source mismatch')
        with target.open('r+b') as f:
            for e in m['edits']:
                old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                f.seek(e['offset']);need(f.read(len(old))==old,'Old option guard')
                f.seek(e['offset']);f.write(new)
    need(sha(target)==expected,'Old release reconstruction mismatch: '+label)


def prepare_default():
    global EXPECT
    target=DIST/'DEFAULT_BUILD.iso';shutil.copyfile(ISO,target)
    # Preflight LOGO88 lookup repair belongs to the option; LOGO138 repair is common.
    repair=json.loads((W/'runtime/release_preflight_manifest.json').read_text(encoding='utf-8'))
    from build_hidden_rewards import Scripts,MAP
    scripts=Scripts();at,size=scripts.logos[88]
    with target.open('r+b') as f:
        for e in repair['edits']:
            if MAP+at<=e['offset']<MAP+at+size:
                old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
                f.seek(e['offset']);need(f.read(len(new))==new,'Option lookup reverse guard')
                f.seek(e['offset']);f.write(old)
        m=json.loads((W/'runtime/hidden_rewards_manifest.json').read_text(encoding='utf-8'))
        for e in m['edits']:
            old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
            f.seek(e['offset']);need(f.read(len(new))==new,'Option reverse guard')
            f.seek(e['offset']);f.write(old)
    EXPECT=sha(target)
    metadata=dict(version=V,default_sha256=EXPECT,hidden_sha256=HIDDEN_EXPECT,default_md5=md5(target))
    (W/'runtime/release_build_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return target


def hidden_pack():
    spec=importlib.util.spec_from_file_location('ranges',QP/'build_range_pack.py')
    ranges=importlib.util.module_from_spec(spec);spec.loader.exec_module(ranges)
    default=DIST/'DEFAULT_BUILD.iso';entries=ranges.find_ranges(default,ISO)
    need(sha(default)==EXPECT and sha(ISO)==HIDDEN_EXPECT,'Option target guard')
    with (QP/'OGS_hidden_rewards.bin').open('wb') as f, default.open('rb') as a, ISO.open('rb') as b:
        f.write(b'OGSHID01');f.write(struct.pack('<Q',ISO.stat().st_size))
        f.write(bytes.fromhex(EXPECT));f.write(bytes.fromhex(HIDDEN_EXPECT));f.write(struct.pack('<I',len(entries)))
        for off,size in entries:
            a.seek(off);b.seek(off);f.write(struct.pack('<QI',off,size));f.write(a.read(size));f.write(b.read(size))


def test_options():
    exe=QP/'OGS_AxelSwap_QuickPatch.exe';t=QP/'TEST.iso';bak=Path(str(t)+'.ogsbak')
    results=[]
    def action(label, expected, *flags):
        run(exe,t,*flags);need(sha(t)==expected,label+' 결과 해시 실패');results.append(label)
        print('PASS',label,flush=True)
    try:
        shutil.copyfile(BASE,t)
        action('기준본 → 기본 옵션',EXPECT,'--cli')
        action('기본 옵션 백업 복원',BASE_SHA,'--restore')
        action('기준본 → 자동 습득 포함',HIDDEN_EXPECT,'--cli','--hidden')
        before_bak=sha(bak)
        action('자동 습득 재적용 무변경',HIDDEN_EXPECT,'--cli','--hidden')
        need(sha(bak)==before_bak,'무변경 재적용이 백업을 변경함')
        action('합성 패치 백업 복원',BASE_SHA,'--restore')
        action('기본 패치 재적용',EXPECT,'--cli')
        action('기본 패치 → 자동 습득 켜기',HIDDEN_EXPECT,'--cli','--hidden')
        action('자동 습득 → 기본 옵션 끄기',EXPECT,'--cli')
        action('옵션 해제 백업 복원',HIDDEN_EXPECT,'--restore')
        for label,xd,expected in OLD:
            restore_old(label,xd,expected,t)
            action(label+' → 자동 습득 포함',HIDDEN_EXPECT,'--cli','--hidden')
            action(label+' 업그레이드 백업 복원',expected,'--restore')
            action(label+' → 기본 옵션',EXPECT,'--cli')
        report=dict(passed=True,paths=results,base_iso_sha256=EXPECT,hidden_iso_sha256=HIDDEN_EXPECT)
        (W/'runtime/hidden_rewards_patcher_e2e.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        t.unlink(missing_ok=True);bak.unlink(missing_ok=True)


def main() -> None:
    out = subprocess.run(["tasklist"], capture_output=True, text=True, errors="ignore").stdout.lower()
    need("pcsx2" not in out and "srwz" not in out, "PCSX2 실행 중")
    package_only = "--package-only" in sys.argv
    print("[0] 해시 가드")
    need(sha(BASE) == BASE_SHA, "기준 ISO 해시 불일치")
    need(sha(ISO) == HIDDEN_EXPECT, "SRWOGS_K.iso 해시 불일치")
    global EXPECT
    if any(x in sys.argv for x in ('--publish','--test-options','--package-only')):
        meta=json.loads((W/'runtime/release_build_metadata.json').read_text(encoding='utf-8'))
        need(meta['version']==V and meta['hidden_sha256']==HIDDEN_EXPECT,'Build metadata mismatch')
        EXPECT=meta['default_sha256']
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

    print("[4] 패처 E2E")
    exe = QP / "OGS_AxelSwap_QuickPatch.exe"
    t = QP / "TEST.iso"
    bak = Path(str(t) + ".ogsbak")

    def patch_and_check(label):
        run(exe, t, "--cli")
        need(sha(t) == EXPECT, f"E2E {label} 실패")
        print(f"  E2E {label} OK")

    shutil.copyfile(BASE, t)
    patch_and_check("기준본→신판")
    run(exe, t, "--restore")
    need(sha(t) == BASE_SHA, "E2E 복원 실패")
    print("  E2E 복원 OK")
    for label, xd, _ in OLD:
        bak.unlink(missing_ok=True)
        restore_old(label,xd,_,t)
        patch_and_check(f"{label}→신판")
    t.unlink()
    bak.unlink(missing_ok=True)

    default_iso.unlink()
    test_options()
    package(exe)


def package(exe: Path) -> None:
    print("[5] 패키지")
    result=json.loads((W/'runtime/hidden_rewards_patcher_e2e.json').read_text(encoding='utf-8'))
    need(result.get('passed') and result['hidden_iso_sha256']==HIDDEN_EXPECT,'패처 E2E 검증 미완료')
    if REL.exists():
        keep = {p.name: p.read_bytes() for p in REL.glob("*.txt")}
        remove_build_tree(REL)
    else:
        keep = {}
    (REL / "patcher").mkdir(parents=True)
    (REL / "xdelta").mkdir()
    for p in [exe, QP / "OGS_ISO_ranges.bin", QP/'OGS_hidden_rewards.bin', *sorted(QP.glob("OGS_ISO_ranges_upgrade_*.bin"))]:
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
              "", "숨겨진 요소 자동 습득 선택 결과 ISO", f"{HIDDEN_EXPECT}  (4,518,150,144B)"]
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
    need(report['passed'] and report['hidden_iso_sha256']==HIDDEN_EXPECT,'E2E incomplete')
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
        name='OGs 액셀 역할 교체 패치 '+V+' — 추가 기체·보상 및 다이젠가 환장',
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
