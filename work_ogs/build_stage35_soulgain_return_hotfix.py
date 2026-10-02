# -*- coding: utf-8 -*-
"""35화 뒤 실제 잔존 슬롯을 `강화형 소울게인`으로 복구한다.

새 ISO를 만들지 않고 CURRENT.iso만 제자리 수정한다. 세이브 스테이트에서
확인된 실제 잔존 슬롯(0x49)에 소울게인 본체와 강화 무장을 결합한다.
처음에 강화 대상으로 잘못 추정했던
0x1A1은 원래 역할 교체 상태인 일반 소울게인으로 복원하고, 0x136은
안쥬르그로 유지한다.

초기 1.2 패치의 실제 결과를 xdelta 스트림으로 대조하면 Unit[0x49]의 레코드
내부 기체 키(+0x10)는 목적지 키 0x38이 아니라 소울게인의 0x106이다. 저장된
보유 키 0x38은 UTbl을 통해 이 슬롯을 찾는다. +0x46은 목록
아이콘 계열이므로 현재 보이는 기체의 값(안쥬르그 0x2B / 소울게인 0x63)을 쓴다.

런타임 역어셈블 결과 0x1EE360은 파일럿 허용 판정이 아니라 이동/지형
게이트다. Unit +0x4A~+0x50을 허용 파일럿 네 칸으로 본 종전 가설은
폐기했으며, 이 필드들은 소울게인 원값을 유지한다.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from ogs_korean_codec import decode, encode


ROOT = Path(__file__).resolve().parent
ISO = ROOT / "build" / "SRWOGS_AxelRoleSwap_kr_CURRENT.iso"
BASELINE = ROOT / "baseline" / "srwogs-v1.4.3s1.iso"
MANIFEST = ROOT / "runtime" / "stage35_soulgain_return_manifest.json"

ARCHIVES = {"SHARED": 0x5DA000, "IM": 0x83F000}
UNIT_DATA = 0x11F8A4
UNIT_STRIDE = 0x64
WTBL_DATA = 0x129F7C
WEAP_DATA = 0x12BF88
WEAP_STRIDE = 0x24
STRG_TAG = 0x155BFC
PLOT_DATA = 0x13B490
PLOT_STRIDE = 0x94

ANGELG_SLOT = 0x1A1
RETURN_SLOT = 0x049
SOULGAIN_SLOT = 0x136
VAISAGA_ALLIED_SLOT = 0x04E
UID_ANGELG = 0x2B
UID_SOULGAIN = 0x63
UID_VAISAGA = 0x30
VAISAGA_RAW_KEY = 0x42
AXEL_ROLE_PLOTS = (53, 54)
# +0x46은 목록에서 사용하는 외형/아이콘 계열이다.
VISIBLE_UNIT_UIDS = {
    0x048: UID_SOULGAIN,
    0x049: UID_SOULGAIN,
    0x0CE: UID_ANGELG,
    SOULGAIN_SLOT: UID_ANGELG,
    ANGELG_SLOT: UID_SOULGAIN,
}
# 초반 역할 교체 슬롯은 복사된 원본 raw key 때문에 서로 같은 기체로
# 역참조되었다. 목적지 슬롯의 기준판 raw key를 복원해 중복을 없앤다.
# 0x49는 1.2 패치부터 의도적으로 소울게인의 내부 기체 키 0x106을 쓴다.
# 목적지 키로 되돌리는 대상은 나머지 초반 적 슬롯뿐이다.
EARLY_DESTINATION_RAW_KEYS = (0x048, 0x0CE)
NORMAL_WEAPONS = tuple(range(0xD86, 0xD8B))
ENHANCED_WEAPONS = tuple(range(0xD97, 0xD9C))
# Unit[0x136] must not share these overwritten weapons with enhanced Soulgain.
# The former return-Angelg keys are unused after Unit[0x49] changes to Soulgain.
REVERSE_ANGELG_WEAPONS = tuple(range(0x8B3, 0x8B8))
AUXILIARY_WEAPONS = (0xD8B, 0xD8C)
ENHANCED_POWERS = (3500, 4200, 4300, 5400, 6200)
ENHANCED_NAME = "강화형소울게인"
LEGACY_ENHANCED_NAMES = {"강화형 소울게인", ENHANCED_NAME}
ENHANCED_NAME_IDS = {"SHARED": 0x70D, "IM": 0x70E}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def u16(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def unit_off(base: int, index: int) -> int:
    return base + UNIT_DATA + index * UNIT_STRIDE


def weapon_index(fh, base: int, raw_key: int) -> int:
    fh.seek(base + WTBL_DATA + raw_key * 2)
    blob = fh.read(2)
    if len(blob) != 2:
        raise ValueError(f"WTbl[0x{raw_key:X}] 읽기 실패")
    return u16(blob, 0)


def weapon_off(base: int, index: int) -> int:
    return base + WEAP_DATA + index * WEAP_STRIDE


def make_enhanced_weapon(source: bytes, ordinal: int) -> bytes:
    result = bytearray(source)
    struct.pack_into("<H", result, 0x08, ENHANCED_POWERS[ordinal])
    flags = result[0x14]
    cost = result[0x1A]
    morale = result[0x1B]
    if morale:
        result[0x1B] = morale - 10
    if flags & 0x40 and cost:
        result[0x1A] = cost - 10
    if flags & 0x80 and cost:
        result[0x1A] = cost + 2
    # OG2 액셀 1.2 강화형에서 1칸짜리 근접 무장이 1~3으로 확대된다.
    if ordinal == 1:
        result[0x18] = 3
    return bytes(result)


def make_enhanced_unit(soulgain: bytes, name_id: int) -> bytes:
    result = bytearray(soulgain)
    struct.pack_into("<H", result, 0x0C, name_id)
    # 갈아타기 필터 0x431740의 필수 게이트(속성 0x59)는
    # 0x1B01D0 -> 0x1CE290 -> 0x1A6BB0을 거쳐 Unit +0x22를 읽는다.
    # 일반 소울게인의 0은 후보에서 탈락한다. 강화형 반환 슬롯은 사용자의
    # 요청대로 파일럿 계열 제한을 없애기 위해 모든 카테고리 비트를 허용한다.
    # 다른 공통 상태 게이트(보유/잠금/배정 상태)는 기존 로직을 그대로 따른다.
    struct.pack_into("<H", result, 0x22, 0xFFFF)
    weapons = ENHANCED_WEAPONS + AUXILIARY_WEAPONS
    weapons += (0xFFFF,) * (16 - len(weapons))
    struct.pack_into("<16H", result, 0x24, *weapons)
    # +0x4A~+0x50도 소울게인 원값을 유지한다. 이를 허용 파일럿 목록으로
    # 오인해 안쥬르그 값을 넣었던 2026-09-04 시험은 실기에서 무효였고 원복했다.
    return bytes(result)


def make_reverse_unit(angelg: bytes, soulgain: bytes) -> bytes:
    """Preserve Angelg and isolate its weapons from the enhanced Soulgain set."""
    result = bytearray(angelg)
    struct.pack_into('<5H', result, 0x24, *REVERSE_ANGELG_WEAPONS)
    return bytes(result)


def isolated_angelg_weapon_plan(current, baseline, base):
    """Read-only guarded plan; preserve baseline allied Angelg stats exactly.

    Check every Unit and every WTbl alias, not just the five raw keys. No table
    expansion, animation resource, pilot/boarding mask, or Soulgain edit.
    """
    current.seek(base + UNIT_DATA - 12)
    tag, size, count = struct.unpack('<4sII', current.read(12))
    if tag != b'Unit' or count != 0x1AB:
        raise ValueError('Unexpected Unit table')
    current.seek(base + UNIT_DATA)
    units = current.read(count * UNIT_STRIDE)
    current.seek(base + WTBL_DATA)
    lookup = struct.unpack('<4096H', current.read(8192))
    targets = {lookup[k] for k in REVERSE_ANGELG_WEAPONS}
    if len(targets) != 5:
        raise ValueError('Angelg weapon targets are not independent')
    for slot in range(count):
        keys = struct.unpack_from('<16H', units, slot * UNIT_STRIDE + 0x24)
        if slot in (RETURN_SLOT, SOULGAIN_SLOT):
            # These two units are explicitly assigned disjoint sets by builder.
            continue
        if any(k < len(lookup) and lookup[k] in targets for k in keys):
            raise ValueError(f'Weapon storage still used by Unit[{slot:X}]')
    plan = []
    for src, dst in zip(ENHANCED_WEAPONS, REVERSE_ANGELG_WEAPONS):
        baseline.seek(weapon_off(base, weapon_index(baseline, base, src)))
        desired = baseline.read(WEAP_STRIDE)
        at = weapon_off(base, lookup[dst])
        current.seek(at)
        old = current.read(WEAP_STRIDE)
        baseline.seek(weapon_off(base, weapon_index(baseline, base, dst)))
        original = baseline.read(WEAP_STRIDE)
        if old not in (original, desired):
            raise ValueError(f'Unexpected Angelg target weapon {dst:X}')
        plan.append((at, old, desired))
    return plan


def make_extended_strg(current: bytes, name_id: int) -> bytes:
    if current[:4] != b"Strg":
        raise ValueError("Strg 태그가 아니다")
    total = u32(current, 4)
    count = u32(current, 8)
    if count == name_id + 1:
        pointer = u32(current, 0x0C + name_id * 4)
        end = current.find(b"\0", pointer)
        if end < 0 or decode(current[pointer:end]) not in LEGACY_ENHANCED_NAMES:
            raise ValueError("확장된 Strg 이름 검증 실패")
        encoded_name = encode(ENHANCED_NAME) + b"\0"
        old_size = end - pointer + 1
        if len(encoded_name) > old_size:
            raise ValueError("기존 확장 이름 공간보다 새 이름이 큼")
        result = bytearray(current[:total])
        result[pointer:pointer + old_size] = encoded_name + b"\0" * (old_size - len(encoded_name))
        return bytes(result)
    if count != name_id:
        raise ValueError(f"예상하지 못한 Strg 개수: 0x{count:X}")
    pointer0 = u32(current, 0x0C)
    pointer1 = u32(current, 0x10)
    if pointer0 != 0x0C + count * 4 or not pointer0 < pointer1 <= total:
        raise ValueError("Strg 포인터 배열 경계 불일치")
    string0 = current[pointer0:pointer1]
    if not string0.endswith(b"\0"):
        raise ValueError("Strg 첫 문자열 종단자 없음")
    encoded_name = encode(ENHANCED_NAME) + b"\0"
    new_total = total + len(string0) + len(encoded_name)
    result = bytearray(current[:new_total])
    if not any(result[total:new_total]):
        # 다음 태그 전의 0 패딩에 정상 확장할 수 있는 경우(SHARED).
        struct.pack_into("<I", result, 4, new_total)
        struct.pack_into("<I", result, 8, count + 1)
        struct.pack_into("<I", result, 0x0C, total)
        struct.pack_into("<I", result, 0x0C + count * 4, total + len(string0))
        result[total:total + len(string0)] = string0
        result[total + len(string0):new_total] = encoded_name
        return bytes(result)

    # IM은 다음 Expl 태그까지 2바이트뿐이다. 기존 문자열 중 다른 긴 문자열의
    # 완전한 접미부인 항목을 그 접미부로 공동 참조시켜 동일 내용의 공간을
    # 확보한다. 태그 크기와 뒤 데이터 위치는 바꾸지 않는다.
    result = bytearray(current[:total])
    need = len(string0) + len(encoded_name)
    rows = []
    for index in range(count):
        pointer = u32(current, 0x0C + index * 4)
        end = current.find(b"\0", pointer, total)
        if end < 0:
            raise ValueError(f"Strg[{index:X}] 종단자 없음")
        rows.append((index, pointer, current[pointer:end + 1]))
    candidate = None
    for index, pointer, value in rows:
        if index == 0 or len(value) < need:
            continue
        for other_index, other_pointer, other_value in rows:
            if other_index != index and len(other_value) > len(value) and other_value.endswith(value):
                candidate = (index, pointer, value, other_pointer + len(other_value) - len(value))
                break
        if candidate and len(value) == need:
            break
    if candidate is None:
        raise ValueError("Strg 무손실 접미부 공유 공간을 찾지 못했다")
    candidate_index, hole, old_value, shared_pointer = candidate
    struct.pack_into("<I", result, 8, count + 1)
    struct.pack_into("<I", result, 0x0C, hole)
    struct.pack_into("<I", result, 0x0C + count * 4, hole + len(string0))
    struct.pack_into("<I", result, 0x0C + candidate_index * 4, shared_pointer)
    result[hole:hole + len(string0)] = string0
    result[hole + len(string0):hole + need] = encoded_name
    if len(old_value) > need:
        result[hole + need:hole + len(old_value)] = b"\0" * (len(old_value) - need)
    return bytes(result)


def add_change(plan: list[dict], label: str, offset: int, old: bytes, new: bytes) -> None:
    if old != new:
        plan.append({"label": label, "offset": offset, "old": old, "new": new})


def main() -> None:
    if not ISO.is_file() or not BASELINE.is_file():
        raise SystemExit("CURRENT ISO 또는 기준 ISO가 없습니다")
    before_hash = sha256(ISO)
    plan: list[dict] = []
    audit: list[dict] = []

    with BASELINE.open("rb") as baseline, ISO.open("rb") as current:
        for archive, base in ARCHIVES.items():
            enhanced_name_id = ENHANCED_NAME_IDS[archive]
            baseline.seek(unit_off(base, ANGELG_SLOT))
            angelg = baseline.read(UNIT_STRIDE)
            baseline.seek(unit_off(base, RETURN_SLOT))
            return_angelg = baseline.read(UNIT_STRIDE)
            baseline.seek(unit_off(base, SOULGAIN_SLOT))
            soulgain = baseline.read(UNIT_STRIDE)
            if u16(angelg, 0x46) != UID_ANGELG or u16(soulgain, 0x46) != UID_SOULGAIN:
                raise SystemExit(f"{archive}: 기준 기체 UID 불일치")

            return_unit = make_enhanced_unit(soulgain, enhanced_name_id)
            normal_role_swap_unit = bytes(soulgain)
            reverse_unit = make_reverse_unit(angelg, soulgain)
            for offset, old, desired in isolated_angelg_weapon_plan(current, baseline, base):
                add_change(plan, f'{archive} isolated Angelg weapon', offset, old, desired)
            for slot, desired, name in (
                (RETURN_SLOT, return_unit, "35화 잔존 강화형 소울게인"),
                (ANGELG_SLOT, normal_role_swap_unit, "일반 소울게인 원복"),
                (SOULGAIN_SLOT, reverse_unit, "안쥬르그"),
            ):
                offset = unit_off(base, slot)
                current.seek(offset)
                old = current.read(UNIT_STRIDE)
                add_change(plan, f"{archive} Unit[0x{slot:X}] {name}", offset, old, desired)

            # 목록 아이콘은 실제로 보이는 기체 계열과 맞춘다.
            for slot, desired_uid in VISIBLE_UNIT_UIDS.items():
                offset = unit_off(base, slot) + 0x46
                current.seek(offset)
                old = current.read(2)
                if len(old) != 2:
                    raise SystemExit(f"{archive} Unit[0x{slot:X}] UID 읽기 실패")
                actual_uid = u16(old, 0)
                if actual_uid not in (UID_ANGELG, UID_SOULGAIN):
                    raise SystemExit(
                        f"{archive} Unit[0x{slot:X}] UID 가드 실패: "
                        f"0x{actual_uid:X}")
                add_change(
                    plan,
                    f"{archive} Unit[0x{slot:X}] 표시 UID 교정",
                    offset,
                    old,
                    struct.pack("<H", desired_uid),
                )

            # 초반 적 역할 교체 레코드의 raw key 중복을 해소한다. 단, 0x49는
            # 1.2 패치의 소울게인 내부 키 0x106이 탑승 호환에 필요하므로 제외한다.
            for slot in EARLY_DESTINATION_RAW_KEYS:
                offset = unit_off(base, slot) + 0x10
                baseline.seek(offset)
                desired = baseline.read(2)
                current.seek(offset)
                old = current.read(2)
                add_change(
                    plan,
                    f"{archive} Unit[0x{slot:X}] raw key 중복 해소",
                    offset,
                    old,
                    desired,
                )

            # 아군용 바이사가도 모든 파일럿에게 개방한다.
            vaisaga_offset = unit_off(base, VAISAGA_ALLIED_SLOT)
            baseline.seek(vaisaga_offset)
            allied_vaisaga = baseline.read(UNIT_STRIDE)
            if (u16(allied_vaisaga, 0x10) != VAISAGA_RAW_KEY or
                    u16(allied_vaisaga, 0x46) != UID_VAISAGA):
                raise SystemExit(f"{archive}: 아군용 바이사가 식별 가드 실패")
            offset = vaisaga_offset + 0x22
            current.seek(offset)
            old = current.read(2)
            add_change(
                plan,
                f"{archive} Unit[0x{VAISAGA_ALLIED_SLOT:X}] 바이사가 탑승 제한 해제",
                offset,
                old,
                struct.pack("<H", 0xFFFF),
            )

            # PTbl 역할 교체 뒤 아군 액셀 raw 키들은 Plot 53(예비 변형 54)으로
            # 연결된다. pilot master 속성 0x21은 Plot +0x12를 직접 읽으므로,
            # 원본 액셀의 0을 라미아 아군값 0x0201로 복구해야 갈아타기 후보가 된다.
            for plot in AXEL_ROLE_PLOTS:
                plot_offset = base + PLOT_DATA + plot * PLOT_STRIDE
                baseline.seek(plot_offset)
                plot_record = baseline.read(PLOT_STRIDE)
                if u16(plot_record, 0x48) != 0x14:
                    raise SystemExit(f"{archive}: Plot[{plot}] 액셀 식별 가드 실패")
                offset = plot_offset + 0x12
                current.seek(offset)
                old = current.read(2)
                add_change(
                    plan,
                    f"{archive} Plot[{plot}] 역할교체 액셀 탑승 마스크 복구",
                    offset,
                    old,
                    struct.pack("<H", 0x0201),
                )

            weapon_rows = []
            for ordinal, (source_key, target_key) in enumerate(zip(NORMAL_WEAPONS, ENHANCED_WEAPONS)):
                source_index = weapon_index(baseline, base, source_key)
                target_index = weapon_index(baseline, base, target_key)
                baseline.seek(weapon_off(base, source_index))
                source = baseline.read(WEAP_STRIDE)
                desired = make_enhanced_weapon(source, ordinal)
                offset = weapon_off(base, target_index)
                current.seek(offset)
                old = current.read(WEAP_STRIDE)
                add_change(plan, f"{archive} Weap[0x{target_key:X}]", offset, old, desired)
                weapon_rows.append({
                    "key": f"0x{target_key:X}",
                    "power": u16(desired, 0x08),
                    "range_max": desired[0x18],
                    "cost_or_ammo": desired[0x1A],
                    "morale": desired[0x1B],
                })

            strg_offset = base + STRG_TAG
            current.seek(strg_offset)
            header = current.read(12)
            if header[:4] != b"Strg":
                raise SystemExit(f"{archive}: Strg 없음")
            old_total = u32(header, 4)
            count = u32(header, 8)
            read_size = old_total if count == enhanced_name_id + 1 else old_total + 64
            current.seek(strg_offset)
            old_region = current.read(read_size)
            new_strg = make_extended_strg(old_region, enhanced_name_id)
            # 확장 전후를 하나의 동일 길이 범위로 비교한다.
            span = max(old_total, len(new_strg))
            old_span = old_region[:span]
            new_span = new_strg + old_region[len(new_strg):span]
            add_change(plan, f"{archive} Strg[{enhanced_name_id:X}]", strg_offset, old_span, new_span)
            audit.append({
                "archive": archive,
                "unit_slots": [f"0x{RETURN_SLOT:X}"],
                "restored_misidentified_slot": f"0x{ANGELG_SLOT:X}",
                "runtime_verified_return_slot": f"0x{RETURN_SLOT:X}",
                "runtime_roster_lookup_key": f"0x{u16(return_angelg, 0x10):X}",
                "master_internal_unit_key": f"0x{u16(return_unit, 0x10):X}",
                "name": ENHANCED_NAME,
                "name_id": f"0x{enhanced_name_id:X}",
                "visible_unit_uid": f"0x{u16(return_unit, 0x46):X}",
                "pilot_family": f"0x{u16(return_unit, 0x48):X}",
                "soulgain_compatibility_fields": {
                    "+0x0A": f"0x{u16(return_unit, 0x0A):X}",
                    "+0x22": f"0x{u16(return_unit, 0x22):X}",
                    "+0x4E": f"0x{u16(return_unit, 0x4E):X}",
                    "+0x50": f"0x{u16(return_unit, 0x50):X}",
                },
                "auxiliary_weapons": [f"0x{x:X}" for x in AUXILIARY_WEAPONS],
                "weapons": weapon_rows,
            })

    changed = sum(sum(a != b for a, b in zip(item["old"], item["new"])) for item in plan)
    print(f"변경 범위 {len(plan)}건 / 실제 변경 {changed}바이트")
    for item in plan:
        print(f"  {item['label']} @0x{item['offset']:X} ({len(item['new'])} bytes)")
    if not plan:
        print("이미 강화형 소울게인 구성이 적용되어 있습니다.")
        return

    # 쓰기 잠금을 먼저 확인한다. 실패하면 아직 아무 바이트도 쓰지 않는다.
    try:
        writer = ISO.open("r+b")
    except PermissionError as exc:
        raise SystemExit("CURRENT ISO가 PCSX2에서 사용 중입니다. PCSX2를 완전히 종료한 뒤 다시 실행하십시오.") from exc
    with writer:
        for item in plan:
            writer.seek(item["offset"])
            if writer.read(len(item["old"])) != item["old"]:
                raise SystemExit(f"쓰기 직전 값 변경 감지: {item['label']}")
        for item in plan:
            writer.seek(item["offset"])
            writer.write(item["new"])

    after_hash = sha256(ISO)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "kind": "stage35-enhanced-soulgain-return-hotfix",
        "target": str(ISO),
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "changed_byte_count": changed,
        "rules": {
            "name": ENHANCED_NAME,
            "visible_unit_uids": {
                f"0x{slot:X}": f"0x{uid:X}"
                for slot, uid in VISIBLE_UNIT_UIDS.items()
            },
            "early_destination_raw_keys": [
                f"0x{slot:X}" for slot in EARLY_DESTINATION_RAW_KEYS
            ],
            "runtime_verified_return_slot": "Unit[0x49], roster/UTbl lookup key 0x38",
            "restored_misidentified_slot": "Unit[0x1A1] restored to the normal role-swapped Soulgain record",
            "enhanced_internal_unit_key": "0x106, matching the original v20260810 role-swap Unit[0x49] record",
            "enhanced_pilot_family": "0x3F Soulgain render/model family retained",
            "compatibility_fields": "Unit +0x22 is 0xFFFF to remove pilot-category restrictions for the enhanced return unit; Unit +0x4A/+0x4C/+0x4E/+0x50 retain Soulgain values; the disproven allowed-pilot interpretation and 14-byte Angelg-value trial were reverted",
            "auxiliary_weapons": [f"0x{x:X}" for x in AUXILIARY_WEAPONS],
            "weapon_power": list(ENHANCED_POWERS),
            "morale_requirement": "-10 when present",
            "en_cost": "-10 for EN weapons",
            "ammo": "+2 for ammo weapons",
            "base_unit_stats": "unchanged from normal Soulgain",
            "new_model_or_weapon": False,
            "ashsaber": "not modified; failed acquisition/backfill experiments were removed before release",
            "vaisaga": "Allied Unit[0x4E] +0x22 is 0xFFFF; raw id 0x42 and UID 0x30 are guarded.",
        },
        "audit": audit,
        "changes": [{
            "label": item["label"],
            "offset": f"0x{item['offset']:X}",
            "length": len(item["new"]),
            "old_sha256": hashlib.sha256(item["old"]).hexdigest().upper(),
            "new_sha256": hashlib.sha256(item["new"]).hexdigest().upper(),
            "old_hex": item["old"].hex(),
            "new_hex": item["new"].hex(),
        } for item in plan],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"적용 완료: {ISO}")
    print(f"SHA-256: {after_hash}")
    print(f"manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
