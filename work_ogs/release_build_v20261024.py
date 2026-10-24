# -*- coding: utf-8 -*-
"""v20261024 릴리즈 산출물 일괄 생성 (build/SRWOGS_K.iso 기준).

xdelta → 전체 구간 팩 → 업그레이드 팩(v20260831, v20260904, v20261002 적용본 → 신판)
→ 패처 E2E(기준본/세 업그레이드 경로/복원) → release_v20261024 폴더·SHA256SUMS·ZIP.
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

V = "v20261024"
W = Path(__file__).resolve().parent
ROOT = W.parent
XD = ROOT / "xdelta.exe"
ISO = W / "build" / "SRWOGS_K.iso"
BASE = W / "baseline" / "srwogs-v1.4.3s1.iso"
DIST = W / "dist"
QP = W / "iso_quickpatch"
REL = W / f"release_{V}"
BASE_SHA = "9D39F5EA9E560E864A9FC4B0ABC234FD42619D846FC1A9C2A98CBA19CF5D5A0C"
EXPECT = "5432A2F5066DB50E54511AB2C3A0744A56911FA4510A519AB65FB803CE7114A8"
HIDDEN_EXPECT = "687397FA1E1B57CB6FD547B3D6A23701B7AE529C500B491360B6B69566EB1735"
OLD = [  # (라벨, xdelta, 복원 해시)
    ("v20260831", DIST / "old_v20260831" / "SRWOGS_AxelRoleSwap_kr_v20260831.xdelta",
     "08615F303D301AC9935A7C71379D8AE4BD5B2F9E0C2B328397D103FD0352B930"),
    ("v20260904", DIST / "SRWOGS_AxelRoleSwap_kr_v20260904.xdelta",
     "831A646BCDE363B92A1E8CD2C5CACE786102A61833A5757BB155B527CF35B9CC"),
    ("v20261002", DIST / "SRWOGS_AxelRoleSwap_kr_v20261002.xdelta",
     "747832E0310F6CD4B23A702FC1FC928C19F6D44B8B51879184FCC2459BEF6915"),
]
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

def hidden_pack():
    m = json.loads((W / 'runtime/hidden_rewards_manifest.json').read_text(encoding='utf-8'))
    need(m['source_sha256'].upper() == EXPECT and m['target_sha256'].upper() == HIDDEN_EXPECT, '옵션 매니페스트 해시 오류')
    with (QP / 'OGS_hidden_rewards.bin').open('wb') as f:
        f.write(b'OGSHID01'); f.write(struct.pack('<Q', ISO.stat().st_size))
        f.write(bytes.fromhex(EXPECT)); f.write(bytes.fromhex(HIDDEN_EXPECT)); f.write(struct.pack('<I',len(m['edits'])))
        for e in m['edits']:
            old,new=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
            need(len(old)==len(new),'옵션 길이 오류')
            f.write(struct.pack('<QI',e['offset'],len(old)));f.write(old);f.write(new)

def test_options():
    hidden_pack()
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
            run(XD,'-d','-f','-s',BASE,xd,t);need(sha(t)==expected,'구판 복원 오류')
            action(label+' → 자동 습득 포함',HIDDEN_EXPECT,'--cli','--hidden')
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
    hidden_pack()
    if '--publish' in sys.argv:
        publish();return
    if '--test-options' in sys.argv:
        test_options();return

    if package_only:
        exe = QP / "OGS_AxelSwap_QuickPatch.exe"
        need(XDELTA_OUT.exists(), "xdelta 없음")
        return package(exe)
    # Build the default-off target by reversing only the optional manifest.
    # The working ISO remains the user's requested automatic-reward variant.
    default_iso = DIST / 'DEFAULT_BUILD.iso'
    shutil.copyfile(ISO,default_iso)
    m=json.loads((W/'runtime/hidden_rewards_manifest.json').read_text(encoding='utf-8'))
    with default_iso.open('r+b') as f:
        for e in m['edits']:
            f.seek(e['offset']);need(f.read(len(bytes.fromhex(e['after'])))==bytes.fromhex(e['after']),'옵션 원복 가드 오류')
            f.seek(e['offset']);f.write(bytes.fromhex(e['before']))
    need(sha(default_iso)==EXPECT,'기본 패치 복원 오류')
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
        run(XD, "-d", "-f", "-s", BASE, xd, tmp)
        need(sha(tmp) == exp, f"{label} 복원 불일치")
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
        run(XD, "-d", "-f", "-s", BASE, xd, t)
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
            "__ISO_MD5__": "FF94B73361C05CD984D16E072A160BAE",
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
    """Update the existing release ZIP; keep the default xdelta and tag intact."""
    repo=ROOT/'ogs-repo';z=DIST/f'SRWOGS_AxelRoleSwap_kr_{V}.zip'
    need(z.exists(),'릴리즈 ZIP 없음')
    token=next((line.split('=',1)[1].strip().strip('"').strip("'")
                for line in (ROOT/'.env').read_text(encoding='utf-8').splitlines()
                if line.startswith('GITHUB_TOKEN=')),None)
    need(bool(token),'릴리즈 인증 없음')
    api_root='https://api.github.com/repos/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch'
    def api(method,url,data=None,ctype='application/json'):
        req=urllib.request.Request(url,method=method,data=data,headers={
            'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
            'Content-Type':ctype,'User-Agent':'ogs-release-patcher'})
        with urllib.request.urlopen(req,timeout=120) as response:
            return json.loads(response.read() or b'{}')
    rel=api('GET',api_root+'/releases/tags/'+V)
    need(rel['tag_name']==V and not rel['draft'],'기존 릴리즈 식별 실패')
    # Publish sources first. The existing release tag continues to identify the
    # unchanged default xdelta; this commit identifies the optional patcher update.
    run('git','-C',repo,'push','origin','main')
    head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    temporary=z.stem+'.uploading.zip'
    need(not any(a['name']==temporary for a in rel['assets']),'이전 업로드 임시 자산 확인 필요')
    uploaded=api('POST',rel['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(temporary),z.read_bytes(),'application/zip')
    # Verify the bytes using the download endpoint, before replacing the old ZIP.
    with urllib.request.urlopen(uploaded['browser_download_url'],timeout=120) as response:
        h=hashlib.sha256()
        while b:=response.read(4<<20):h.update(b)
    need(h.hexdigest().upper()==sha(z),'업로드 후 다운로드 해시 불일치')
    for asset in rel['assets']:
        if asset['name']==z.name:api('DELETE',asset['url'])
    uploaded=api('PATCH',uploaded['url'],json.dumps({'name':z.name}).encode())
    section='''## 추가 업데이트: 숨겨진 요소 자동 습득 옵션

빠른패처 UI를 OGMD 스타일로 바꾸고 **숨겨진 요소 자동 습득 (OG2)** 체크박스를 추가했습니다. 기본값은 꺼짐입니다.
체크하면 숨겨진 무기·기체·강화파츠를 원래 획득 시점에 조건 없이 받습니다. 22화 인스펙터 보상은 보스 격추 없이 클리어 시 지급하며 중복하지 않습니다.
이미 지난 화의 보상은 소급 지급하지 않습니다. 기존 대사·라미아 밸런스·AP 음성·소울게인/바이사가/아슈세이버 변경은 보존했습니다.

- 기존 v20261024 적용본에서도 옵션 켜기·끄기 가능. 저장한 보유품은 옵션을 꺼도 회수하지 않습니다.
- xdelta 단독 적용 결과는 기존과 같습니다. 자동 습득은 새 ZIP의 빠른패처에서 선택하세요.
- 실제 게임 분기/지급 코드 오프라인 실행 및 기본/구버전 업그레이드/옵션 전환/백업 복원 해시 검증 통과. 전 루트 실플레이는 미검증입니다.
- 자동 습득 선택 결과 SHA-256: `'''+HIDDEN_EXPECT+'''`
- [옵션 구현 소스](https://github.com/kimjh-eclipse/super-robot-wars-ogs-axel-korean-patch/commit/'''+head+''')

'''
    body=rel.get('body','')
    body=re.sub(r'ZIP SHA-256: `[^`]+`','ZIP SHA-256: `'+sha(z)+'`',body)
    if '## 추가 업데이트: 숨겨진 요소 자동 습득 옵션' not in body:body=section+body
    api('PATCH',rel['url'],json.dumps({'body':body},ensure_ascii=False).encode('utf-8'))
    check=api('GET',api_root+'/releases/tags/'+V)
    asset=next(a for a in check['assets'] if a['name']==z.name)
    need(asset['size']==z.stat().st_size,'최종 자산 크기 오류')
    report=dict(release=check['html_url'],zip_url=asset['browser_download_url'],zip_sha256=sha(z),commit=head,download_verified=True)
    (W/'runtime/hidden_rewards_publish.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__ == "__main__":
    main()
