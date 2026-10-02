# -*- coding: utf-8 -*-
"""Extract and triage every Axel scenario utterance in PASS25."""
from __future__ import annotations

import json
import argparse
import hashlib
import mmap
import re
from collections import Counter
from pathlib import Path

from build_og2new_scene_workbench import iso_rows
from ogs_korean_codec import encode, decode


ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_v20260830_TONE_PASS25.iso"
OUT_JSON = ROOT / "runtime" / "axel_full_audit_pass25.json"
OUT_MD = ROOT / "AXEL_FULL_AUDIT_PASS25.md"
CURRENT_ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
BASELINE_ISO = ROOT / "baseline" / "srwogs-v1.4.3s1.iso"
MAP_ISO_OFF = 0xC10800

SPEAKER = re.compile(r"^([^：（]{1,16})[：（]")
BROKEN = re.compile(
    r"습니다에요|합니다에요|입니다에요|하였습니다인걸|했거나해버렸|"
    r"해버렸습니다인|겠습니까요|이옵니다|하겠사옵니다"
)
NONHUMAN = re.compile(
    r"W시리즈|Ｗ시리즈|W넘버|Ｗ넘버|넘버즈|인조인간|인형|피조물|"
    r"최고걸작|최고　걸작|실패작|후기　로트|조정|기능부전|기능　부전|"
    r"감정회로|시냅스|제작|만들어졌|만들어진|창조"
)
MEMORY = re.compile(
    r"기억|전이　충격|전이충격|말투|경어|존댓말|이름조차|누군지|"
    r"과거|떠올|생각나|잊"
)
RELATION = re.compile(
    r"레몬|빈델|라미아|W17|Ｗ１７|W16|Ｗ１６|에키드나|워단|W15|Ｗ１５|"
    r"쿄스케|베오울프|엑셀렌|엑세　누님|알피미|연인|사랑|배신|대장"
)
POLITE = re.compile(r"습니다|습니까|세요|드립니다|입니다|합니다|하죠|군요|네요")
ROUGH = re.compile(r"(?:해라|마라|했어|한다|이다|없다|있다|겠나|인가|이냐|거야|말야|구만)(?:[！？…。]|$)")

# Full manual adjudication after reading all 1,043 unique utterances and all
# 393 repeated occurrences in context. Every occurrence receives one verdict.
SETTING_FIX = {
    # A human Axel must not explain his AP-like speech as a broken language unit.
    0x5E24DE9, 0x5E24F51, 0x5E42168, 0x5E45C63, 0x5EE454F,
    0x6077833, 0x6077896, 0x6164EF9, 0x61EDAD0, 0x61F4ADB,
    0x61F55D1, 0x61F5634,
    # Original Lamia/W-series self-identity residue.
    0x5F730C0, 0x5F734B0, 0x6533E01, 0x6533FC0, 0x653402A,
    0x65340D2, 0x653413C,
    # Human/emotion continuity, memory order, and relationship residue.
    0x5F1CE4D, 0x6079062, 0x607A12D, 0x61EE763, 0x61EE857,
    0x61F3B38, 0x6295202, 0x63E7595, 0x63E75C3, 0x63E760D,
    0x6774800, 0x67A246C, 0x6878D99,
}

TEXT_FIX = {
    0x5F07B5E, 0x5F3F4B0, 0x5F414FE, 0x5F415D5, 0x5EA1013,
    0x60756AB, 0x6078BDB, 0x61850E8, 0x61EF970, 0x6212727,
    0x6295085, 0x637F6B8, 0x64B268A, 0x6533158, 0x65358B0,
    0x676E7E0, 0x676EA7F, 0x676FD3D, 0x677047F, 0x6770D01,
    0x6773968,
}

SCENE_COMPANION = {
    # W16's protection/sacrifice target must be Lemon, not Lamia.
    0x63C2620, 0x63C2730, 0x63C2997, 0x63C2B57, 0x63C2C34,
    0x63C2C91, 0x63C2DE6, 0x63C2EA1, 0x63C2EEA, 0x63C2F4F,
    0x63E737F,
    # Paired with the Lamia-Kyosuke personal-rivalry scenes already found.
    0x65AD60C, 0x65AD672, 0x65AF7DC,
}

ODE_POSSESSION = {0x68783AD, 0x68784CA, 0x68784FE, 0x6878541}


def manual_verdict(off: int) -> tuple[str, str, str]:
    if off in SETTING_FIX:
        return (
            "설정·관계 수정 필요",
            "인간 액셀의 정체성, 기억상실 연속성 또는 확정 관계 기준과 충돌",
            "OG2 액셀 패치 1.20과 관계 기준서에 맞춰 장면 의미를 재작성",
        )
    if off in TEXT_FIX:
        return (
            "문장 교정 필요",
            "오탈자, 자동변환 파손 또는 의미가 성립하지 않는 문장",
            "화자와 장면 의미는 유지하고 문장만 정상 한국어로 교정",
        )
    if off in SCENE_COMPANION:
        return (
            "장면 동반 수정",
            "문장 단독보다 연결 장면의 잘못된 보호 대상·라이벌 전제에 종속",
            "W16 희생 또는 라미아-쿄스케 장면을 고칠 때 함께 재검토",
        )
    if off in ODE_POSSESSION:
        return (
            "정상—ODE 침식 발화",
            "표시 화자는 액셀이지만 실제 발화 주체가 액셀 본인이 아닌 장면",
            "유지",
        )
    return ("이상 없음", "액셀의 시점·성격·관계 및 장면 문맥과 충돌 없음", "유지")


def speaker(text: str) -> str:
    match = SPEAKER.match(text)
    return match.group(1) if match else ""


def shown(text: str) -> str:
    return text.replace("@", " / ")


def current_audit() -> None:
    """Read-only full-image anchor/encoding review of the active CURRENT ISO."""
    previous = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else {}
    old_by_off = {int(item['off']): item for item in previous.get('items', [])}
    with CURRENT_ISO.open('rb') as source:
        image = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
        entries = {}
        for label in ('액셀：', '액셀（'):
            needle = encode(label)
            at = 0
            while True:
                at = image.find(needle, at)
                if at < 0:
                    break
                end = image.find(b'\0', at, min(at + 1024, len(image)))
                if end > at:
                    raw = image[at:end]
                    entries[at-MAP_ISO_OFF] = {
                        'off': at-MAP_ISO_OFF, 'raw': raw,
                        'text': decode(raw),
                        'boundary': at > 0 and image[at-1] == 0,
                    }
                at += len(needle)
        sha = hashlib.sha256()
        for at in range(0, len(image), 8*1024*1024):
            sha.update(image[at:at+8*1024*1024])
        image.close()
    rows = iso_rows(CURRENT_ISO)
    row_index = {r['off']: i for i, r in enumerate(rows)}
    counters = Counter()
    with BASELINE_ISO.open('rb') as baseline:
        for off, item in sorted(entries.items()):
            text = item['text']; reasons=[]
            if not item['boundary']:
                reasons.append('NUL경계불일치'); counters['boundary'] += 1
            if ' ' in text:
                reasons.append('반각공백'); counters['halfwidth_space'] += 1
                baseline.seek(MAP_ISO_OFF + off)
                old = baseline.read(1024).split(b'\0', 1)[0]
                if b' ' in old: counters['baseline_also_space'] += 1
                if len(encode(text.replace(' ', '　'))) > len(old):
                    counters['fullwidth_exceeds_baseline_length'] += 1
            other = sorted(set(c for c in text if ord(c) < 128 and c not in ' @'))
            if other:
                reasons.append('기타ASCII:' + repr(''.join(other)))
                counters['other_ascii'] += 1
            try: valid = encode(text) == item['raw']
            except UnicodeError: valid = False
            if not valid or '\ufffd' in text:
                reasons.append('인코딩왕복실패'); counters['encoding'] += 1
            if text.count('@') > 2:
                reasons.append('4줄이상'); counters['line_count'] += 1
            for opening, closing in (('（','）'), ('『','』')):
                if text.count(opening) != text.count(closing):
                    reasons.append('괄호불균형:' + opening + closing)
                    counters['brackets'] += 1
            if BROKEN.search(text):
                reasons.append('파손어미'); counters['broken_ending'] += 1
            if '빈델님' in text or '레몬님' in text or '라미아　대장' in text:
                reasons.append('관계호칭확인'); counters['relation_honorific'] += 1
            old_item = old_by_off.get(off)
            if old_item and old_item['text'] == text:
                item['historical_verdict'] = old_item.get('verdict', old_item.get('historical_verdict', '이전 감사에 없음'))
                item['historical_reason'] = old_item.get('manual_reason', old_item.get('historical_reason', ''))
                counters['previous_verdict_text_still_identical'] += 1
            elif old_item:
                item['historical_verdict'] = '문장 변경: 이전 판정 재검토'
                counters['previous_verdict_text_changed'] += 1
            else:
                item['historical_verdict'] = '이전 감사에 없음'
                counters['new_anchor'] += 1
            item['reasons'] = reasons
    flagged = [item for item in entries.values() if item['reasons']]
    historical = [item for item in entries.values()
                  if item['historical_verdict'] not in ('이상 없음', '이전 감사에 없음',
                      '정상—ODE 침식 발화')]
    source_counts = previous.get('source_pass25_match_counts')
    if source_counts is None and previous.get('iso') == str(CURRENT_ISO):
        source_counts = previous.get('flags', {})
    if source_counts is None:
        source_counts = counters
    lines = ['# CURRENT 액셀 대사 전수 조사 (2026-10-01)', '',
        '- 이 감사 실행은 읽기 전용이다. CURRENT ISO의 액셀 대사 수정은 별도 복구 도구로 이미 반영되었다.',
        '- 이전 판정과 달랐던 143개는 문맥을 다시 검토했다. 그중 2개(0x63E75C3, 0x63E760D)를 수정했고, 나머지 141개는 명백한 설정 모순을 찾지 못해 유지했다. 별도로 0x6295202도 수정했다. 실기 확인은 아직 아니다.',
        '- SHA256: `'+sha.hexdigest().upper()+'`',
        f'- 전체 ISO에서 찾은 액셀 직접 대사/독백: {len(entries)}개.',
        f'- 이전 PASS25와 동일한 문장: {source_counts["previous_verdict_text_still_identical"]}개;'
        f' 문장 변경: {source_counts["previous_verdict_text_changed"]}개;'
        f' 새 앵커: {source_counts["new_anchor"]}개.',
        '- 검사 집계: `'+json.dumps(counters, ensure_ascii=False)+'`',
        '- NUL 경계 및 인코딩 검사는 자동 전수 검사다. 내용과 말투 판정은 이전 PASS25 판정이 문장까지 동일할 때만 재사용한다.',
        '- 반각 공백은 이번 라미아 사례처럼 실기 파손 위험이다. 길이 초과는 기본판 문자열 길이와 비교한 1차 지표다.',
        '- 전투 자막, 화자명 자체가 깨진 텍스트, 압축/동적 대사는 이 앵커 검사로 포괄하지 않는다.',
        '', '## 표시 파손 및 구조 후보', '']
    for item in sorted(flagged, key=lambda x:x['off']):
        lines.append(f'- `0x{item["off"]:X}` [{", ".join(item["reasons"])}] {shown(item["text"])}')
    lines += ['', '## 문맥 판정 재검토 대상', '']
    for item in sorted(historical, key=lambda x:x['off']):
        off=item['off']; lines += [f'### 0x{off:X} — {item["historical_verdict"]}', '']
        if item.get('historical_reason'):
            lines.append('- 이전 판정 근거: '+item['historical_reason'])
        idx=row_index.get(off)
        if idx is not None:
            for row in rows[max(0,idx-2):idx+3]:
                if abs(row['off']-off)<0x700:
                    lines.append(f'- `0x{row["off"]:X}` {shown(row["text"])}')
        lines.append('')
    lines += ['## 액셀 전체 대사 목록', '']
    for item in sorted(entries.values(),key=lambda x:x['off']):
        lines.append(f'- `0x{item["off"]:X}` [{len(item["raw"])}B] {shown(item["text"])}')
    OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    payload = {'iso':str(CURRENT_ISO),'sha256':sha.hexdigest().upper(),
        'axel_lines':len(entries),'flags':dict(counters),
        'source_pass25_match_counts': {key:source_counts[key]
            for key in ('previous_verdict_text_still_identical',
                'previous_verdict_text_changed', 'new_anchor')},
        'items':[{'off':i['off'],'len':len(i['raw']),'text':i['text'],
                  'reasons':i['reasons'],'historical_verdict':i['historical_verdict'],
                  'historical_reason':i.get('historical_reason','')}
                 for i in sorted(entries.values(),key=lambda x:x['off'])]}
    OUT_JSON.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'sha256':payload['sha256'],'axel_lines':len(entries),
                      'flags':dict(counters),'flagged_unique':len(flagged),
                      'review_targets':len(historical),'report':str(OUT_MD)},
                     ensure_ascii=False,indent=2))


def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument('--current',action='store_true')
    if ap.parse_args().current:
        return current_audit()
    rows = iso_rows(ISO)
    indices = [
        i for i, row in enumerate(rows)
        if row["text"].startswith(("액셀：", "액셀（"))
    ]
    items = []
    for i in indices:
        row = rows[i]
        text = row["text"]
        flags = []
        if BROKEN.search(text):
            flags.append("자동변환_파손어미")
        if NONHUMAN.search(text):
            flags.append("인간설정_충돌후보")
        if MEMORY.search(text):
            flags.append("기억상실_연속성")
        if RELATION.search(text):
            flags.append("관계설정")
        if any(x in text for x in ("빈델님", "레몬님", "라미아　대장", "라미아대장")):
            flags.append("잘못된_상하호칭후보")
        if text.startswith("액셀：") and POLITE.search(text):
            flags.append("존댓말_시점확인")
        if text.startswith("액셀：") and ROUGH.search(text):
            flags.append("군인체_문맥확인")

        context = []
        for j in range(max(0, i - 3), min(len(rows), i + 4)):
            other = rows[j]
            if abs(other["off"] - row["off"]) > 0x700:
                continue
            context.append({
                "off": other["off"],
                "speaker": speaker(other["text"]),
                "text": other["text"],
                "target": j == i,
            })
        verdict, reason, recommendation = manual_verdict(row["off"])
        items.append({
            "off": row["off"],
            "len": row["len"],
            "text": text,
            "flags": flags,
            "context": context,
            "verdict": verdict,
            "manual_reason": reason,
            "recommendation": recommendation,
        })

    flag_counts = Counter(flag for item in items for flag in item["flags"])
    verdict_counts = Counter(item["verdict"] for item in items)
    payload = {
        "iso": str(ISO),
        "axel_lines": len(items),
        "flag_counts": dict(flag_counts),
        "verdict_counts": dict(verdict_counts),
        "items": items,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# PASS25 액셀 대사 전량 감사",
        "",
        f"- 액셀 화자 대사: {len(items)}건",
        f"- 고유 문장: {len(set(x['text'] for x in items))}건",
        f"- 중복 발생: {len(items) - len(set(x['text'] for x in items))}건",
        f"- 설정·관계 수정 필요: {verdict_counts['설정·관계 수정 필요']}건",
        f"- 문장 교정 필요: {verdict_counts['문장 교정 필요']}건",
        f"- 장면 동반 수정: {verdict_counts['장면 동반 수정']}건",
        f"- 정상—ODE 침식 발화: {verdict_counts['정상—ODE 침식 발화']}건",
        f"- 이상 없음: {verdict_counts['이상 없음']}건",
        f"- 미판정: {verdict_counts['미판정']}건",
        "",
        "## 설정·관계 수정 필요",
        "",
    ]
    for number, item in enumerate((x for x in items if x["verdict"] == "설정·관계 수정 필요"), 1):
        lines.extend([
            f"### S{number:03d} — 0x{item['off']:07X}",
            "",
            f"- 판정: {item['manual_reason']}",
            f"- 수정 방향: {item['recommendation']}",
            "",
            "```text",
        ])
        for ctx in item["context"]:
            mark = ">" if ctx["target"] else " "
            lines.append(f"{mark} 0x{ctx['off']:07X} {shown(ctx['text'])}")
        lines.extend(["```", ""])
    for title, verdict, prefix in (
        ("문장 교정 필요", "문장 교정 필요", "T"),
        ("장면 동반 수정", "장면 동반 수정", "C"),
        ("ODE 침식 발화—정상", "정상—ODE 침식 발화", "O"),
    ):
        lines.extend([f"## {title}", ""])
        for number, item in enumerate((x for x in items if x["verdict"] == verdict), 1):
            lines.extend([
                f"### {prefix}{number:03d} — 0x{item['off']:07X}",
                "",
                f"- 판정: {item['manual_reason']}",
                f"- 수정 방향: {item['recommendation']}",
                "",
                "```text",
            ])
            for ctx in item["context"]:
                mark = ">" if ctx["target"] else " "
                lines.append(f"{mark} 0x{ctx['off']:07X} {shown(ctx['text'])}")
            lines.extend(["```", ""])
    lines.extend([
        "## 관계별 전수 결론",
        "",
        "- 액셀-레몬: 연인·결별 축은 대체로 정상이다. 액셀 자신을 레몬의 피조물로 말하는 대사는 없다.",
        "- 액셀-쿄스케: 적대에서 전우로 이동하는 큰 흐름은 정상이나, 최종 ODE 장면의 `쿄스케 중위/당신`은 이름만 부르는 관계로 되돌려야 한다.",
        "- 액셀-라미아: 전 대장-부하 축은 유지되지만 개인 결투, `당신` 역존칭, 라미아의 쿄스케 집착을 전제한 문장이 남았다.",
        "- 액셀-W16: 자율 의지 인정은 정상이다. 다만 해당 중복 분기의 희생 대상이 라미아로 바뀐 장면과 묶어 수정해야 한다.",
        "- 액셀-빈델·워단: 인간 지휘관과 옛 사상적 동지/별도 전투원의 결별로 읽히며 직접 충돌 없음.",
        "- 액셀-알피미: 초반 분석 대상에서 후반 재생·귀속의 거울로 이동하는 관계가 유지된다.",
        "",
        "## 전체 액셀 대사 판정",
        "",
        "```text",
    ])
    for item in items:
        lines.append(
            f"0x{item['off']:07X}[{item['len']:3}] [{item['verdict']}] {shown(item['text'])}"
        )
    lines.extend(["```", ""])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "axel_lines": len(items),
        "automatic_candidates": sum(bool(x["flags"]) for x in items),
        "flag_counts": dict(flag_counts),
        "verdict_counts": dict(verdict_counts),
        "md": str(OUT_MD),
        "json": str(OUT_JSON),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
