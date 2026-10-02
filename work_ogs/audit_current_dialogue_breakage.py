# -*- coding: utf-8 -*-
"""CURRENT ISO의 누적 수정 대사에서 화면 파손·문법 잔재를 전수 추출한다."""
from __future__ import annotations

import json
import argparse
import hashlib
import mmap
import re
from collections import Counter, defaultdict
from pathlib import Path

from build_og2new_scene_workbench import iso_rows
from ogs_korean_codec import decode, encode


ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
DRAFT = ROOT / "runtime" / "og2new_tone_pass01_33_combined.json"
HOTFIX = ROOT / "runtime" / "stage35_vysaga_hotfix_manifest.json"
REPORT = ROOT / "CURRENT_DIALOGUE_BREAKAGE_AUDIT_2026-08-31.md"
MAP_ISO_OFF = 0xC10800

ROLE_SPEAKERS = {"액셀", "라미아", "레몬", "빈델", "에키드나", "쿄스케", "엑셀렌"}
HARD_PATTERNS = {
    "붙은말·조사 파손": re.compile(r"이라이|어쩔생각|그여자|이녀석|한명|아까전|할수|없을리|할텐데|그겁니까|이겁니까…|말입니다？"),
    "호칭 뒤 비칭 충돌": re.compile(r"(?:레몬|빈델)님.{0,14}(?:녀석|네놈|너희)|(?:레몬|빈델)님이랑"),
    "어미 중복·혼합": re.compile(r"말입니까。|입니까。|습니다。.{0,8}(?:인가|이야|군|하지)|인가요인가|이라구。\s*이게"),
    "문장 조각": re.compile(r"이라　이겁니까|이　생각입니까|말이지@　이게|말이지 / 　이게"),
}


def speaker(text: str) -> str:
    for sep in ("：", "（"):
        if sep in text:
            return text.split(sep, 1)[0]
    return ""


def shown(text: str) -> str:
    return text.replace("@", " / ")


def full_current_audit():
    """Read-only ISO audit; update the existing report, never the game image.

    A full-image anchor scan checks coverage independently of the historical
    workbench window. Semantic flags are review candidates, not proof.
    """
    with ISO.open('rb') as source:
        image=mmap.mmap(source.fileno(),0,access=mmap.ACCESS_READ)
        entries={}
        for label in ('라미아：','라미아（','Ｗ１７：','Ｗ１７（'):
            needle=encode(label);at=0
            while True:
                at=image.find(needle,at)
                if at<0:break
                end=image.find(b'\0',at,min(at+1024,len(image)))
                if end>at:
                    raw=image[at:end]
                    entries[at-MAP_ISO_OFF]={'off':at-MAP_ISO_OFF,'raw':raw,
                        'text':decode(raw),'boundary':at>0 and image[at-1]==0}
                at+=len(needle)
        digest=hashlib.sha256()
        for at in range(0,len(image),8*1024*1024):
            digest.update(image[at:at+8*1024*1024])
        image.close()
    rows=iso_rows(ISO);by_off={r['off']:i for i,r in enumerate(rows)}
    counts=Counter();flagged=[]
    for off,r in sorted(entries.items()):
        text=r['text'];reasons=[]
        ascii_chars=sorted(set(c for c in text if ord(c)<128 and c!='@'))
        if ' ' in text:reasons.append('反角공백');counts['halfwidth_space']+=1
        other=[c for c in ascii_chars if c!=' ']
        if other:reasons.append('기타ASCII(제어문법여부확인):'+repr(''.join(other)));counts['other_ascii']+=1
        try:roundtrip=encode(text)==r['raw']
        except UnicodeError:roundtrip=False
        if not roundtrip or '\ufffd' in text:reasons.append('인코딩왕복실패');counts['encoding']+=1
        if text.count('@')>2:reasons.append('4줄이상');counts['line_count']+=1
        if max(map(len,text.split('@')))>27:reasons.append('27자초과줄(화면확인)');counts['long_line']+=1
        for a,b in [('（','）'),('『','』')]:
            if text.count(a)!=text.count(b):reasons.append('괄호불균형:'+a+b);counts['brackets']+=1
        if any(p in text for p in ('인형들','인형들을','내　부하','당신이　세운','그　이레귤러에')):
            reasons.append('관계/문장수동검토');counts['semantic_candidate']+=1
        r['reasons']=reasons
        if reasons:flagged.append(r)
    known={0x6682673:'스크린샷 확인: 반각 공백과 어색한 문장. 최근 117슬롯 수정 대상 밖.',
           0x6681DE1:'레몬이 라미아에게 당신이라고 부름. 앞뒤 너/W17 호칭과 불일치.',
           0x66816CD:'W16의 옛: 앞뒤 평어와 혼재. 원 슬롯 10바이트라 알았다 단순 치환도 용량 재검증 필요.',
           0x6662AC5:'W16 완료되었습니다: 앞의 보고하겠다와 말투 혼재.',
           0x6662B87:'W16 네/말씀하셨습니다: 라미아와의 평어 대화 중 존댓말.',
           0x6662C62:'W16 실행할뿐입니다/없습니다: 라미아에게 하는 말투 재검토.'}
    lines=['# CURRENT 대사 파손 전수 조사 (2026-10-02 갱신)','',
        '- 이 감사 실행은 읽기 전용이다. 별도 복구 도구로 CURRENT ISO에는 수정이 적용되었다.',
        '- 라미아 반각 공백 52개 및 다른 화자의 패치 유입 반각 공백 30개는 기존 복구 기록에 따라 수정되었다.',
        '- SHA256: `'+digest.hexdigest().upper()+'`',
        f'- 전체 ISO 화자 앵커: {len(entries)}개. 라미아 및 전각 W17 직접대사/독백.',
        f'- 기존 시나리오 구간 밖 앵커: {sum(not 0x5C00000<=off<0x6900000 for off in entries)}개.',
        f'- 직전 NUL 경계 확인: {sum(r["boundary"] for r in entries.values())}개.',
        '- 검사 집계: `'+json.dumps(counts,ensure_ascii=False)+'`',
        '- 전수 검사는 문자열/구조 자동 검사다. 786개 모두의 이야기 의미를 수동 검토했다는 뜻은 아니다.',
        '- 반각 공백은 실기 재현된 파손 위험. ASCII 꺾쇠는 제어문법 가능성이 있어 별도 후보로 분리.',
        '- 27자 초과/괄호 불균형/관계 플래그는 확인 후보이며 확정 오류 개수가 아니다.',
        '- 화자명이 손상된 레코드, 별도 전투 자막 형식, 압축/동적 대사는 이 앵커 검사만으로 보장하지 못한다.',
        '', '## 제보 및 확인된 문맥', '']
    def context(off):
        idx=by_off.get(off)
        if idx is None:return
        for r in rows[max(0,idx-2):idx+3]:
            if abs(r['off']-off)<0x600:lines.append(f'- `0x{r["off"]:X}` {shown(r["text"])}')
    for off,note in known.items():
        lines.extend([f'### 0x{off:X}', '',note,'']);context(off);lines.append('')
    lines.extend(['## 라미아 파손 및 구조 후보 (전체)',''])
    for r in flagged:
        lines.append(f'- `0x{r["off"]:X}` [{" / ".join(r["reasons"])}] {shown(r["text"])}')
    lines.extend(['','## 동료 화자 반각 공백/ASCII 후보 (시나리오 전체)',''])
    related=Counter()
    for r in rows:
        who=speaker(r['text'])
        if who not in {'레몬','빈델','에키드나','Ｗ１６','Ｗ１７'}:continue
        if any(ord(c)<128 and c!='@' for c in r['text']):
            related[who]+=1;lines.append(f'- `0x{r["off"]:X}` {shown(r["text"])}')
    lines.extend(['','## 라미아 전체 목록 (원문 순서, 검사 추적용)',''])
    for off,r in sorted(entries.items()):
        lines.append(f'- `0x{off:X}` [{len(r["raw"])}B] {shown(r["text"])}')
    REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'sha256':digest.hexdigest().upper(),'anchors':len(entries),
        'flags':counts,'flagged_unique':len(flagged),'related_ascii':related,
        'report':str(REPORT)},ensure_ascii=False,indent=2))


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--full-current',action='store_true')
    if ap.parse_args().full_current:return full_current_audit()
    rows = json.loads(DRAFT.read_text(encoding="utf-8"))
    by_off = {int(row["off"]): row for row in rows}
    hotfix = json.loads(HOTFIX.read_text(encoding="utf-8"))
    for change in hotfix["changes"]:
        if change["kind"] == "scenario_text":
            off = int(change["map_offset"], 16)
            if off in by_off:
                by_off[off]["new"] = change["new_text"]

    data = ISO.read_bytes()
    actual_rows = []
    payload_mismatches = []
    for off, row in sorted(by_off.items()):
        start = MAP_ISO_OFF + off
        capacity = int(row["orig_len"])
        # 후속 PASS가 같은 슬롯을 더 긴 원래 창 용량으로 재활용한 경우가 있으므로
        # 누적 JSON의 최초 orig_len이 아니라 실제 NUL까지 읽어 페이로드를 판정한다.
        end = data.index(0, start)
        raw = bytes(data[start:end])
        actual = decode(raw)
        actual_rows.append((off, capacity, actual, row))
        if actual != row["new"]:
            payload_mismatches.append((off, row["new"], actual))

    halfwidth = [(off, cap, text) for off, cap, text, _ in actual_rows if " " in text]
    role_halfwidth = [item for item in halfwidth if speaker(item[2]) in ROLE_SPEAKERS]
    normalization_overflow = [
        (off, cap, len(encode(text.replace(" ", "　"))), text)
        for off, cap, text in halfwidth
        if len(encode(text.replace(" ", "　"))) > cap
    ]
    normalization_deltas = Counter(
        len(encode(text.replace(" ", "　"))) - len(encode(text))
        for _off, _cap, text in halfwidth
    )

    hard = []
    for off, cap, text, _ in actual_rows:
        reasons = [name for name, pattern in HARD_PATTERNS.items() if pattern.search(text)]
        if reasons:
            hard.append((off, cap, text, reasons))

    structural = []
    pairs = (("（", "）"), ("『", "』"), ("<", ">"))
    for off, cap, text, _ in actual_rows:
        reasons = []
        if "�" in text:
            reasons.append("디코드 불능 문자")
        for opening, closing in pairs:
            if text.count(opening) != text.count(closing):
                reasons.append(f"{opening}{closing} 불균형")
        if text.count("@") >= 3:
            reasons.append(f"{text.count('@') + 1}줄 대사")
        longest = max((len(line) for line in text.split("@")), default=0)
        if longest >= 34:
            reasons.append(f"과장문 {longest}자")
        if reasons:
            structural.append((off, cap, text, reasons))

    # 동일한 긴 문장이 여러 슬롯에 반복되면 잘못된 장면 이식 후보로 남긴다.
    duplicates = defaultdict(list)
    for off, _cap, text, _ in actual_rows:
        body = text.split("：", 1)[-1]
        if len(body) >= 24:
            duplicates[body].append(off)
    duplicate_groups = [(body, offs) for body, offs in duplicates.items() if len(offs) >= 2]

    all_role_halfwidth = []
    for item in iso_rows(ISO):
        text = item["text"]
        if speaker(text) in ROLE_SPEAKERS and " " in text:
            all_role_halfwidth.append((item["off"], item["len"], text))
    outside_modified = [item for item in all_role_halfwidth if item[0] not in by_off]

    lines = [
        "# CURRENT ISO 수정 대사 파손 전수 감사",
        "",
        f"- 누적 수정 슬롯: {len(actual_rows):,}개",
        f"- 누적안 대비 페이로드 불일치: {len(payload_mismatches)}개",
        f"- 일반 공백(U+0020) 포함 슬롯: {len(halfwidth)}개",
        f"- 핵심 인물 화자의 일반 공백 슬롯: {len(role_halfwidth)}개",
        f"- 전체 핵심 인물 대사 중 일반 공백 슬롯: {len(all_role_halfwidth)}개",
        f"- 누적 수정 범위 밖 핵심 인물 일반 공백 슬롯: {len(outside_modified)}개",
        f"- 문법·호칭 강위험 후보: {len(hard)}개",
        f"- 괄호·줄 수·과장문 구조 후보: {len(structural)}개",
        f"- 일반→전각 공백 치환 시 슬롯 초과: {len(normalization_overflow)}개",
        f"- 긴 문장 중복 그룹: {len(duplicate_groups)}개",
        "",
        "## 판정 기준",
        "",
        "OGs 한글 대화창은 일반 공백이 비정상적으로 넓게 보일 수 있으므로, 수정 대사의 단어 사이는 전각 공백(U+3000)을 사용해야 한다.",
        "",
        "## 문법·호칭 강위험 후보",
        "",
    ]
    for off, cap, text, reasons in hard:
        lines.append(f"- `0x{off:X}` [{cap}] ({', '.join(reasons)}): {shown(text)}")

    lines += ["", "## 구조 후보", ""]
    for off, cap, text, reasons in structural:
        lines.append(f"- `0x{off:X}` [{cap}] ({', '.join(reasons)}): {shown(text)}")

    lines += ["", "## 핵심 인물 일반 공백 후보", ""]
    for off, cap, text in role_halfwidth:
        lines.append(f"- `0x{off:X}` [{cap}]: {shown(text)}")

    lines += ["", "## 기타 인물 일반 공백 후보", ""]
    for off, cap, text in halfwidth:
        if speaker(text) not in ROLE_SPEAKERS:
            lines.append(f"- `0x{off:X}` [{cap}]: {shown(text)}")

    lines += ["", "## 누적 수정 범위 밖 핵심 인물 일반 공백 후보", ""]
    for off, cap, text in outside_modified:
        lines.append(f"- `0x{off:X}` [{cap}]: {shown(text)}")

    lines += ["", "## 긴 문장 중복 그룹", ""]
    for body, offs in duplicate_groups:
        rendered = ", ".join(f"0x{off:X}" for off in offs)
        lines.append(f"- {rendered}: {shown(body)}")

    lines += ["", "## 누적안 대비 페이로드 불일치", ""]
    for off, expected, actual in payload_mismatches:
        lines.append(f"- `0x{off:X}` 예상: {shown(expected)}")
        lines.append(f"  - 실제: {shown(actual)}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "slots": len(actual_rows),
        "payload_mismatches": len(payload_mismatches),
        "halfwidth_spaces": len(halfwidth),
        "role_halfwidth_spaces": len(role_halfwidth),
        "all_role_halfwidth_spaces": len(all_role_halfwidth),
        "outside_modified_role_halfwidth_spaces": len(outside_modified),
        "hard_candidates": len(hard),
        "structural_candidates": len(structural),
        "space_normalization_overflow": len(normalization_overflow),
        "space_normalization_length_deltas": normalization_deltas,
        "duplicate_groups": len(duplicate_groups),
        "hard_reason_counts": Counter(reason for *_, reasons in hard for reason in reasons),
        "report": str(REPORT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
